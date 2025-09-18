from typing import Dict

# Import the print-based slog utility
import common.slog as slog

class Agent:
    """
    An example agent demonstrating the integration of the print-based slog utility.
    
    shard_config: Dict = {
        "id": 1,
        "host": "b7b4b6da-1ebd-4e4e-8bb0-dcc14640e2c0"
    }
    """
    async def init(self, script_config: Dict, shard_config: Dict):
        # There is no logger object to initialize; we just set the counter.
        self.counter = 0
        
        # Log the initialization event with configuration as context.
        init_context = {
            "script_config": script_config,
            "shard_config": shard_config
        }
        slog.info("Agent initialized.", context=init_context)

    async def work(self):
        # Log the work event with the counter as context.
        slog.info(
            "Agent is performing work.", 
            context={"work_cycle": self.counter}
        )
        self.counter += 1