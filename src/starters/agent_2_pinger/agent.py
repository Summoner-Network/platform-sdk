# src/starters/agent_2_pinger/agent.py

from typing import Dict
import time
import common.slog as slog
import pyodide.http


class Agent:
    """
    An agent that periodically performs an HTTP GET request to a specified URL
    and reports the status and latency using the print-based slog utility.
    """

    async def head(self, script_config, shard_config, dbro):
        """
        Initializes the agent with the target URL and request settings.
        """
        self.target_url = shard_config.url
        if not self.target_url:
            slog.error(
                "Initialization failed: 'url' key missing from shard_config.",
                context=shard_config.to_py(),
            )
            raise ValueError("The 'url' key must be present in shard_config.")

        # The timeout is now an argument to pyfetch, so we just store it.
        self.timeout_seconds = shard_config.timeout
        self.work_counter = 0

        init_context = {
            "target_url": self.target_url,
            "timeout_seconds": self.timeout_seconds,
            "shard_config": shard_config.to_py(),
        }
        slog.info("Agent initialized successfully.", context=init_context)

    async def tail(self, dbrw):
        """
        Executes a single work cycle: performs a GET request and logs the result.
        """
        slog.info(
            "Starting health check.",
            context={"work_cycle": self.work_counter, "url": self.target_url},
        )

        start_ns = time.monotonic_ns()
        try:
            response = await pyodide.http.pyfetch(
                self.target_url,
                timeout=self.timeout_seconds * 1000,  # pyfetch timeout is in ms
            )
            response.raise_for_status()
            latency_ns = time.monotonic_ns() - start_ns

            success_context = {
                "url": self.target_url,
                "status_code": response.status,
                "latency_ms": round(latency_ns / 1_000_000, 2),
            }
            slog.info("Health check successful.", context=success_context)

        except Exception as e:
            latency_ns = time.monotonic_ns() - start_ns

            # ✅ THE FIX: Build the context safely.
            error_context = {
                "url": self.target_url,
                "latency_ms": round(latency_ns / 1_000_000, 2),
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

            # Check if the exception has HTTP response details before accessing them.
            if hasattr(e, "response") and e.response:
                error_context["status_code"] = e.response.status
                error_context["reason"] = e.response.status_text
            else:
                # This case now handles AbortError, timeouts, DNS failures, etc.
                error_context["status_code"] = None
                error_context["reason"] = "Request failed before receiving a response."

            slog.error(
                "Health check failed with an exception.",
                exc_info=True,
                context=error_context,
            )

        finally:
            self.work_counter += 1
