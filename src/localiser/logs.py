"""Key=value logging through the standard library."""
import logging

logger = logging.getLogger("localiser")
# A library must not configure logging; host stubs attach handlers.
logger.addHandler(logging.NullHandler())


def log_event(level: int, event: str, **fields) -> None:
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    logger.log(level, "event=%s %s", event, details)
