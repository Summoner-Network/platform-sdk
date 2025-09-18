from typing import Dict
import common.slog as slog

class Agent:
    """
    shard_config: Dict = {
        "id": 1,
        "host": "b7b4b6da-1ebd-4e4e-8bb0-dcc14640e2c0"
    }
    """
    async def init(self, script_config: Dict, shard_config: Dict):
        # There is no logger object to initialize.
        
        # Log the initialization event with configuration data in the context.
        init_context = {
            "script_config": script_config,
            "shard_config": shard_config
        }
        slog.info("Agent initialized.", context=init_context)

    async def work(self):
        # Log the work event.
        slog.info("Agent is performing work.")