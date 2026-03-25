# -*- coding: utf-8 -*-

"""
General-purpose status tracking framework.
Status type implementations register via decorator and are persisted
to the database across restarts.
"""

from threading import Lock, Timer
from time import time
from typing import Any, Callable, Dict, List, Tuple, Union

from backend.base.definitions import StatusHandler, StatusType
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class StatusHandlers:
    """Registry and manager for status type handlers.
    Modeled after StartTypeHandlers in server.py.
    """

    handlers: Dict[StatusType, StatusHandler] = {}
    _active: Dict[StatusType, Dict[str, Tuple[float, Union[float, None]]]] = {}
    """In-memory state: {type: {subtype: (timestamp, expires_at)}}"""
    _timers: Dict[str, Timer] = {}
    """Expiry timers keyed by 'type.subtype'"""
    _lock = Lock()

    @classmethod
    def register_handler(
        cls,
        status_type: StatusType
    ) -> Callable[
        ['type[StatusHandler]'], 'type[StatusHandler]'
    ]:
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
            handler_class: 'type[StatusHandler]'
        ) -> 'type[StatusHandler]':
            cls.handlers[status_type] = handler_class()
            return handler_class
        return wrapper

    @classmethod
    def report(cls, status_type: StatusType, subtype: str) -> None:
        """Report a status issue.

        Args:
            status_type (StatusType): The type of status issue.
            subtype (str): The subtype identifier
                (e.g. "search_volumes" for CV rate limit).
        """
        handler = cls.handlers.get(status_type)
        if handler is None:
            return

        timestamp = time()
        timer_key = f"{status_type.value}.{subtype}"

        with cls._lock:
            type_statuses = cls._active.setdefault(status_type, {})
            existing = type_statuses.get(subtype)

            if existing is not None:
                # Subtype already active: update timestamp, keep expires_at
                type_statuses[subtype] = (timestamp, existing[1])
                cls._save_to_db(status_type, subtype,
                                timestamp, existing[1])
            else:
                # New subtype
                expires_at = handler.get_expiry(subtype, timestamp)
                type_statuses[subtype] = (timestamp, expires_at)
                cls._save_to_db(status_type, subtype,
                                timestamp, expires_at)
                cls._schedule_expiry(
                    status_type, subtype, expires_at, timer_key
                )

        handler.on_report(subtype)
        cls._emit_count()

        LOGGER.info(
            "Status reported: %s / %s",
            status_type.value, subtype
        )
        return

    @classmethod
    def clear(
        cls,
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
        handler = cls.handlers.get(status_type)

        with cls._lock:
            type_statuses = cls._active.get(status_type)
            if type_statuses is None:
                return

            if subtype is not None:
                if subtype not in type_statuses:
                    return
                del type_statuses[subtype]
                cls._delete_from_db(status_type, subtype)
                cls._cancel_timer(f"{status_type.value}.{subtype}")

                if not type_statuses:
                    del cls._active[status_type]
                    fully_cleared = True
                else:
                    fully_cleared = False
            else:
                # Clear all subtypes
                for st in list(type_statuses):
                    cls._cancel_timer(f"{status_type.value}.{st}")
                    cls._delete_from_db(status_type, st)
                del cls._active[status_type]
                fully_cleared = True

        if fully_cleared and handler is not None:
            handler.on_clear()

        cls._emit_count()

        LOGGER.info(
            "Status cleared: %s%s",
            status_type.value,
            f" / {subtype}" if subtype else " (all)"
        )
        return

    @classmethod
    def clear_all(cls) -> None:
        """Clear all status issues."""
        with cls._lock:
            for status_type in list(cls._active):
                for st in list(cls._active.get(status_type, {})):
                    cls._cancel_timer(f"{status_type.value}.{st}")
                    cls._delete_from_db(status_type, st)

                handler = cls.handlers.get(status_type)
                if handler is not None:
                    handler.on_clear()

            cls._active.clear()

        cls._emit_count()
        LOGGER.info("All statuses cleared")
        return

    @classmethod
    def is_active(
        cls,
        status_type: StatusType,
        subtype: Union[str, None] = None
    ) -> bool:
        """Check if a status type (or specific subtype) is currently active.

        Args:
            status_type (StatusType): The type to check.
            subtype (Union[str, None], optional): The subtype to check.
                If None, checks if any subtype is active.
                Defaults to None.

        Returns:
            bool: Whether the status is active.
        """
        with cls._lock:
            type_statuses = cls._active.get(status_type)
            if type_statuses is None:
                return False
            if subtype is not None:
                return subtype in type_statuses
            return True

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        """Get all active statuses with display data from handlers.

        Returns:
            List[Dict[str, Any]]: A list of status entries with display
                data provided by each handler.
        """
        result: List[Dict[str, Any]] = []
        with cls._lock:
            for status_type, subtypes in cls._active.items():
                handler = cls.handlers.get(status_type)
                if handler is None:
                    continue
                display = handler.get_display(subtypes.copy())
                display["type"] = status_type.value
                result.append(display)
        return result

    @classmethod
    def get_count(cls) -> int:
        """Get the total number of active status types.

        Returns:
            int: The count of active status types (not subtypes).
        """
        with cls._lock:
            return len(cls._active)

    @classmethod
    def load_from_db(cls) -> None:
        """Load status data from the database on startup.
        Expired entries are deleted. Active entries are restored
        with timers for remaining time.
        """
        now = time()
        cursor = get_db()

        rows = cursor.execute(
            "SELECT status_type, subtype, timestamp, expires_at "
            "FROM status;"
        ).fetchall()

        for row in rows:
            raw_type, subtype, timestamp, expires_at = row

            # Find the matching StatusType enum
            try:
                status_type = StatusType(raw_type)
            except ValueError:
                # Unknown status type, remove from DB
                cursor.execute(
                    "DELETE FROM status "
                    "WHERE status_type = ? AND subtype = ?;",
                    (raw_type, subtype)
                )
                continue

            if status_type not in cls.handlers:
                continue

            # Check expiry
            if expires_at is not None and expires_at <= now:
                # Expired while offline, remove
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

            # Restore active entry
            with cls._lock:
                type_statuses = cls._active.setdefault(status_type, {})
                type_statuses[subtype] = (timestamp, expires_at)

                timer_key = f"{status_type.value}.{subtype}"
                cls._schedule_expiry(
                    status_type, subtype, expires_at, timer_key
                )

            handler = cls.handlers[status_type]
            handler.on_report(subtype)

            LOGGER.info(
                "Restored status from DB: %s / %s",
                raw_type, subtype
            )

        cls._emit_count()
        return

    @classmethod
    def _schedule_expiry(
        cls,
        status_type: StatusType,
        subtype: str,
        expires_at: Union[float, None],
        timer_key: str
    ) -> None:
        """Schedule an expiry timer. Must be called while holding _lock.

        Args:
            status_type (StatusType): The status type.
            subtype (str): The subtype.
            expires_at (Union[float, None]): When to expire.
                None means no auto-expiry.
            timer_key (str): The key for the timer dict.
        """
        if expires_at is None:
            return

        if timer_key in cls._timers:
            return

        remaining = max(expires_at - time(), 0.001)

        from backend.internals.server import Server
        timer = Server().get_db_timer_thread(
            interval=remaining,
            target=cls._on_expiry,
            name=f"StatusExpiry.{timer_key}",
            args=(status_type, subtype)
        )
        timer.daemon = True
        timer.start()
        cls._timers[timer_key] = timer
        return

    @classmethod
    def _on_expiry(cls, status_type: StatusType, subtype: str) -> None:
        """Called by an expiry timer.

        Args:
            status_type (StatusType): The status type that expired.
            subtype (str): The subtype that expired.
        """
        timer_key = f"{status_type.value}.{subtype}"
        with cls._lock:
            cls._timers.pop(timer_key, None)
        cls.clear(status_type, subtype)
        return

    @classmethod
    def _cancel_timer(cls, timer_key: str) -> None:
        """Cancel an expiry timer. Must be called while holding _lock.

        Args:
            timer_key (str): The key for the timer dict.
        """
        timer = cls._timers.pop(timer_key, None)
        if timer is not None:
            timer.cancel()
        return

    @classmethod
    def _save_to_db(
        cls,
        status_type: StatusType,
        subtype: str,
        timestamp: float,
        expires_at: Union[float, None]
    ) -> None:
        """Save or update a status entry in the database.
        Must be called while holding _lock.

        Args:
            status_type (StatusType): The status type.
            subtype (str): The subtype.
            timestamp (float): When the status was reported.
            expires_at (Union[float, None]): When it expires, or None.
        """
        get_db().execute(
            "INSERT OR REPLACE INTO status "
            "(status_type, subtype, timestamp, expires_at) "
            "VALUES (?, ?, ?, ?);",
            (status_type.value, subtype, timestamp, expires_at)
        )
        return

    @classmethod
    def _delete_from_db(
        cls,
        status_type: StatusType,
        subtype: str
    ) -> None:
        """Delete a status entry from the database.
        Must be called while holding _lock.

        Args:
            status_type (StatusType): The status type.
            subtype (str): The subtype.
        """
        get_db().execute(
            "DELETE FROM status "
            "WHERE status_type = ? AND subtype = ?;",
            (status_type.value, subtype)
        )
        return

    @classmethod
    def _emit_count(cls) -> None:
        """Emit a WebSocket event with the current status count."""
        from backend.internals.server import StatusCountEvent, WebSocket
        count = cls.get_count()
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

    _subtype_labels: Dict[str, str] = {
        "search_volumes": "Searching volumes",
        "fetch_volume": "Fetching volume metadata",
        "fetch_issues": "Fetching issue metadata"
    }

    def get_expiry(
        self, subtype: str, timestamp: float
    ) -> Union[float, None]:
        return timestamp + 3600

    def on_report(self, subtype: str) -> None:
        return

    def on_clear(self) -> None:
        return

    def get_display(
        self,
        subtypes: Dict[str, Tuple[float, Union[float, None]]]
    ) -> Dict[str, Any]:
        return {
            "source": "ComicVine",
            "description": self.description,
            "subtypes": [
                {
                    "name": st,
                    "label": self._subtype_labels.get(st, st),
                    "since": data[0],
                    "expires_at": data[1]
                }
                for st, data in subtypes.items()
            ]
        }
