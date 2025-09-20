from typing import Dict
import time

# Import the custom libraries
import common.http as http
import common.slog as slog

class Agent:
    """
    An agent that periodically performs an HTTP GET request to a specified URL
    and reports the status and latency using the print-based slog utility.
    """
    async def init(self, script_config: Dict, shard_config: Dict, dbro):
        """
        Initializes the agent with the target URL and request settings.
        """
        # Retrieve the URL from the script_config, raising an error if not provided.
        self.target_url = script_config.get("url")
        if not self.target_url:
            slog.error(
                "Initialization failed: 'url' key missing from script_config.",
                context={"script_config": script_config}
            )
            raise ValueError("The 'url' key must be present in script_config.")

        # Retrieve the timeout or use a default of 10 seconds.
        timeout = script_config.get("timeout", 10)

        # Initialize an HTTP session to manage connection settings.
        self.http_session = http.Session(timeout=timeout)
        self.work_counter = 0
        
        init_context = {
            "target_url": self.target_url,
            "timeout_seconds": timeout,
            "shard_config": shard_config
        }
        slog.info("Agent initialized successfully.", context=init_context)

    async def work(self, dbrw):
        """
        Executes a single work cycle: performs a GET request and logs the result.
        """
        slog.info(
            "Starting health check.",
            context={"work_cycle": self.work_counter, "url": self.target_url}
        )
        
        start_ns = time.monotonic_ns()
        try:
            # Perform the GET request using the configured session.
            response = self.http_session.get(self.target_url)
            
            # Check for HTTP errors (e.g., 404 Not Found, 500 Server Error).
            response.raise_for_status()

            latency_ns = time.monotonic_ns() - start_ns
            
            success_context = {
                "url": self.target_url,
                "status_code": response.status_code,
                "latency_ms": round(latency_ns / 1_000_000, 2)
            }
            slog.info("Health check successful.", context=success_context)

        except http.HTTPError as e:
            latency_ns = time.monotonic_ns() - start_ns
            error_context = {
                "url": self.target_url,
                "status_code": e.response.status_code,
                "reason": e.response.reason,
                "latency_ms": round(latency_ns / 1_000_000, 2)
            }
            slog.error("Health check failed with HTTP error.", context=error_context)

        except http.RequestException as e:
            latency_ns = time.monotonic_ns() - start_ns
            error_context = {
                "url": self.target_url,
                "error_type": type(e).__name__,
                "latency_ms": round(latency_ns / 1_000_000, 2)
            }
            slog.error(
                "Health check failed with a request exception.",
                exc_info=True,
                context=error_context
            )
        
        finally:
            self.work_counter += 1