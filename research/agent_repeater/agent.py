import asyncio
import datetime
from typing import Dict, List, Any, TypedDict, Optional
import common.slog as slog

# === Configuration and Constants ===

DEFAULT_CONCURRENCY_LIMIT = 10

# Object Types
OT_TASK = 1
OT_CLOCK = 2
OT_PROCESSED_COMMAND = 3

# Association Types
AT_SCHEDULED_TASK = "scheduled_task"

# Fixed Object IDs
ID_TASK_ROOT = 0
ID_GLOBAL_CLOCK = 1

# === Data Structures (TypedDicts) ===
# Using TypedDicts clarifies the expected shape of data objects.

class TaskDefinition(TypedDict):
    """The structure of a scheduled task object."""
    owner: int
    channel: str
    payload: Dict[str, Any]
    interval_ticks: int

class ClockState(TypedDict):
    """The structure of the global clock."""
    time: int

# Type aliases for host interactions
HostAPI = Any
Transaction = Any
CommandBlock = Dict[str, Any]


class SchedulerAgent:
    """
    A persistent, command-driven scheduler agent.

    It operates in a sharded environment, ensuring tasks are executed on time.
    Command processing is strictly transactional and idempotent.
    """

    async def head(self, script_config: Dict, shard_config: Dict, host: HostAPI):
        """Initializes the agent, setting up sharding and concurrency controls."""
        self.host = host
        self.shard_id: int = shard_config.id
        self.shard_count: int = shard_config.count

        # Determine the concurrency limit for parallel I/O operations
        concurrency_limit = script_config.system.core.concurrency_limit

        # Semaphore restricts the number of concurrent I/O operations.
        self.semaphore = asyncio.Semaphore(concurrency_limit)

        slog.info(
            "Scheduler agent initialized.",
            context={
                "shard_id": self.shard_id,
                "concurrency_limit": concurrency_limit
            },
        )

    # =========================================================================
    # Main Work Loop
    # =========================================================================

    async def tail(self):
        """
        The main execution cycle of the agent.
        """
        # 1. Advance the Global Clock
        current_tick = await self._advance_clock()

        if current_tick is None:
            # If the clock cannot be advanced reliably, we must halt the cycle
            # to prevent incorrect task execution based on stale time.
            slog.error("Halting work cycle due to failure in advancing the clock.")
            return

        # 2. Dispatch concurrent processing for Tasks and Commands
        # We dispatch both phases concurrently to maximize throughput.
        task_jobs = await self._dispatch_task_processing(current_tick)
        command_jobs = await self._dispatch_command_processing()

        # 3. Wait for all concurrent operations to complete
        all_jobs = task_jobs + command_jobs
        if all_jobs:
            # Errors are handled within the individual jobs.
            await asyncio.gather(*all_jobs)

        slog.info(
            "Agent work cycle complete.",
            context={"tick_count": current_tick, "shard_id": self.shard_id},
        )

    # =========================================================================
    # Clock Management
    # =========================================================================

    async def _advance_clock(self) -> Optional[int]:
        """Advances the global clock by one tick. Returns the new tick count or None on failure."""
        # Note: This implements a read-modify-write. If the host supports atomic increments,
        # that would be preferable.
        try:
            try:
                # Attempt to fetch the existing clock.
                clock: ClockState = await self.host.get_object(OT_CLOCK, ID_GLOBAL_CLOCK)
                new_tick_count = clock.time + 1
            except Exception:
                # Clock likely doesn't exist yet (e.g., first run).
                slog.warn("Clock object not found, initializing to 1.")
                new_tick_count = 1
            
            clock.time = new_tick_count
            # Persist the new clock value.
            await self.host.put_object(clock)
            return new_tick_count
        except Exception as e:
            slog.error("Critical error while updating the clock.", context={"error": str(e)})
            return None

    # =========================================================================
    # Task Processing
    # =========================================================================

    async def _dispatch_task_processing(self, current_tick: int) -> List[asyncio.Task]:
        """Streams scheduled tasks assigned to this shard and dispatches concurrent workers."""
        jobs: List[asyncio.Task] = []
        # Stream associations from the root task ID, filtered for this shard.
        task_stream = self.host.stream_assocs(
            type=AT_SCHEDULED_TASK,
            src=ID_TASK_ROOT,
            shards=self.shard_count,
            shard_id=self.shard_id,
        )

        async for association in task_stream:
            task_id = association["target_id"]
            # Create an asyncio Task for concurrent execution.
            job = asyncio.create_task(
                self._process_scheduled_task(task_id, current_tick)
            )
            jobs.append(job)
        return jobs

    async def _process_scheduled_task(self, task_id: int, current_tick: int):
        """Worker coroutine: Checks if a task is due and executes it."""

        # Wait if concurrency limit is reached.
        async with self.semaphore:
            try:
                # Fetch the task definition.
                task: TaskDefinition = await self.host.get_object(OT_TASK, task_id)

                # Check if the task is due based on its interval.
                if current_tick % task.interval_ticks == 0:
                    slog.info(
                        "Executing scheduled task.",
                        context={"task_id": task_id, "tick": current_tick},
                    )
                    # Execute the task (e.g., send a message).
                    await self.host.push_message(
                        task["owner"], task["channel"], task["payload"]
                    )

            except Exception as e:
                # Catch errors to ensure the failure of one task does not stop the agent.
                slog.error(
                    "Failed to process a scheduled task.",
                    context={"task_id": task_id, "error": str(e)},
                )

    # =========================================================================
    # Command Processing (Transactional and Idempotent)
    # =========================================================================

    async def _dispatch_command_processing(self) -> List[asyncio.Task]:
        """Streams incoming command blocks and dispatches concurrent workers."""
        jobs: List[asyncio.Task] = []
        command_stream = self.host.stream_blocks("commands")

        async for block in command_stream:
            # Create an asyncio Task for concurrent execution.
            job = asyncio.create_task(self._process_command_block(block))
            jobs.append(job)
        return jobs

    async def _process_command_block(self, block: CommandBlock):
        """
        Worker coroutine: Processes a command block atomically and idempotently.
        """
        command_id = block.get("id")
        if not command_id:
            slog.error("Command block missing ID. Discarding.", context={"block": block})
            await block.forget()
            return

        # Wait if concurrency limit is reached.
        async with self.semaphore:
            # 1. Idempotency Check
            if await self.host.object_exists(OT_PROCESSED_COMMAND, command_id):
                slog.info(
                    "Skipping already processed command block (idempotency check).",
                    context={"command_id": command_id},
                )
                await block.forget()
                return

            # 2. Transactional Processing (Atomicity)
            tx = self.host.rwtx()
            try:
                # Process individual commands within the block
                for command in block.get("commands", []):
                    await self._execute_command(tx, command)

                # 3. Finalization
                # These steps MUST occur within the same transaction as the command execution.

                # Mark the command block as processed (for idempotency).
                await tx.put_object(
                    OT_PROCESSED_COMMAND,
                    command_id,
                    {"processed_at": int(datetime.datetime.now().timestamp())},
                )
                # Acknowledge and remove the block from the stream.
                await tx.forget(block)

                # Commit the transaction. All changes apply atomically.
                await tx.commit()
                slog.info(
                    "Successfully committed command block.",
                    context={"command_id": command_id},
                )

            except Exception as e:
                # 4. Rollback on Failure
                # If any error occurs (including validation errors), rollback the entire transaction.
                await tx.rollback()
                slog.error(
                    "Failed to process command block. Transaction rolled back.",
                    context={"command_id": command_id, "error": str(e)},
                )
                # The block is not forgotten, allowing for retry if the error is transient.

    # === Command Handlers ===

    async def _execute_command(self, tx: Transaction, command: Dict[str, Any]):
        """Dispatches the command to the appropriate handler."""
        action = command.get("action")

        if action == "repeat":
            await self._handle_repeat(tx, command)
        elif action == "desist":
            await self._handle_desist(tx, command)
        else:
            # Raise an error to force transaction rollback for unknown commands.
            raise ValueError(f"Unknown command action received: {action}")

    async def _handle_repeat(self, tx: Transaction, command: Dict[str, Any]):
        """Handles the creation of a new repeating task."""
        # Validation: Ensure required fields exist before proceeding.
        required_fields = ["owner", "channel", "payload", "interval_ticks"]
        if not all(field in command for field in required_fields):
             # Raising an error triggers the transaction rollback.
             raise ValueError(f"Missing required fields in 'repeat' command: {command}")

        new_task: TaskDefinition = {
            "owner": command["owner"],
            "channel": command["channel"],
            "payload": command["payload"],
            "interval_ticks": command["interval_ticks"],
        }
        # Create the new task object (ID 0 usually means auto-assign ID).
        new_task_id = await tx.put_object(OT_TASK, 0, new_task)
        # Associate it with the root task list.
        await tx.create_assoc(
            src=ID_TASK_ROOT, tar=new_task_id, type=AT_SCHEDULED_TASK
        )

    async def _handle_desist(self, tx: Transaction, command: Dict[str, Any]):
        """Handles the removal of an existing task."""
        task_id = command.get("task_id")
        if not task_id:
            raise ValueError(f"Missing 'task_id' in 'desist' command: {command}")

        # Delete the task object itself.
        # The associations touching it are auto-deleted.
        await tx.delete_object(OT_TASK, task_id)