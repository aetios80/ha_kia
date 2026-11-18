"""Rate limit for full password logins (one per window, then reauth).

Why: when the token refresh fails, refresh_access_token falls back to a full
password login. With a 10-minute poll that was one full login every 10
minutes against Kia's identity provider, for as long as the cause persisted.

Rules enforced here:
- at most ONE full login attempt per LOGIN_WINDOW_SECONDS; attempts are
  counted, not only successes, and the check runs before any network call;
- after LOGIN_FAILURE_LIMIT consecutive rejected logins the guard demands a
  manual reauthentication (AuthenticationError) and nothing is sent anymore;
- the state is two numbers and nothing else, so the owner (the Home Assistant
  coordinator) can persist it next to, but separate from, the token. No
  account data, credential or token is ever stored in it.

The library does not depend on Home Assistant: the owner creates the guard
from its stored dict, hands it to the VehicleManager and persists to_dict()
whenever `dirty` is set, also when the login raised.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Any

from .exceptions import AuthenticationError, LoginThrottledError

LOGIN_WINDOW_SECONDS: int = 6 * 3600
LOGIN_FAILURE_LIMIT: int = 2


class LoginGuard:
    """Window and consecutive-failure state for full logins."""

    def __init__(
        self,
        last_attempt_at: float = 0.0,
        failures: int = 0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self.last_attempt_at: float = float(last_attempt_at)
        self.failures: int = int(failures)
        # True when the state changed since the owner last persisted it.
        self.dirty: bool = False

    @classmethod
    def from_dict(
        cls, data: Any, clock: Callable[[], float] = time.time
    ) -> "LoginGuard":
        """Rebuild from persisted data, distrusting every field.

        Wrong types fall back to the empty state; a timestamp in the future
        (clock change, corrupted entry) is brought back to now.
        """
        guard = cls(clock=clock)
        if not isinstance(data, dict):
            return guard
        last = data.get("last_attempt_at")
        if (
            isinstance(last, (int, float))
            and not isinstance(last, bool)
            and math.isfinite(last)
            and last > 0
        ):
            now = clock()
            if last > now:
                last = now
                guard.dirty = True
            guard.last_attempt_at = float(last)
        failures = data.get("failures")
        if isinstance(failures, int) and not isinstance(failures, bool):
            guard.failures = max(0, min(failures, LOGIN_FAILURE_LIMIT))
        return guard

    def to_dict(self) -> dict[str, float | int]:
        return {"last_attempt_at": self.last_attempt_at, "failures": self.failures}

    def remaining_seconds(self) -> float:
        """Seconds until the next full login is allowed (0 when allowed)."""
        if self.last_attempt_at <= 0:
            return 0.0
        return max(0.0, self.last_attempt_at + LOGIN_WINDOW_SECONDS - self._clock())

    def next_allowed_at(self) -> float:
        """Epoch seconds of the next allowed attempt."""
        return self.last_attempt_at + LOGIN_WINDOW_SECONDS

    def begin_attempt(self) -> None:
        """Gate and count one full login attempt, before any network call.

        Raises AuthenticationError when the failure limit is reached (the
        owner must start a reauthentication) and LoginThrottledError, which
        is deliberately not an AuthenticationError, while the window is still
        closed.
        """
        with self._lock:
            if self.failures >= LOGIN_FAILURE_LIMIT:
                raise AuthenticationError(
                    "Repeated full-login failures: reauthentication required"
                )
            remaining = self.remaining_seconds()
            if remaining > 0:
                raise LoginThrottledError(
                    "Full login limited to one per 6 hours", retry_after=remaining
                )
            self.last_attempt_at = self._clock()
            self.dirty = True

    def record_success(self) -> None:
        with self._lock:
            if self.failures:
                self.failures = 0
                self.dirty = True

    def record_rejection(self) -> int:
        """Count one consecutive rejected login; returns the new count."""
        with self._lock:
            self.failures = min(self.failures + 1, LOGIN_FAILURE_LIMIT)
            self.dirty = True
            return self.failures
