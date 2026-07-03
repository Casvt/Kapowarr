# -*- coding: utf-8 -*-

"""
Database model for notification connections.
"""

import json
from typing import Dict, List, Union

from backend.base.logging import LOGGER
from backend.internals.db import get_db


class NotificationConnection:
    @staticmethod
    def get_all() -> List[Dict]:
        """Fetch all notification connections.

        Returns:
            List[Dict]: All connections with settings deserialized.
        """
        cursor = get_db()
        cursor.execute("""
            SELECT id, name, provider_type, settings,
                   on_download, on_volume_add,
                   on_application_update, enabled
            FROM notifications
            ORDER BY id;
        """)
        rows: List[Dict] = cursor.fetchalldict()  # type: ignore
        for row in rows:
            row['settings'] = json.loads(row['settings'])
        return rows

    @staticmethod
    def get_one(notification_id: int) -> Dict:
        """Fetch a single notification connection by ID.

        Args:
            notification_id (int): The connection ID.

        Raises:
            NotificationNotFound: No connection with that ID exists.

        Returns:
            Dict: The connection with settings deserialized.
        """
        from backend.base.custom_exceptions import NotificationNotFound

        cursor = get_db()
        cursor.execute("""
            SELECT id, name, provider_type, settings,
                   on_download, on_volume_add,
                   on_application_update, enabled
            FROM notifications
            WHERE id = ?
            LIMIT 1;
        """, (notification_id,))
        row: Union[Dict, None] = cursor.fetchonedict()  # type: ignore
        if row is None:
            raise NotificationNotFound(notification_id)
        row['settings'] = json.loads(row['settings'])
        return row

    @staticmethod
    def add(data: Dict) -> int:
        """Insert a new notification connection.

        Args:
            data (Dict): Keys: name, provider_type, settings (dict),
                on_download, on_volume_add,
                on_application_update, enabled.

        Returns:
            int: The new row ID.
        """
        cursor = get_db()
        with cursor:
            row_id = cursor.execute("""
                INSERT INTO notifications(
                    name, provider_type, settings,
                    on_download, on_volume_add,
                    on_application_update, enabled
                ) VALUES (
                    :name, :provider_type, :settings,
                    :on_download, :on_volume_add,
                    :on_application_update, :enabled
                );
            """, {
                'name': data['name'],
                'provider_type': data['provider_type'],
                'settings': json.dumps(data.get('settings', {})),
                'on_download': int(data.get('on_download', True)),
                'on_volume_add': int(data.get('on_volume_add', True)),
                'on_application_update': int(
                    data.get('on_application_update', True)
                ),
                'enabled': int(data.get('enabled', True))
            }).lastrowid
        LOGGER.debug('Added notification connection with ID %d', row_id)
        return row_id  # type: ignore

    @staticmethod
    def update(notification_id: int, data: Dict) -> None:
        """Update an existing notification connection.

        Args:
            notification_id (int): The connection ID.
            data (Dict): Fields to update (same keys as add()).
        """
        # Verify it exists first (raises NotificationNotFound if missing)
        NotificationConnection.get_one(notification_id)

        cursor = get_db()
        with cursor:
            cursor.execute("""
                UPDATE notifications
                SET name = :name,
                    provider_type = :provider_type,
                    settings = :settings,
                    on_download = :on_download,
                    on_volume_add = :on_volume_add,
                    on_application_update = :on_application_update,
                    enabled = :enabled
                WHERE id = :id;
            """, {
                'id': notification_id,
                'name': data['name'],
                'provider_type': data['provider_type'],
                'settings': json.dumps(data.get('settings', {})),
                'on_download': int(data.get('on_download', True)),
                'on_volume_add': int(data.get('on_volume_add', True)),
                'on_application_update': int(
                    data.get('on_application_update', True)
                ),
                'enabled': int(data.get('enabled', True))
            })
        LOGGER.debug('Updated notification connection %d', notification_id)
        return

    @staticmethod
    def delete(notification_id: int) -> None:
        """Delete a notification connection.

        Args:
            notification_id (int): The connection ID.
        """
        # Verify it exists first (raises NotificationNotFound if missing)
        NotificationConnection.get_one(notification_id)

        cursor = get_db()
        with cursor:
            cursor.execute(
                "DELETE FROM notifications WHERE id = ?;",
                (notification_id,)
            )
        LOGGER.debug('Deleted notification connection %d', notification_id)
        return

    @staticmethod
    def get_enabled_for_event(event_flag: str) -> List[Dict]:
        """Fetch enabled connections that subscribe to the given event flag.

        Args:
            event_flag (str): Column name, e.g. 'on_download'.

        Returns:
            List[Dict]: Matching connections with deserialized settings.
        """
        cursor = get_db()
        cursor.execute(f"""
            SELECT id, name, provider_type, settings,
                   on_download, on_volume_add,
                   on_application_update, enabled
            FROM notifications
            WHERE enabled = 1 AND {event_flag} = 1
            ORDER BY id;
        """)
        rows: List[Dict] = cursor.fetchalldict()  # type: ignore
        for row in rows:
            row['settings'] = json.loads(row['settings'])
        return rows
