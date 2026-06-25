# -*- coding: utf-8 -*-

"""
Prowl notification provider (via apprise prowl:// plugin).
"""

from typing import Dict
from urllib.parse import quote

import apprise

from backend.base.logging import LOGGER
from backend.features.notifications import (AppriseNotificationProvider,
                                            provider_registry)

_PRIORITY_MAP = {
    'Very Low': -2,
    'Low': -1,
    'Normal': 0,
    'High': 1,
    'Emergency': 2,
}


class ProwlProvider(AppriseNotificationProvider):
    """Sends notifications via Prowl (iOS push notification service)."""

    FIELDS = [
        {
            'name': 'api_key',
            'type': 'password',
            'label': 'API Key',
            'placeholder': '',
        },
        {
            'name': 'application',
            'type': 'text',
            'label': 'Application',
            'placeholder': 'Kapowarr',
        },
        {
            'name': 'priority',
            'type': 'select',
            'label': 'Priority',
            'options': [
                'Very Low', 'Low', 'Normal', 'High', 'Emergency'
            ],
            'default': 'Normal',
        },
    ]

    def validate_settings(self, settings: Dict) -> None:
        from backend.base.custom_exceptions import InvalidNotificationSettings

        if not settings.get('api_key', '').strip():
            raise InvalidNotificationSettings(
                'Prowl settings must include a non-empty API key'
            )

    def _build_prowl_url(self, settings: Dict) -> str:
        api_key = settings.get('api_key', '').strip()
        application = (
            settings.get('application', '').strip() or 'Kapowarr'
        )
        priority_label = settings.get('priority', 'Normal')
        priority = _PRIORITY_MAP.get(priority_label, 0)
        encoded_app = quote(application, safe='')
        return (
            f'prowl://{api_key}/{encoded_app}'
            f'?priority={priority}'
        )

    def _send(
        self, title: str, body: str, settings: Dict
    ) -> None:
        url = self._build_prowl_url(settings)
        try:
            a = apprise.Apprise()
            a.add(url)
            a.notify(title=title, body=body)
            LOGGER.debug('Prowl notification sent')
        except Exception:
            LOGGER.exception('Prowl notification failed')


provider_registry['prowl'] = ProwlProvider
