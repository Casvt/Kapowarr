# -*- coding: utf-8 -*-

"""
Support for Newznab and Torznab indexers (usenet and torrent)
"""

from asyncio import gather
from typing import Dict, List, Union
from xml.etree import ElementTree as ET

from aiohttp import ClientError

from backend.base.custom_exceptions import InvalidKeyValue
from backend.base.definitions import SearchResultData
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class IndexerDB:
    """Database operations for indexers"""

    @staticmethod
    def add(
        name: str,
        base_url: str,
        api_key: str,
        indexer_type: str = "newznab",
        categories: str = "7030"
    ) -> int:
        """Add a new indexer.

        Args:
            name (str): Display name for the indexer
            base_url (str): Base URL of the indexer
            api_key (str): API key for the indexer
            indexer_type (str): Type of indexer (newznab or torznab)
            categories (str): Comma-separated category IDs (default: 7030 for comics)

        Returns:
            int: The ID of the created indexer
        """
        cursor = get_db()
        cursor.execute(
            """
            INSERT INTO indexers (name, base_url, api_key, indexer_type, categories, enabled)
            VALUES (?, ?, ?, ?, ?, 1);
            """,
            (name, base_url, api_key, indexer_type, categories)
        )
        return cursor.lastrowid

    @staticmethod
    def update(indexer_id: int, **kwargs) -> None:
        """Update an indexer.

        Args:
            indexer_id (int): ID of the indexer to update
            **kwargs: Fields to update
        """
        allowed_fields = {
            'name',
            'base_url',
            'api_key',
            'indexer_type',
            'categories',
            'enabled'}
        fields_to_update = {k: v for k, v in kwargs.items()
                            if k in allowed_fields}

        if not fields_to_update:
            raise InvalidKeyValue("No valid fields to update")

        set_clause = ", ".join(f"{k} = ?" for k in fields_to_update.keys())
        values = list(fields_to_update.values()) + [indexer_id]

        get_db().execute(
            f"UPDATE indexers SET {set_clause} WHERE id = ?;",
            values
        )

    @staticmethod
    def delete(indexer_id: int) -> None:
        """Delete an indexer.

        Args:
            indexer_id (int): ID of the indexer to delete
        """
        get_db().execute("DELETE FROM indexers WHERE id = ?;", (indexer_id,))

    @staticmethod
    def get_all() -> List[Dict]:
        """Get all indexers.

        Returns:
            List[Dict]: List of all indexers
        """
        cursor = get_db()
        cursor.execute(
            """
            SELECT id, name, base_url, api_key, indexer_type, categories, enabled
            FROM indexers
            ORDER BY name;
            """
        )
        return cursor.fetchalldict()

    @staticmethod
    def get_enabled() -> List[Dict]:
        """Get all enabled indexers.

        Returns:
            List[Dict]: List of enabled indexers
        """
        cursor = get_db()
        cursor.execute(
            """
            SELECT id, name, base_url, api_key, indexer_type, categories, enabled
            FROM indexers
            WHERE enabled = 1
            ORDER BY name;
            """
        )
        return cursor.fetchalldict()

    @staticmethod
    def get_by_id(indexer_id: int) -> Union[Dict, None]:
        """Get an indexer by ID.

        Args:
            indexer_id (int): ID of the indexer

        Returns:
            Union[Dict, None]: Indexer data or None if not found
        """
        cursor = get_db()
        cursor.execute(
            """
            SELECT id, name, base_url, api_key, indexer_type, categories, enabled
            FROM indexers
            WHERE id = ?
            LIMIT 1;
            """,
            (indexer_id,)
        )
        result = cursor.fetchalldict()
        return result[0] if result else None


