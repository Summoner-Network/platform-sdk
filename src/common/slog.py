# slog.py
# A simple, structured JSON logger that uses the built-in print() function.

import json
import sys
import os
import traceback
from datetime import datetime, timezone

def _log(level: str, message: str, context: dict, exc_info: bool):
    """Internal log function that constructs and prints the JSON log."""
    
    # --- Get Caller Information ---
    # We go 2 frames up the stack to get the original caller's info
    # (Frame 0: _log, Frame 1: info/warn/error, Frame 2: user's code)
    frame = sys._getframe(2)
    
    # --- Build the Log Object ---
    log_obj = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "source": {
            "filename": os.path.basename(frame.f_code.co_filename),
            "line": frame.f_lineno,
            "function": frame.f_code.co_name,
        },
        "context": context if context is not None else {},
    }

    # --- Add Exception Info if Requested ---
    if exc_info:
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type:
            traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            log_obj["context"]["exception"] = {
                "type": exc_type.__name__,
                "message": str(exc_value),
                "traceback": traceback_str,
            }

    # --- Print to the Correct Stream ---
    # INFO/DEBUG go to stdout, WARN/ERROR go to stderr.
    output_stream = sys.stderr if level in ("WARN", "ERROR") else sys.stdout
    
    try:
        print(json.dumps(log_obj), file=output_stream, flush=True)
    except TypeError:
        # Fallback for objects that can't be JSON serialized
        log_obj["context"] = {"__unserializable_data__": str(context)}
        print(json.dumps(log_obj), file=output_stream, flush=True)


def info(message: str, context: dict = None):
    """Logs a message with INFO level."""
    _log("INFO", message, context, exc_info=False)

def warn(message: str, context: dict = None):
    """Logs a message with WARN level."""
    _log("WARN", message, context, exc_info=False)

def error(message: str, context: dict = None, exc_info: bool = False):
    """Logs a message with ERROR level. Set exc_info=True inside an except block."""
    _log("ERROR", message, context, exc_info=exc_info)

# --- Example Usage ---
if __name__ == "__main__":
    
    def process_user(user_id):
        info("Starting to process user.", context={"user_id": user_id})
        
        if user_id == "usr_bad":
            warn("User has a bad reputation.", context={"user_id": user_id, "rep_score": -5})
        
        try:
            result = 100 / (len(user_id) - 7) # This will cause a ZeroDivisionError for 'usr_bad'
        except ZeroDivisionError:
            error("Failed to calculate user score.", context={"user_id": user_id}, exc_info=True)
            return

        info("Finished processing user.", context={"user_id": user_id, "result": result})

    print("--- Running example functions ---")
    process_user("usr_good_123")
    print("\n--- Running with a user that will cause an error ---")
    process_user("usr_bad")