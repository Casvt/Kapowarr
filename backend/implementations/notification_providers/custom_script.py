# -*- coding: utf-8 -*-

"""
Custom Script notification provider.

Executes a user-specified script with kapowarr_-prefixed environment variables,
following the Sonarr convention for custom script notifications.
"""

import os
import subprocess
from typing import Dict

from backend.base.logging import LOGGER
from backend.features.notifications import (ApplicationUpdateEvent,
                                            DownloadEvent,
                                            NotificationProvider, TestEvent,
                                            VolumeAddEvent,
                                            get_application_url,
                                            provider_registry)


class CustomScriptProvider(NotificationProvider):
    """Runs a user script with kapowarr_* environment variables."""

    FIELDS = [
        {
            'name': 'path',
            'type': 'text',
            'label': 'Script Path',
            'placeholder': '/path/to/script.sh'
        }
    ]

    def validate_settings(self, settings: Dict) -> None:
        from backend.base.custom_exceptions import InvalidNotificationSettings

        if not settings.get('path'):
            raise InvalidNotificationSettings(
                "Custom script settings must include 'path'"
            )

    def _common_env(self, event_type: str) -> Dict[str, str]:
        return {
            'kapowarr_eventtype': event_type,
            'kapowarr_instancename': 'Kapowarr',
            'kapowarr_applicationurl': get_application_url(),
        }

    def _run_script(self, path: str, env: Dict[str, str]) -> None:
        full_env = {**os.environ, **env}
        try:
            result = subprocess.run(
                [path],
                env=full_env,
                timeout=60,
                capture_output=True
            )
            if result.returncode != 0:
                LOGGER.warning(
                    'Custom script exited with code %d. stderr: %s',
                    result.returncode,
                    result.stderr.decode('utf-8', errors='replace').strip()
                )
            else:
                LOGGER.debug(
                    'Custom script ran successfully: %s', path
                )
        except subprocess.TimeoutExpired:
            LOGGER.warning('Custom script timed out after 60s: %s', path)
        except Exception:
            LOGGER.exception('Failed to run custom script: %s', path)

    def on_download(
        self, event: DownloadEvent, settings: Dict
    ) -> None:
        env = {
            **self._common_env('Download'),
            'kapowarr_volume_id': str(event.volume_id),
            'kapowarr_volume_title': event.volume_title,
            'kapowarr_volume_year': str(event.volume_year),
            'kapowarr_volume_comicvine_id': str(event.volume_comicvine_id),
            'kapowarr_volume_path': event.volume_path,
            'kapowarr_issue_id': str(event.issue_id or ''),
            'kapowarr_issue_comicvine_id': str(event.issue_comicvine_id or ''),
            'kapowarr_issue_number': event.issue_number,
            'kapowarr_issue_title': event.issue_title or '',
            'kapowarr_file_path': event.file_path,
            'kapowarr_download_source': event.download_source,
            'kapowarr_isupgrade': str(event.is_upgrade).upper(),
        }
        self._run_script(settings['path'], env)

    def on_volume_add(
        self, event: VolumeAddEvent, settings: Dict
    ) -> None:
        env = {
            **self._common_env('VolumeAdd'),
            'kapowarr_volume_id': str(event.volume_id),
            'kapowarr_volume_title': event.volume_title,
            'kapowarr_volume_year': str(event.volume_year),
            'kapowarr_volume_comicvine_id': str(event.volume_comicvine_id),
            'kapowarr_volume_path': event.volume_path,
            'kapowarr_volume_publisher': event.publisher or '',
        }
        self._run_script(settings['path'], env)

    def on_application_update(
        self, event: ApplicationUpdateEvent, settings: Dict
    ) -> None:
        env = {
            **self._common_env('ApplicationUpdate'),
            'kapowarr_update_previousversion': event.previous_version,
            'kapowarr_update_newversion': event.new_version,
            'kapowarr_update_message': event.message,
        }
        self._run_script(settings['path'], env)

    def on_test(self, event: TestEvent, settings: Dict) -> None:
        self.validate_settings(settings)
        env = self._common_env('Test')
        self._run_script(settings['path'], env)


provider_registry['custom_script'] = CustomScriptProvider
