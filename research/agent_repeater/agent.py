import sys
import json
import asyncio
import datetime
from typing import Dict, List, Any, TypedDict, Optional, Literal

# === Configuration and Constants ===

DEFAULT_CONCURRENCY_LIMIT = 10

# Object Types
OT_TASK = 1
OT_CLOCK = 2
OT_PROCESSED_COMMAND = 3

# Association Types
AT_SCHEDULED_TASK = "scheduled_task"

# Block Markers
MARKER_UNPROCESSED = 0
MARKER_PROCESSED = 1
MARKER_ERROR = 2

# Command Action Codes
CMD_REPEAT = 1
CMD_DESIST = 2

# Fixed Object IDs
ID_TASK_ROOT = 0
ID_GLOBAL_CLOCK = 1

# === Data Structures (TypedDicts) ===


class TaskDefinition(TypedDict):
    """
    The structure of a scheduled task object.
    This is defined by 5 64-bit unsigned integers in the following order:
    1. owner
    2. channel
    3. payload1
    4. payload2
    5. interval_ticks
    """

    owner: int
    channel: int
    payload1: int
    payload2: int
    interval_ticks: int


class ClockState(TypedDict):
    """The structure of the global clock."""

    time: int


# Type aliases
HostAPI = Any
Transaction = Any
CommandBlock = Any  # Opaque type from host, contains .id, .data, and .mark()
ByteOrder = Literal["little", "big"]


