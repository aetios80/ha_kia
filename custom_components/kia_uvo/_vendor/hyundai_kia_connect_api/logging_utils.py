"""Small logging helpers that never serialize vendor payloads."""

import logging


class SafeDebugLogger:
    """Logger facade that drops unsafe legacy DEBUG interpolation arguments."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, *_args, **_kwargs) -> None:
        self._logger.debug("Kia Connect EU debug event")

    def debug_event(self, event: str, *, status: int | None = None) -> None:
        if status is None:
            self._logger.debug("Kia Connect EU event=%s", event)
        else:
            self._logger.debug("Kia Connect EU event=%s status=%s", event, status)

    def error(self, *_args, **_kwargs) -> None:
        self._logger.error("Kia Connect EU error")

    def exception(self, *_args, **_kwargs) -> None:
        self._logger.error("Kia Connect EU exception")

    def __getattr__(self, name: str):
        return getattr(self._logger, name)


def debug_event(logger: logging.Logger | SafeDebugLogger, event: str, *, status: int | None = None) -> None:
    """Log operational metadata without request, response, or identifier data."""
    if isinstance(logger, SafeDebugLogger):
        logger.debug_event(event, status=status)
    elif status is None:
        logger.debug("Kia Connect EU event=%s", event)
    else:
        logger.debug("Kia Connect EU event=%s status=%s", event, status)
