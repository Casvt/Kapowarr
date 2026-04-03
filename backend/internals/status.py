# -*- coding: utf-8 -*-

"""
General-purpose status tracking framework.
Status type implementations register via decorator and are persisted
to the database across restarts.
"""

from threading import Timer
from time import time
from typing import Any, Callable, Dict, List, Type, Union

from backend.base.definitions import StatusHandler, StatusType
from backend.base.helpers import Singleton
from backend.base.logging import LOGGER
from backend.internals.db import get_db
from backend.internals.server import Server, StatusCountEvent, WebSocket


class StatusHandlers(metaclass=Singleton):
    """Registry and manager for status type handlers.
    Modeled after StartTypeHandlers in server.py.

    Handlers register via the class-level register_handler() decorator
    at import time. All other methods are instance methods accessed via
    StatusHandlers().
    """

    handlers: Dict[StatusType, StatusHandler] = {}

    @classmethod
    def register_handler(
        cls,
        status_type: StatusType
    ) -> Callable[[Type[StatusHandler]], Type[StatusHandler]]:
        """Register a handler for a status type.

        ```
        @StatusHandlers.register_handler(StatusType.CV_RATE_LIMIT)
        class CVRateLimitHandler(StatusHandler):
            ...
        ```

        Args:
            status_type (StatusType): The status type that the handler
                is for.
        """
        def wrapper(
            handler_class: Type[StatusHandler]
        ) -> Type[StatusHandler]:
            cls.handlers[status_type] = handler_class()
            return handler_class
        return wrapper

    def report(self, status_type: StatusType, subtype: str) -> None:
        """Report a status issue.

        Args:
            status_type (StatusType): The type of status issue.
            subtype (str): The subtype identifier
                (e.g. "search_volumes" for CV rate limit).
        """
        handler = self.handlers[status_type]
        timestamp = int(time())

        was_active = handler.problem_reported(subtype)
        handler.report(subtype, timestamp)

        if was_active:
            # Update timestamp in DB but keep existing expires_at
            get_db().execute(
                "UPDATE status SET timestamp = ? "
                "WHERE status_type = ? AND subtype = ?;",
                (timestamp, status_type.value, subtype)
            )
        else:
            # New subtype: get expiry from handler's subtypes
            expires_at = self._get_expires_at(handler, subtype, timestamp)
            get_db().execute(
                "INSERT OR REPLACE INTO status "
                "(status_type, subtype, timestamp, expires_at) "
                "VALUES (?, ?, ?, ?);",
                (status_type.value, subtype, timestamp, expires_at)
            )

        self._emit_count()
        LOGGER.info(
            "Status reported: %s / %s",
            status_type.value, subtype
        )
        return

    def clear(
        self,
        status_type: StatusType,
        subtype: Union[str, None] = None
    ) -> None:
        """Clear a status issue or a specific subtype.

        Args:
            status_type (StatusType): The type of status issue.
            subtype (Union[str, None], optional): The subtype to clear.
                If None, clears all subtypes for this type.
                Defaults to None.
        """
        handler = self.handlers[status_type]

        if not handler.problem_reported(subtype):
            return

        handler.clear(subtype)

        if subtype is not None:
            get_db().execute(
                "DELETE FROM status "
                "WHERE status_type = ? AND subtype = ?;",
                (status_type.value, subtype)
            )
        else:
            get_db().execute(
                "DELETE FROM status WHERE status_type = ?;",
                (status_type.value,)
            )

        self._emit_count()
        return

    def clear_all(self) -> None:
        """Clear all status issues."""
        for status_type, handler in self.handlers.items():
            if handler.problem_reported():
                handler.clear()

        get_db().execute("DELETE FROM status;")
        self._emit_count()
        return

    def problem_reported(
        self,
        status_type: StatusType,
        subtype: Union[str, None] = None
    ) -> bool:
        """Check if a problem is reported for a status type.

        Args:
            status_type (StatusType): The type to check.
            subtype (Union[str, None], optional): The subtype to check.
                If None, checks if any subtype is active.
                Defaults to None.

        Returns:
            bool: Whether a problem is reported.
        """
        handler = self.handlers[status_type]
        return handler.problem_reported(subtype)

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all active statuses with display data from handlers.

        Returns:
            List[Dict[str, Any]]: A list of status entries with display
                data provided by each handler.
        """
        result: List[Dict[str, Any]] = []
        for status_type, handler in self.handlers.items():
            if handler.problem_reported():
                display = handler.get_display()
                display["type"] = status_type.value
                result.append(display)
        return result

    def get_count(self) -> int:
        """Get the total number of active status types.

        Returns:
            int: The count of status types with problems reported.
        """
        return sum(
            1 for handler in self.handlers.values()
            if handler.problem_reported()
        )

    def load_from_db(self) -> None:
        """Load status data from the database on startup.
        Expired entries are deleted. Active entries are restored.
        """
        now = int(time())
        cursor = get_db()

        rows = cursor.execute(
            "SELECT status_type, subtype, timestamp, expires_at "
            "FROM status;"
        ).fetchall()

        for row in rows:
            raw_type, subtype, timestamp, expires_at = row
            status_type = StatusType(raw_type)
            handler = self.handlers[status_type]

            if expires_at is not None and expires_at <= now:
                cursor.execute(
                    "DELETE FROM status "
                    "WHERE status_type = ? AND subtype = ?;",
                    (raw_type, subtype)
                )
                LOGGER.info(
                    "Expired status removed on startup: %s / %s",
                    raw_type, subtype
                )
                continue

            remaining = (expires_at - now) if expires_at is not None else None
            handler.restore(subtype, timestamp, remaining)
            LOGGER.info(
                "Restored status from DB: %s / %s",
                raw_type, subtype
            )

        self._emit_count()
        return

    def _get_expires_at(
        self,
        handler: StatusHandler,
        subtype: str,
        timestamp: int
    ) -> Union[int, None]:
        """Get the expiry timestamp from the handler.

        Args:
            handler (StatusHandler): The handler.
            subtype (str): The subtype.
            timestamp (int): The report timestamp.

        Returns:
            Union[int, None]: The expiry timestamp or None.
        """
        return handler.get_expiry(subtype, timestamp)

    def _emit_count(self) -> None:
        """Emit a WebSocket event with the current status count."""
        count = self.get_count()
        WebSocket().emit(StatusCountEvent(count=count))
        return


# region Status Handler Implementations
@StatusHandlers.register_handler(StatusType.CV_RATE_LIMIT)
class CVRateLimitHandler(StatusHandler):
    """Handler for ComicVine API rate limit status.

    ComicVine uses a rolling 200-request-per-resource-per-hour window,
    but the API provides no headers or fields indicating remaining
    requests or reset timing. Entries expire after one hour from the
    first rejection. The timer does not reset on subsequent rejections.
    """

    description = "ComicVine rate limit"
    EXPIRY_SECONDS = 3600

    def __init__(self) -> None:
        self._subtypes: Dict[str, int] = {}
        self._timers: Dict[str, Timer] = {}
        return

    def get_expiry(self, subtype: str, timestamp: int) -> int:
        """Get the expiry timestamp for a subtype.

        Args:
            subtype (str): The subtype.
            timestamp (int): The report timestamp.

        Returns:
            int: The absolute expiry timestamp.
        """
        return timestamp + self.EXPIRY_SECONDS

    def report(self, subtype: str, timestamp: int) -> None:
        if subtype in self._subtypes:
            self._subtypes[subtype] = timestamp
            return

        self._subtypes[subtype] = timestamp
        self._schedule_timer(subtype, self.EXPIRY_SECONDS)
        return

    def restore(
        self, subtype: str, timestamp: int,
        remaining: Union[int, None]
    ) -> None:
        """Restore a subtype from database on startup.

        Args:
            subtype (str): The subtype.
            timestamp (int): The stored timestamp.
            remaining (Union[int, None]): Seconds until expiry, or None.
        """
        self._subtypes[subtype] = timestamp
        if remaining is not None:
            self._schedule_timer(subtype, remaining)
        return

    def clear(self, subtype: Union[str, None] = None) -> None:
        if subtype is not None:
            self._subtypes.pop(subtype, None)
            self._cancel_timer(subtype)
        else:
            self._subtypes.clear()
            for key in list(self._timers):
                self._cancel_timer(key)
        return

    def problem_reported(
        self, subtype: Union[str, None] = None
    ) -> bool:
        if subtype is not None:
            return subtype in self._subtypes
        return len(self._subtypes) > 0

    def get_subtypes(self) -> Dict[str, int]:
        return self._subtypes.copy()

    def get_display(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "subtypes": list(self._subtypes.keys())
        }

    def _schedule_timer(self, subtype: str, seconds: int) -> None:
        """Schedule an expiry timer for a subtype.

        Args:
            subtype (str): The subtype.
            seconds (int): Seconds until expiry.
        """
        if subtype in self._timers:
            return

        timer = Server().get_db_timer_thread(
            interval=seconds,
            target=self._on_expiry,
            name=f"StatusExpiry.{StatusType.CV_RATE_LIMIT.value}.{subtype}",
            args=(subtype,)
        )
        timer.daemon = True
        timer.start()
        self._timers[subtype] = timer
        return

    def _cancel_timer(self, subtype: str) -> None:
        """Cancel an expiry timer.

        Args:
            subtype (str): The subtype.
        """
        timer = self._timers.pop(subtype, None)
        if timer is not None:
            timer.cancel()
        return

    def _on_expiry(self, subtype: str) -> None:
        """Called when a timer fires.

        Args:
            subtype (str): The subtype that expired.
        """
        self._timers.pop(subtype, None)
        StatusHandlers().clear(StatusType.CV_RATE_LIMIT, subtype)
        return
