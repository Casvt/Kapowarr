# -*- coding: utf-8 -*-

"""
Generic Apprise notification provider.

Supports two delivery modes (both can be active simultaneously):
  - Stateless URLs: apprise Python library sends directly.
  - Server mode: HTTP POST to a self-hosted apprise-api server.
"""

from typing import Dict, List

import apprise
import requests

from backend.base.logging import LOGGER
from backend.features.notifications import (AppriseNotificationProvider,
                                            provider_registry)


class AppriseGenericProvider(AppriseNotificationProvider):
    """Connects to an apprise-api server or uses stateless apprise URLs."""

    FIELDS = [
        {
            'name': 'server_url',
            'type': 'text',
            'label': 'Apprise Server URL',
            'placeholder': 'http://localhost:8000',
        },
        {
            'name': 'config_key',
            'type': 'text',
            'label': 'Apprise Configuration Key',
            'placeholder': '',
        },
        {
            'name': 'stateless_urls',
            'type': 'text',
            'label': 'Apprise Stateless URLs',
            'placeholder': 'discord://..., slack://...',
        },
        {
            'name': 'notify_type',
            'type': 'select',
            'label': 'Apprise Notification Type',
            'options': ['Info', 'Success', 'Warning', 'Failure'],
            'default': 'Info',
        },
        {
            'name': 'tags',
            'type': 'text',
            'label': 'Apprise Tags',
            'placeholder': '',
        },
        {
            'name': 'username',
            'type': 'text',
            'label': 'Username',
            'placeholder': '',
        },
        {
            'name': 'password',
            'type': 'password',
            'label': 'Password',
            'placeholder': '',
        },
    ]

    def validate_settings(self, settings: Dict) -> None:
        from backend.base.custom_exceptions import InvalidNotificationSettings

        server_url = (settings.get('server_url') or '').strip()
        stateless_urls = (settings.get('stateless_urls') or '').strip()
        if not server_url and not stateless_urls:
            raise InvalidNotificationSettings(
                'Apprise settings require at least one of '
                '"Apprise Server URL" or "Apprise Stateless URLs"'
            )

    def _send_stateless(
        self, title: str, body: str, settings: Dict
    ) -> None:
        raw = settings.get('stateless_urls', '')
        urls: List[str] = [
            u.strip() for u in raw.split(',') if u.strip()
        ]
        try:
            a = apprise.Apprise()
            for url in urls:
                a.add(url)
            a.notify(title=title, body=body)
            LOGGER.debug(
                'Apprise stateless notification sent to %d URL(s)',
                len(urls)
            )
        except Exception:
            LOGGER.exception('Apprise stateless notification failed')

    def _send_server(
        self, title: str, body: str, settings: Dict
    ) -> None:
        server_url = settings['server_url'].rstrip('/')
        config_key = (settings.get('config_key') or '').strip()
        if config_key:
            endpoint = '{0}/notify/{1}'.format(server_url, config_key)
        else:
            endpoint = '{0}/notify/'.format(server_url)
        notify_type = settings.get('notify_type') or 'Info'
        tags = (settings.get('tags') or '').strip()
        username = (settings.get('username') or '').strip()
        password = (settings.get('password') or '').strip()

        payload: Dict = {
            'title': title,
            'body': body,
            'type': notify_type,
        }
        if tags:
            payload['tag'] = tags

        auth = None
        if username or password:
            auth = (username, password)

        try:
            response = requests.post(
                endpoint,
                json=payload,
                auth=auth,
                timeout=30,
            )
            if not (200 <= response.status_code < 300):
                LOGGER.warning(
                    'Apprise server returned non-2xx status %d for %s',
                    response.status_code, endpoint
                )
            else:
                LOGGER.debug(
                    'Apprise server notification sent to %s', endpoint
                )
        except Exception:
            LOGGER.exception(
                'Apprise server notification failed for %s', endpoint
            )

    def _send(
        self, title: str, body: str, settings: Dict
    ) -> None:
        if (settings.get('stateless_urls') or '').strip():
            self._send_stateless(title, body, settings)
        if (settings.get('server_url') or '').strip():
            self._send_server(title, body, settings)


provider_registry['apprise'] = AppriseGenericProvider
