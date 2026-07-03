# -*- coding: utf-8 -*-

"""
Discord notification provider (via apprise discord:// plugin).
"""

import re
from typing import Dict

import apprise

from backend.base.logging import LOGGER
from backend.features.notifications import (AppriseNotificationProvider,
                                            provider_registry)

_DISCORD_WEBHOOK_RE = re.compile(
    r'https://discord(?:app)?\.com/api/webhooks/(\d+)/([^/?#]+)'
)


class DiscordProvider(AppriseNotificationProvider):
    """Sends notifications to a Discord channel via webhook."""

    FIELDS = [
        {
            'name': 'webhook_url',
            'type': 'text',
            'label': 'Webhook URL',
            'placeholder': (
                'https://discord.com/api/webhooks/...'
            ),
        }
    ]

    def validate_settings(self, settings: Dict) -> None:
        from backend.base.custom_exceptions import InvalidNotificationSettings

        url = settings.get('webhook_url', '')
        if not _DISCORD_WEBHOOK_RE.match(url):
            raise InvalidNotificationSettings(
                'Discord webhook URL must match '
                'https://discord.com/api/webhooks/{id}/{token}'
            )

    def _send(
        self, title: str, body: str, settings: Dict
    ) -> None:
        url = settings.get('webhook_url', '')
        m = _DISCORD_WEBHOOK_RE.match(url)
        if not m:
            LOGGER.warning(
                'DiscordProvider: invalid webhook URL, skipping'
            )
            return
        webhook_id, webhook_token = m.group(1), m.group(2)
        apprise_url = f'discord://{webhook_id}/{webhook_token}'
        try:
            a = apprise.Apprise()
            a.add(apprise_url)
            a.notify(title=title, body=body)
            LOGGER.debug('Discord notification sent')
        except Exception:
            LOGGER.exception('Discord notification failed')


provider_registry['discord'] = DiscordProvider
