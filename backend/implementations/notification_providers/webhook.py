# -*- coding: utf-8 -*-

"""
Webhook notification provider.

Sends an HTTP POST (or configurable method) with a JSON payload to a
user-configured URL.
"""

from typing import Any, Dict

import requests

from backend.base.logging import LOGGER
from backend.features.notifications import (ApplicationUpdateEvent,
                                            DownloadEvent,
                                            NotificationProvider, TestEvent,
                                            VolumeAddEvent,
                                            get_application_url,
                                            provider_registry)


class WebhookProvider(NotificationProvider):
    """Sends an HTTP request with JSON payload to a configurable URL."""

    FIELDS = [
        {
            'name': 'url',
            'type': 'text',
            'label': 'Webhook URL',
            'placeholder': 'https://example.com/webhook'
        },
        {
            'name': 'method',
            'type': 'select',
            'label': 'HTTP Method',
            'options': ['POST', 'PUT'],
            'default': 'POST'
        },
        {
            'name': 'username',
            'type': 'text',
            'label': 'Username',
            'placeholder': ''
        },
        {
            'name': 'password',
            'type': 'password',
            'label': 'Password',
            'placeholder': ''
        },
        {
            'name': 'headers',
            'type': 'keyvalue',
            'label': 'Custom Headers',
            'placeholder': '{"Authorization": "Bearer token"}',
            'advanced': True
        }
    ]

    def validate_settings(self, settings: Dict) -> None:
        from backend.base.custom_exceptions import InvalidNotificationSettings

        url = settings.get('url', '')
        if not url or not url.startswith('http'):
            raise InvalidNotificationSettings(
                "Webhook settings must include a valid 'url' starting with http"
            )

    def _common_base(self, event_type: str) -> Dict[str, Any]:
        return {
            'eventType': event_type,
            'instanceName': 'Kapowarr',
            'applicationUrl': get_application_url(),
        }

    def _send(self, settings: Dict, payload: Dict) -> None:
        url = settings['url']
        method = settings.get('method', 'POST').upper()
        headers = settings.get('headers') or {}

        # Basic auth (matches Sonarr's username/password support)
        auth = None
        username = settings.get('username', '')
        password = settings.get('password', '')
        if username or password:
            auth = (username, password)

        try:
            response = requests.request(
                method=method,
                url=url,
                json=payload,
                headers=headers,
                auth=auth,
                timeout=30
            )
            if not (200 <= response.status_code < 300):
                LOGGER.warning(
                    'Webhook returned non-2xx status %d for URL %s',
                    response.status_code, url
                )
            else:
                LOGGER.debug('Webhook delivered to %s', url)
        except requests.Timeout:
            LOGGER.warning('Webhook timed out after 30s: %s', url)
        except Exception:
            LOGGER.exception('Failed to deliver webhook to %s', url)

    def on_download(
        self, event: DownloadEvent, settings: Dict
    ) -> None:
        payload = {
            **self._common_base('Download'),
            'volume': {
                'id': event.volume_id,
                'title': event.volume_title,
                'year': event.volume_year,
                'comicvineId': event.volume_comicvine_id,
                'path': event.volume_path,
            },
            'issue': {
                'id': event.issue_id,
                'number': event.issue_number,
                'title': event.issue_title,
            },
            'file': {'path': event.file_path},
            'downloadSource': event.download_source,
            'isUpgrade': event.is_upgrade,
        }
        self._send(settings, payload)

    def on_volume_add(
        self, event: VolumeAddEvent, settings: Dict
    ) -> None:
        payload = {
            **self._common_base('VolumeAdd'),
            'volume': {
                'id': event.volume_id,
                'title': event.volume_title,
                'year': event.volume_year,
                'comicvineId': event.volume_comicvine_id,
                'path': event.volume_path,
                'publisher': event.publisher,
            },
        }
        self._send(settings, payload)

    def on_application_update(
        self, event: ApplicationUpdateEvent, settings: Dict
    ) -> None:
        payload = {
            **self._common_base('ApplicationUpdate'),
            'previousVersion': event.previous_version,
            'newVersion': event.new_version,
            'message': event.message,
        }
        self._send(settings, payload)

    def on_test(self, event: TestEvent, settings: Dict) -> None:
        self.validate_settings(settings)
        payload = self._common_base('Test')
        self._send(settings, payload)


provider_registry['webhook'] = WebhookProvider