async def search_indexer(
    session: AsyncSession,
    indexer: Dict,
    query: str
) -> List[SearchResultData]:
    """Search a single indexer using Newznab/Torznab API.

    Args:
        session (AsyncSession): The session to use for requests
        indexer (Dict): Indexer configuration
        query (str): Search query

    Returns:
        List[SearchResultData]: Search results
    """
    base_url = indexer['base_url'].rstrip('/')
    api_key = indexer['api_key']
    categories = indexer.get('categories', '7030')

    # Newznab/Torznab API parameters
    params = {
        't': 'search',
        'apikey': api_key,
        'q': query,
        'cat': categories,
        'o': 'json'  # Request JSON output
    }

    try:
        url = f"{base_url}/api"
        LOGGER.debug(f"Searching indexer {indexer['name']}: {url}")

        response = await session.get(url, params=params)

        if not response.ok:
            LOGGER.warning(
                f"Indexer {indexer['name']} returned status {response.status}"
            )
            return []

        # Try JSON first
        try:
            data = await response.json()
            return _parse_newznab_json(data, indexer['name'])
        except Exception:
            # Fallback to XML
            text = await response.text()
            return _parse_newznab_xml(text, indexer['name'])

    except ClientError as e:
        LOGGER.warning(f"Failed to search indexer {indexer['name']}: {e}")
        return []
    except Exception as e:
        LOGGER.error(f"Error searching indexer {indexer['name']}: {e}")
        return []


def _parse_newznab_json(
    data: Dict,
    indexer_name: str) -> List[SearchResultData]:
    """Parse Newznab/Torznab JSON response.

    Args:
        data (Dict): JSON response data
        indexer_name (str): Name of the indexer

    Returns:
        List[SearchResultData]: Parsed search results
    """
    results = []

    # Handle different JSON structures
    items = []
    if 'channel' in data and 'item' in data['channel']:
        items = data['channel']['item']
    elif 'item' in data:
        items = data['item']

    if not isinstance(items, list):
        items = [items] if items else []

    for item in items:
        try:
            title = item.get('title', '')
            link = item.get('link', '')
            guid = item.get('guid', '')

            # Prefer link over guid for download URL
            download_link = link or guid

            if not download_link or not title:
                continue

            # Extract metadata from title
            extracted = extract_filename_data(
                title,
                assume_volume_number=False,
                fix_year=True
            )

            result: SearchResultData = {
                **extracted,
                "link": download_link,
                "display_title": title,
                "source": indexer_name
            }

            results.append(result)

        except Exception as e:
            LOGGER.debug(f"Failed to parse item from {indexer_name}: {e}")
            continue

    return results


def _parse_newznab_xml(
    xml_text: str,
    indexer_name: str) -> List[SearchResultData]:
    """Parse Newznab/Torznab XML response.

    Args:
        xml_text (str): XML response text
        indexer_name (str): Name of the indexer

    Returns:
        List[SearchResultData]: Parsed search results
    """
    results = []

    try:
        root = ET.fromstring(xml_text)

        # Find all items in the RSS feed
        for item in root.findall('.//item'):
            try:
                title_elem = item.find('title')
                link_elem = item.find('link')
                guid_elem = item.find('guid')

                if title_elem is None:
                    continue

                title = title_elem.text or ''
                link = link_elem.text if link_elem is not None else ''
                guid = guid_elem.text if guid_elem is not None else ''

                # Prefer link over guid
                download_link = link or guid

                if not download_link or not title:
                    continue

                # Extract metadata from title
                extracted = extract_filename_data(
                    title,
                    assume_volume_number=False,
                    fix_year=True
                )

                result: SearchResultData = {
                    **extracted,
                    "link": download_link,
                    "display_title": title,
                    "source": indexer_name
                }

                results.append(result)

            except Exception as e:
                LOGGER.debug(f"Failed to parse item from {indexer_name}: {e}")
                continue

    except Exception as e:
        LOGGER.error(f"Failed to parse XML from {indexer_name}: {e}")

    return results


async def search_all_indexers(
    session: AsyncSession,
    query: str
) -> List[SearchResultData]:
    """Search all enabled indexers.

    Args:
        session (AsyncSession): The session to use for requests
        query (str): Search query

    Returns:
        List[SearchResultData]: Combined search results from all indexers
    """
    indexers = IndexerDB.get_enabled()

    if not indexers:
        LOGGER.debug("No enabled indexers found")
        return []

    # Search all indexers in parallel
    search_tasks = [
        search_indexer(session, indexer, query)
        for indexer in indexers
    ]

    results_per_indexer = await gather(*search_tasks)

    # Combine and deduplicate results
    all_results: List[SearchResultData] = []
    seen_links = set()

    for results in results_per_indexer:
        for result in results:
            if result['link'] not in seen_links:
                all_results.append(result)
                seen_links.add(result['link'])

    LOGGER.info(
        f"Found {
            len(all_results)} results from {
            len(indexers)} indexers")
    return all_results
