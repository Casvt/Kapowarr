# -*- coding: utf-8 -*-

"""
Notification system: event dataclasses, provider ABC, and dispatch service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Tuple, Type, Union

from backend.base.helpers import Singleton
from backend.base.logging import LOGGER


def get_application_url() -> str:
    """Return the base URL of this Kapowarr instance."""
    try:
        from backend.internals.settings import Settings
        sv = Settings().sv
        host = sv.host if sv.host != '0.0.0.0' else 'localhost'
        url_base = sv.url_base.rstrip('/')
        return f'http://{host}:{sv.port}{url_base}'
    except Exception:
        return 'http://localhost:5656'


# region Event dataclasses

@dataclass
class DownloadEvent:
    volume_id: int
    volume_title: str
    volume_year: int
    volume_comicvine_id: int
    volume_path: str
    issue_id: Union[int, None]
    issue_comicvine_id: Union[int, None]
    issue_number: str
    issue_title: str
    file_path: str
    download_source: str
    is_upgrade: bool


@dataclass
class VolumeAddEvent:
    volume_id: int
    volume_title: str
    volume_year: int
    volume_comicvine_id: int
    volume_path: str
    publisher: str


@dataclass
class ApplicationUpdateEvent:
    previous_version: str
    new_version: str
    message: str


@dataclass
class TestEvent:
    pass


# region Event formatters

def format_download_notification(
    event: DownloadEvent
) -> Tuple[str, str]:
    """Return (title, body) for a download-complete event."""
    title = 'Download Complete'
    body = (
        f'{event.volume_title} ({event.volume_year})'
        f' #{event.issue_number}\n'
        f'Source: {event.download_source}'
    )
    return title, body


def format_volume_add_notification(
    event: VolumeAddEvent
) -> Tuple[str, str]:
    """Return (title, body) for a volume-added event."""
    title = 'Volume Added'
    body = (
        f'{event.volume_title} ({event.volume_year})'
        f' added to library\n'
        f'Publisher: {event.publisher}'
    )
    return title, body


def format_application_update_notification(
    event: ApplicationUpdateEvent
) -> Tuple[str, str]:
    """Return (title, body) for an application-update event."""
    title = 'Application Updated'
    body = (
        f'Kapowarr updated'
        f' {event.previous_version} \u2192 {event.new_version}'
    )
    return title, body


def format_test_notification(event: TestEvent) -> Tuple[str, str]:
    """Return (title, body) for a test event."""
    title = 'Test Notification'
    body = 'This is a test notification from Kapowarr'
    return title, body


# region Provider ABC

class NotificationProvider(ABC):
    """Abstract base class for all notification providers."""

    @abstractmethod
    def on_download(
        self, event: DownloadEvent, settings: Dict
    ) -> None: ...

    @abstractmethod
    def on_volume_add(
        self, event: VolumeAddEvent, settings: Dict
    ) -> None: ...

    @abstractmethod
    def on_application_update(
        self, event: ApplicationUpdateEvent, settings: Dict
    ) -> None: ...

    @abstractmethod
    def on_test(self, event: TestEvent, settings: Dict) -> None: ...

    @abstractmethod
    def validate_settings(self, settings: Dict) -> None:
        """Validate provider-specific settings.

        Raises:
            InvalidNotificationSettings: Settings are invalid.
        """
        ...


class AppriseNotificationProvider(NotificationProvider, ABC):
    """Base class for Apprise-backed providers.

    Subclasses implement ``_send`` and ``validate_settings``;
    all ``on_*`` methods are provided here.
    """

    @abstractmethod
    def _send(
        self, title: str, body: str, settings: Dict
    ) -> None:
        """Send a notification via the concrete provider.

        Args:
            title: Notification title.
            body: Notification body text.
            settings: Provider-specific settings dict.
        """
        ...

    def on_download(
        self, event: DownloadEvent, settings: Dict
    ) -> None:
        title, body = format_download_notification(event)
        self._send(title, body, settings)

    def on_volume_add(
        self, event: VolumeAddEvent, settings: Dict
    ) -> None:
        title, body = format_volume_add_notification(event)
        self._send(title, body, settings)

    def on_application_update(
        self, event: ApplicationUpdateEvent, settings: Dict
    ) -> None:
        title, body = format_application_update_notification(event)
        self._send(title, body, settings)

    def on_test(self, event: TestEvent, settings: Dict) -> None:
        self.validate_settings(settings)
        title, body = format_test_notification(event)
        self._send(title, body, settings)


# Provider registry: maps provider_type string -> provider class
provider_registry: Dict[str, Type[NotificationProvider]] = {}


# region Notification Service

class NotificationService(metaclass=Singleton):
    """Central service that dispatches events to registered providers.

    Note: Singleton
    """

    def _dispatch_async(
        self,
        event_flag: str,
        event,
        method_name: str
    ) -> None:
        """Spawn a background thread to dispatch an event."""
        from backend.internals.server import Server

        def _run() -> None:
            self._dispatch(event_flag, event, method_name)

        t = Server().get_db_thread(
            target=_run,
            name=f'notification-{method_name}'
        )
        t.daemon = True
        t.start()

    def _dispatch(
        self,
        event_flag: str,
        event,
        method_name: str
    ) -> None:
        """Dispatch an event to all enabled matching connections."""
        from backend.internals.db_models_notifications import \
            NotificationConnection

        try:
            connections = NotificationConnection.get_enabled_for_event(
                event_flag
            )
        except Exception:
            LOGGER.exception(
                'Failed to fetch notification connections for %s',
                event_flag
            )
            return

        for conn in connections:
            provider_type = conn['provider_type']
            if provider_type not in provider_registry:
                LOGGER.warning(
                    'Unknown notification provider type: %s (connection %d)',
                    provider_type, conn['id']
                )
                continue
            try:
                provider = provider_registry[provider_type]()
                getattr(provider, method_name)(event, conn['settings'])
            except Exception:
                LOGGER.exception(
                    'Notification provider %s (connection %d "%s") '
                    'failed for event %s',
                    provider_type, conn['id'], conn['name'], method_name
                )
        return

    def notify_download(self, event: DownloadEvent) -> None:
        """Dispatch a download-complete event asynchronously."""
        self._dispatch_async('on_download', event, 'on_download')

    def notify_download_from_download(self, download) -> None:
        """Build a DownloadEvent from a Download object and dispatch it."""
        try:
            from backend.implementations.volumes import Issue, Volume

            vd = Volume(download.volume_id).vd

            issue_number = ''
            issue_title = ''
            issue_comicvine_id = None
            if download.issue_id is not None:
                try:
                    issue_data = Issue(download.issue_id).get_data()
                    issue_number = issue_data.issue_number or ''
                    issue_title = issue_data.title or ''
                    issue_comicvine_id = issue_data.comicvine_id or None
                except Exception:
                    pass

            # count >= 2 means upgrade (add_to_history already ran)
            try:
                from backend.internals.db import get_db
                count = get_db().execute(
                    """
                    SELECT COUNT(*) FROM download_history
                    WHERE volume_id = ?
                      AND (issue_id = ? OR (issue_id IS NULL AND ? IS NULL))
                      AND success = 1;
                    """,
                    (download.volume_id, download.issue_id, download.issue_id)
                ).fetchone()[0]
                is_upgrade = count >= 2
            except Exception:
                is_upgrade = False

            event = DownloadEvent(
                volume_id=vd.id,
                volume_title=vd.title,
                volume_year=vd.year or 0,
                volume_comicvine_id=vd.comicvine_id,
                volume_path=vd.folder or '',
                issue_id=download.issue_id,
                issue_comicvine_id=issue_comicvine_id,
                issue_number=issue_number,
                issue_title=issue_title,
                file_path=download.files[0] if download.files else '',
                download_source=download.source_type.value,
                is_upgrade=is_upgrade
            )
            self.notify_download(event)
        except Exception:
            LOGGER.exception(
                'Failed to build or dispatch download notification '
                'for download %s', getattr(download, 'id', '?')
            )

    def notify_volume_add(self, event: VolumeAddEvent) -> None:
        """Dispatch a volume-added event asynchronously."""
        self._dispatch_async('on_volume_add', event, 'on_volume_add')

    def notify_application_update(
        self, event: ApplicationUpdateEvent
    ) -> None:
        """Dispatch an application-update event asynchronously."""
        self._dispatch_async(
            'on_application_update', event, 'on_application_update'
        )

    def send_test(self, connection_id: int) -> None:
        """Send a test event to a single specific connection.

        Args:
            connection_id (int): The connection to test.

        Raises:
            NotificationNotFound: Connection not found.
            InvalidNotificationSettings: Provider raised on test.
            Exception: Any provider error is re-raised so the API can report it.
        """
        from backend.internals.db_models_notifications import \
            NotificationConnection

        conn = NotificationConnection.get_one(connection_id)
        provider_type = conn['provider_type']
        if provider_type not in provider_registry:
            from backend.base.custom_exceptions import \
                InvalidNotificationSettings
            raise InvalidNotificationSettings(
                f'Unknown provider type: {provider_type}'
            )

        provider = provider_registry[provider_type]()
        provider.on_test(TestEvent(), conn['settings'])


# Import providers so they register themselves
def _import_providers() -> None:
    """Import provider modules to trigger registration in provider_registry."""
    from backend.implementations.notification_providers import (  # noqa: F401
        apprise_generic, custom_script,
        discord_apprise, prowl_apprise, webhook)


_import_providers()