class SchedulerAgent:
    """
    A persistent, command-driven scheduler agent using a binary data protocol.
    """

    def _serialize_json(self, data: Dict[str, Any]) -> bytes:
        """Serializes a dictionary to a UTF-8 encoded JSON byte string."""
        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    def _deserialize_json(self, data: bytes) -> Dict[str, Any]:
        """Deserializes a UTF-8 encoded JSON byte string into a dictionary."""
        return json.loads(data)

    async def head(self, script_config: Dict, shard_config: Dict, host: HostAPI):
        """Initializes the agent, setting up sharding and concurrency controls."""
        self.host = host
        self.shard_id: int = shard_config.get("id", 0)
        self.shard_count: int = shard_config.get("count", 1)
        concurrency_limit = (
            script_config.get("system", {})
            .get("core", {})
            .get("concurrency_limit", DEFAULT_CONCURRENCY_LIMIT)
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        print(
            f"Scheduler agent initialized. Shard ID: {self.shard_id}, Concurrency: {concurrency_limit}"
        )

    async def tail(self):
        """The main execution cycle of the agent."""
        current_tick = await self._advance_clock()
        if current_tick is None:
            print("Halting work cycle due to failure in advancing the clock.")
            return

        task_jobs = await self._dispatch_task_processing(current_tick)
        command_jobs = await self._dispatch_command_processing()

        all_jobs = task_jobs + command_jobs
        if all_jobs:
            await asyncio.gather(*all_jobs)

        print(
            f"Agent work cycle complete. Tick: {current_tick}, Shard ID: {self.shard_id}"
        )

    # =========================================================================
    # Clock Management
    # =========================================================================

    async def _advance_clock(self) -> Optional[int]:
        """Advances the global clock by one tick atomically."""
        try:
            try:
                clock_raw = await self.host.get_object(OT_CLOCK, ID_GLOBAL_CLOCK)
                clock_obj: ClockState = self._deserialize_json(clock_raw.data)
                new_tick_count = clock_obj["time"] + 1
            except Exception:
                print("Clock object not found, initializing to 1.")
                clock_raw = self.host.new_object(OT_CLOCK, ID_GLOBAL_CLOCK)
                new_tick_count = 1

            updated_clock: ClockState = {"time": new_tick_count}
            clock_raw.data = self._serialize_json(updated_clock)
            await self.host.put_object(clock_raw)
            return new_tick_count
        except Exception as e:
            print(f"Critical error while updating the clock: {e}")
            return None

    # =========================================================================
    # Task Processing
    # =========================================================================

    async def _dispatch_task_processing(self, current_tick: int) -> List[asyncio.Task]:
        """Streams scheduled tasks and dispatches concurrent workers."""
        jobs: List[asyncio.Task] = []
        try:
            task_stream = self.host.stream_assocs(
                type=AT_SCHEDULED_TASK,
                src=ID_TASK_ROOT,
                shards=self.shard_count,
                shard_id=self.shard_id,
            )
            async for assoc_raw in task_stream:
                job = asyncio.create_task(
                    self._process_scheduled_task(assoc_raw.target_id, current_tick)
                )
                jobs.append(job)
        except Exception as e:
            print(f"Error dispatching task processing: {e}")
        return jobs

    async def _process_scheduled_task(self, task_id: int, current_tick: int):
        """Worker: Checks if a task is due and executes it."""
        async with self.semaphore:
            try:
                task_raw = await self.host.get_object(OT_TASK, task_id)
                task_ints = bytes_to_int_array(task_raw.data, byte_width=8)

                task: TaskDefinition = {
                    "owner": task_ints[0],
                    "channel": task_ints[1],
                    "payload1": task_ints[2],
                    "payload2": task_ints[3],
                    "interval_ticks": task_ints[4],
                }

                if current_tick % task["interval_ticks"] == 0:
                    print(f"Executing scheduled task {task_id} at tick {current_tick}.")
                    await self.host.push_message(
                        task["owner"],
                        task["channel"],
                        int_array_to_bytes(
                            [task["payload1"], task["payload2"]], byte_width=8
                        ),
                    )
            except Exception as e:
                print(f"Failed to process scheduled task {task_id}: {e}")

    # =========================================================================
    # Command Processing (Binary Protocol)
    # =========================================================================

    async def _dispatch_command_processing(self) -> List[asyncio.Task]:
        """Streams binary command blocks and dispatches workers."""
        jobs: List[asyncio.Task] = []
        try:
            # We filter for blocks with marker 0, indicating they are unprocessed.
            command_stream = self.host.stream_blocks(
                "commands", markers=[MARKER_UNPROCESSED, MARKER_ERROR]
            )
            async for block in command_stream:
                job = asyncio.create_task(self._process_command_block(block))
                jobs.append(job)
        except Exception as e:
            print(f"Error dispatching command processing: {e}")
        return jobs

    async def _process_command_block(self, block: CommandBlock):
        """Worker: Processes a binary command block atomically and idempotently."""
        command_id = block.id
        if not command_id:
            print(f"Command block missing ID. Marking as error.")
            await block.mark(MARKER_ERROR)
            return

        async with self.semaphore:
            if await self.host.object_exists(OT_PROCESSED_COMMAND, command_id):
                print(f"Skipping already processed command: {command_id}")
                await block.mark(MARKER_PROCESSED)
                return

            tx = self.host.rwtx()
            try:
                # Deserialize the command from its raw byte format (6 x 64-bit uints)
                command_ints = bytes_to_int_array(block.data, byte_width=8)
                await self._execute_command(tx, command_ints)

                # Mark command as processed using a simple JSON marker
                processed_marker = {
                    "processed_at": int(datetime.datetime.now().timestamp())
                }
                await tx.put_object(
                    OT_PROCESSED_COMMAND,
                    command_id,
                    self._serialize_json(processed_marker),
                )
                # Mark the block as processed within the same transaction.
                await tx.mark(block, MARKER_PROCESSED)
                await tx.commit()
                print(f"Successfully committed command block: {command_id}")
            except Exception as e:
                await tx.rollback()
                print(
                    f"Failed to process command block {command_id}. Rolled back. Error: {e}"
                )
                # On failure, the block is not marked and remains at MARKER_UNPROCESSED,
                # allowing for retries on the next agent cycle for transient errors.

    async def _execute_command(self, tx: Transaction, command_ints: List[int]):
        """Dispatches a binary command to the appropriate handler."""
        action_code = command_ints[0]
        if action_code == CMD_REPEAT:
            await self._handle_repeat(tx, command_ints)
        elif action_code == CMD_DESIST:
            await self._handle_desist(tx, command_ints)
        else:
            raise ValueError(f"Unknown command action code: {action_code}")

    async def _handle_repeat(self, tx: Transaction, command_ints: List[int]):
        """Handles creating a new repeating task from binary command."""
        # command_ints: [CMD_REPEAT, owner, channel, payload1, payload2, interval_ticks]
        task_data_list = command_ints[1:]  # Extract the 5 task integers
        task_bytes = int_array_to_bytes(task_data_list, byte_width=8)
        new_task_id = await tx.put_object(OT_TASK, 0, task_bytes)
        await tx.create_assoc(src=ID_TASK_ROOT, tar=new_task_id, type=AT_SCHEDULED_TASK)

    async def _handle_desist(self, tx: Transaction, command_ints: List[int]):
        """Handles removing an existing task from binary command."""
        # command_ints: [CMD_DESIST, task_id, 0, 0, 0, 0]
        task_id = command_ints[1]
        await tx.delete_object(OT_TASK, task_id)


# =========================================================================
# Standalone Byte Conversion Utilities
# =========================================================================


def bytes_to_int_array(
    data: bytes,
    byte_width: int,
    byte_order: ByteOrder = "big",
    signed: bool = False,
    output_list: Optional[List[int]] = None,
) -> List[int]:
    """Converts a bytes object into a list of integers."""
    if byte_width <= 0:
        raise ValueError("byte_width must be a positive integer.")
    if byte_order not in ("little", "big"):
        raise ValueError("byte_order must be either 'little' or 'big'.")
    if len(data) % byte_width != 0:
        raise ValueError(
            f"Data length ({len(data)}) is not a multiple of byte width ({byte_width})."
        )

    target_list = output_list if output_list is not None else []
    if output_list is not None:
        target_list.clear()

    for i in range(0, len(data), byte_width):
        target_list.append(
            int.from_bytes(
                data[i : i + byte_width], byteorder=byte_order, signed=signed
            )
        )
    return target_list


def int_array_to_bytes(
    numbers: List[int],
    byte_width: int,
    byte_order: ByteOrder = "big",
    signed: bool = False,
    output_bytearray: Optional[bytearray] = None,
) -> bytes:
    """Converts a list of integers into a bytes object."""
    if byte_width <= 0:
        raise ValueError("byte_width must be a positive integer.")
    if byte_order not in ("little", "big"):
        raise ValueError("byte_order must be either 'little' or 'big'.")

    target_bytearray = output_bytearray if output_bytearray is not None else bytearray()
    if output_bytearray is not None:
        target_bytearray.clear()

    for num in numbers:
        try:
            target_bytearray.extend(
                num.to_bytes(byte_width, byteorder=byte_order, signed=signed)
            )
        except OverflowError:
            raise ValueError(
                f"Number '{num}' cannot be represented in {byte_width} bytes."
            )
    return bytes(target_bytearray)
