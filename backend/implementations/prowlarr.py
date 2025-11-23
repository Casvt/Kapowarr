# -*- coding: utf-8 -*-

"""
Prowlarr integration for managing indexers
"""

from typing import Dict, List, Union

from aiohttp import ClientError

from backend.base.helpers import AsyncSession, normalise_base_url
from backend.base.logging import LOGGER
from backend.implementations.indexers import IndexerDB
from backend.internals.db import get_db
from backend.internals.settings import Settings


class ProwlarrDB:
    """Database operations for Prowlarr settings"""

    @staticmethod
    def get_config() -> Union[Dict, None]:
        """Get Prowlarr configuration.

        Returns:
            Union[Dict, None]: Prowlarr config or None if not configured
        """
        cursor = get_db()
        cursor.execute(
            "SELECT base_url, api_key FROM prowlarr_config LIMIT 1;"
        )
        result = cursor.fetchalldict()
        return result[0] if result else None

    @staticmethod
    def set_config(base_url: str, api_key: str) -> None:
        """Set Prowlarr configuration.

        Args:
            base_url (str): Prowlarr base URL
            api_key (str): Prowlarr API key
        """
        cursor = get_db()
        # Delete existing config and insert new one
        cursor.execute("DELETE FROM prowlarr_config;")
        cursor.execute(
            "INSERT INTO prowlarr_config (base_url, api_key) VALUES (?, ?);",
            (base_url, api_key)
        )

    @staticmethod
    def clear_config() -> None:
        """Clear Prowlarr configuration."""
        get_db().execute("DELETE FROM prowlarr_config;")


class ProwlarrClient:
    """Client for interacting with Prowlarr API"""

    def __init__(self, base_url: str, api_key: str):
        """Initialize Prowlarr client.

        Args:
            base_url (str): Prowlarr base URL
            api_key (str): Prowlarr API key
        """
        self.base_url = normalise_base_url(base_url)
        self.api_key = api_key

    async def test_connection(self) -> bool:
        """Test connection to Prowlarr.

        Returns:
            bool: True if connection successful
        """
        try:
            async with AsyncSession() as session:
                url = f"{self.base_url}/api/v1/system/status"
                headers = {"X-Api-Key": self.api_key}

                response = await session.get(url, headers=headers)

                if response.ok:
                    LOGGER.info("Successfully connected to Prowlarr")
                    return True
                else:
                    LOGGER.warning(
                        "Prowlarr connection failed with "
                        f"status {response.status}"
                    )
                    return False

        except ClientError as e:
            LOGGER.warning(f"Failed to connect to Prowlarr: {e}")
            return False
        except Exception as e:
            LOGGER.error(f"Error testing Prowlarr connection: {e}")
            return False

    async def get_indexers(self) -> List[Dict]:
        """Fetch all indexers from Prowlarr.

        Returns:
            List[Dict]: List of indexer configurations
        """
        try:
            async with AsyncSession() as session:
                url = f"{self.base_url}/api/v1/indexer"
                headers = {"X-Api-Key": self.api_key}

                response = await session.get(url, headers=headers)

                if not response.ok:
                    LOGGER.warning(
                        "Failed to fetch indexers from Prowlarr: "
                        f"{response.status}"
                    )
                    return []

                indexers = await response.json()

                # Filter for comic-capable indexers and parse them
                parsed_indexers = []
                for indexer in indexers:
                    # Skip disabled indexers
                    if not indexer.get('enable', False):
                        continue

                    # Check if indexer supports comics (category 7000-7999)
                    capabilities = indexer.get('capabilities', {})
                    categories = capabilities.get('categories', [])

                    supports_comics = any(
                        7000 <= cat.get('id', 0) < 8000
                        for cat in categories
                    )

                    if not supports_comics:
                        continue

                    # Extract indexer details
                    name = indexer.get('name', 'Unknown')
                    protocol = indexer.get('protocol', 'usenet').lower()
                    indexer_type = 'torznab' if protocol == 'torrent' else 'newznab'

                    # Get base URL from fields
                    fields = indexer.get('fields', [])
                    base_url_field = next(
                        (f for f in fields if f.get('name') == 'baseUrl'),
                        None
                    )
                    api_key_field = next(
                        (f for f in fields if f.get('name') == 'apiKey'),
                        None
                    )

                    if not base_url_field or not api_key_field:
                        continue

                    base_url = base_url_field.get('value', '')
                    api_key = api_key_field.get('value', '')

                    if not base_url or not api_key:
                        continue

                    parsed_indexers.append({
                        'name': name,
                        'base_url': base_url,
                        'api_key': api_key,
                        'indexer_type': indexer_type,
                        'categories': '7030',  # Comics category
                        'prowlarr_id': indexer.get('id')
                    })

                LOGGER.info(
                    f"Found {len(parsed_indexers)} comic-capable "
                    "indexers in Prowlarr"
                )
                return parsed_indexers

        except ClientError as e:
            LOGGER.warning(f"Failed to fetch indexers from Prowlarr: {e}")
            return []
        except Exception as e:
            LOGGER.error(f"Error fetching indexers from Prowlarr: {e}")
            return []


async def sync_prowlarr_indexers() -> Dict[str, int]:
    """Sync indexers from Prowlarr to local database.

    Returns:
        Dict[str, int]: Statistics about sync (added, updated, removed)
    """
    config = ProwlarrDB.get_config()

    if not config:
        LOGGER.warning("Prowlarr not configured")
        return {'added': 0, 'updated': 0, 'removed': 0}

    client = ProwlarrClient(config['base_url'], config['api_key'])

    # Test connection first
    if not await client.test_connection():
        LOGGER.error("Failed to connect to Prowlarr, aborting sync")
        return {'added': 0, 'updated': 0, 'removed': 0}

    # Fetch indexers from Prowlarr
    prowlarr_indexers = await client.get_indexers()

    if not prowlarr_indexers:
        LOGGER.info("No indexers found in Prowlarr")
        return {'added': 0, 'updated': 0, 'removed': 0}

    # Get current indexers
    current_indexers = IndexerDB.get_all()

    # Track Prowlarr indexer names for comparison
    prowlarr_names = {idx['name'] for idx in prowlarr_indexers}
    current_names = {idx['name'] for idx in current_indexers}

    stats = {'added': 0, 'updated': 0, 'removed': 0}

    # Add or update indexers from Prowlarr
    for p_indexer in prowlarr_indexers:
        existing = next(
            (idx for idx in current_indexers
             if idx['name'] == p_indexer['name']),
            None)

        if existing:
            # Update existing indexer
            IndexerDB.update(
                existing['id'],
                base_url=p_indexer['base_url'],
                api_key=p_indexer['api_key'],
                indexer_type=p_indexer['indexer_type'],
                categories=p_indexer['categories']
            )
            stats['updated'] += 1
            LOGGER.debug(f"Updated indexer: {p_indexer['name']}")
        else:
            # Add new indexer
            IndexerDB.add(
                name=p_indexer['name'],
                base_url=p_indexer['base_url'],
                api_key=p_indexer['api_key'],
                indexer_type=p_indexer['indexer_type'],
                categories=p_indexer['categories']
            )
            stats['added'] += 1
            LOGGER.info(f"Added indexer: {p_indexer['name']}")

    # Optionally remove indexers that are no longer in Prowlarr
    # For now, we'll keep them but could add a flag to auto-remove

    LOGGER.info(
        f"Prowlarr sync complete: {stats['added']} added, "
        f"{stats['updated']} updated"
    )

    return stats
