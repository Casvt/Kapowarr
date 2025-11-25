# -*- coding: utf-8 -*-

"""
Support for Newznab and Torznab indexers (usenet and torrent)
"""

from asyncio import gather, sleep
from time import time
from typing import Dict, List, Tuple, Union
from xml.etree import ElementTree as ET

from aiohttp import ClientError

from backend.base.custom_exceptions import (IndexerRateLimitReached,
                                            IndexerTemporarilyBlocked,
                                            InvalidKeyValue)
from backend.base.definitions import Constants, SearchResultData
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession
from backend.base.logging import LOGGER
from backend.internals.db import commit, get_db


class IndexerDB:
    """Database operations for indexers"""

    @staticmethod
    def add(
        name: str,
        base_url: str,
        api_key: str,
        indexer_type: str = "newznab",
        categories: str = "7030",
        protocol: str = "usenet"
    ) -> int:
        """Add a new indexer.

        Args:
            name (str): Display name for the indexer
            base_url (str): Base URL of the indexer
            api_key (str): API key for the indexer
            indexer_type (str): Type of indexer (newznab or torznab)
            categories (str): Comma-separated category IDs (default: 7030 for comics)
            protocol (str): Protocol type ('usenet' or 'torrent')

        Returns:
            int: The ID of the created indexer
        """
        cursor = get_db()
        cursor.execute(
            """
            INSERT INTO indexers (name, base_url, api_key, indexer_type, categories, protocol, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1);
            """,
            (name, base_url, api_key, indexer_type, categories, protocol)
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
            'protocol',
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
            SELECT id, name, base_url, api_key, indexer_type, categories, protocol, enabled
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
            SELECT id, name, base_url, api_key, indexer_type, categories, protocol, enabled
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
            SELECT id, name, base_url, api_key, indexer_type, categories, protocol, enabled
            FROM indexers
            WHERE id = ?
            LIMIT 1;
            """,
            (indexer_id,)
        )
        result = cursor.fetchalldict()
        return result[0] if result else None


# region Indexer Failure Tracking
def record_indexer_failure(indexer_id: int, indexer_name: str) -> None:
    """Record a failure for an indexer and potentially block it temporarily.

    Args:
        indexer_id (int): ID of the indexer that failed
        indexer_name (str): Name of the indexer for logging
    """
    cursor = get_db()
    current_time = int(time())

    # Get current failure record
    cursor.execute(
        "SELECT failure_count, last_failure FROM indexer_failures WHERE indexer_id = ?;",
        (indexer_id,)
    )
    result = cursor.fetchone()

    if result:
        failure_count, last_failure = result
        # Reset count if last failure was more than 10 minutes ago
        if current_time - last_failure > 600:
            failure_count = 1
        else:
            failure_count += 1
    else:
        failure_count = 1

    # Determine if indexer should be temporarily blocked
    next_retry = None
    if failure_count >= Constants.INDEXER_FAILURE_THRESHOLD:
        next_retry = current_time + Constants.INDEXER_TEMP_BLOCK_DURATION
        LOGGER.warning(
            f"Indexer '{indexer_name}' temporarily blocked after {failure_count} failures. "
            f"Will retry at {next_retry}"
        )

    # Update or insert failure record
    cursor.execute(
        """
        INSERT INTO indexer_failures (indexer_id, last_failure, failure_count, next_retry)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(indexer_id) DO UPDATE SET
            last_failure = excluded.last_failure,
            failure_count = excluded.failure_count,
            next_retry = excluded.next_retry;
        """,
        (indexer_id, current_time, failure_count, next_retry)
    )
    commit()


def get_blocked_indexers() -> List[int]:
    """Get list of indexer IDs that are currently blocked.

    Returns:
        List[int]: List of blocked indexer IDs
    """
    cursor = get_db()
    current_time = int(time())

    cursor.execute(
        """
        SELECT indexer_id FROM indexer_failures
        WHERE next_retry IS NOT NULL AND next_retry > ?;
        """,
        (current_time,)
    )

    return [row[0] for row in cursor.fetchall()]


def should_skip_indexer(indexer_id: int) -> Tuple[bool, Union[int, None]]:
    """Check if an indexer should be skipped due to temporary blocking.

    Args:
        indexer_id (int): ID of the indexer to check

    Returns:
        Tuple[bool, Union[int, None]]: (should_skip, retry_time_if_blocked)
    """
    cursor = get_db()
    current_time = int(time())

    cursor.execute(
        "SELECT next_retry FROM indexer_failures WHERE indexer_id = ?;",
        (indexer_id,)
    )
    result = cursor.fetchone()

    if result and result[0] is not None:
        next_retry = result[0]
        if next_retry > current_time:
            return True, next_retry
        else:
            # Block expired, clear it
            clear_indexer_failures(indexer_id)
            return False, None

    return False, None


def clear_indexer_failures(indexer_id: int) -> None:
    """Clear failure records for an indexer.

    Args:
        indexer_id (int): ID of the indexer to clear
    """
    cursor = get_db()
    cursor.execute(
        "DELETE FROM indexer_failures WHERE indexer_id = ?;",
        (indexer_id,)
    )
    commit()
    LOGGER.debug(f"Cleared failure records for indexer {indexer_id}")


async def search_indexer(
    session: AsyncSession,
    indexer: Dict,
    query: str
) -> List[SearchResultData]:
    """Search a single indexer using Newznab/Torznab API with retry logic.

    Args:
        session (AsyncSession): The session to use for requests
        indexer (Dict): Indexer configuration
        query (str): Search query

    Returns:
        List[SearchResultData]: Search results

    Raises:
        IndexerRateLimitReached: If rate limit is detected
        IndexerTemporarilyBlocked: If indexer is blocked
    """
    base_url = indexer['base_url'].rstrip('/')
    api_key = indexer['api_key']
    categories = indexer.get('categories', '7030')
    protocol = indexer.get('protocol', 'usenet')
    indexer_id = indexer['id']
    indexer_name = indexer['name']

    # Check if indexer is temporarily blocked
    is_blocked, retry_time = should_skip_indexer(indexer_id)
    if is_blocked:
        raise IndexerTemporarilyBlocked(indexer_name, retry_time)

    # Newznab/Torznab API parameters
    params = {
        't': 'search',
        'apikey': api_key,
        'q': query,
        'cat': categories,
        'o': 'json'  # Request JSON output
    }

    url = f"{base_url}/api"
    last_exception = None

    # Retry loop with exponential backoff
    for attempt in range(Constants.INDEXER_RETRY_ATTEMPTS):
        try:
            if attempt > 0:
                # Exponential backoff
                backoff_time = Constants.INDEXER_RETRY_BACKOFF * (2 ** (attempt - 1))
                LOGGER.debug(
                    f"Retrying indexer {indexer_name} after {backoff_time}s "
                    f"(attempt {attempt + 1}/{Constants.INDEXER_RETRY_ATTEMPTS})"
                )
                await sleep(backoff_time)

            LOGGER.debug(f"Searching indexer {indexer_name}: {url}")
            response = await session.get(url, params=params)

            # Check for rate limiting
            if response.status in (429, 503):
                LOGGER.warning(
                    f"Indexer {indexer_name} returned rate limit status {response.status}"
                )
                record_indexer_failure(indexer_id, indexer_name)
                raise IndexerRateLimitReached(indexer_name)

            # Check response body for rate limit indicators
            if response.status == 200:
                content_type = response.headers.get('content-type', '').lower()
                if 'json' in content_type or 'xml' in content_type:
                    text = await response.text()
                    text_lower = text.lower()
                    if any(indicator in text_lower for indicator in [
                        'rate limit', 'too many requests', 'quota exceeded',
                        'api limit', 'throttle'
                    ]):
                        LOGGER.warning(
                            f"Indexer {indexer_name} returned rate limit message in body"
                        )
                        record_indexer_failure(indexer_id, indexer_name)
                        raise IndexerRateLimitReached(indexer_name)

                    # Try to parse as JSON first
                    try:
                        data = await response.json()
                        results = _parse_newznab_json(data, indexer_name, protocol)
                        # Success - clear any previous failures
                        if attempt == 0:
                            clear_indexer_failures(indexer_id)
                        return results
                    except Exception:
                        # Fallback to XML parsing
                        results = _parse_newznab_xml(text, indexer_name, protocol)
                        # Success - clear any previous failures
                        if attempt == 0:
                            clear_indexer_failures(indexer_id)
                        return results

            if not response.ok:
                LOGGER.warning(
                    f"Indexer {indexer_name} returned status {response.status}"
                )
                last_exception = ClientError(f"HTTP {response.status}")
                continue

        except IndexerRateLimitReached:
            # Don't retry on rate limits, propagate immediately
            raise

        except IndexerTemporarilyBlocked:
            # Don't retry on blocks, propagate immediately
            raise

        except ClientError as e:
            LOGGER.warning(
                f"Network error searching indexer {indexer_name}: {e}"
            )
            last_exception = e
            continue

        except Exception as e:
            LOGGER.error(f"Error searching indexer {indexer_name}: {e}")
            last_exception = e
            continue

    # All retries exhausted
    if last_exception:
        record_indexer_failure(indexer_id, indexer_name)

    return []


def _parse_newznab_json(
    data: Dict,
    indexer_name: str,
    protocol: str = 'usenet') -> List[SearchResultData]:
    """Parse Newznab/Torznab JSON response.

    Args:
        data (Dict): JSON response data
        indexer_name (str): Name of the indexer
        protocol (str): Protocol type ('usenet' or 'torrent')

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
                "source": indexer_name,
                "protocol": protocol
            }

            results.append(result)

        except Exception as e:
            LOGGER.debug(f"Failed to parse item from {indexer_name}: {e}")
            continue

    return results


def _parse_newznab_xml(
    xml_text: str,
    indexer_name: str,
    protocol: str = 'usenet') -> List[SearchResultData]:
    """Parse Newznab/Torznab XML response.

    Args:
        xml_text (str): XML response text
        indexer_name (str): Name of the indexer
        protocol (str): Protocol type ('usenet' or 'torrent')

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
                    "source": indexer_name,
                    "protocol": protocol
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
) -> Tuple[List[SearchResultData], List[Dict[str, Union[str, int]]]]:
    """Search all enabled indexers and collect errors.

    Args:
        session (AsyncSession): The session to use for requests
        query (str): Search query

    Returns:
        Tuple[List[SearchResultData], List[Dict[str, Union[str, int]]]]: 
            (search_results, errors)
            errors is a list of dicts with keys: indexer, error, blocked_until (optional)
    """
    indexers = IndexerDB.get_enabled()

    if not indexers:
        LOGGER.debug("No enabled indexers found")
        return [], []

    # Search all indexers in parallel, capturing exceptions
    all_results: List[SearchResultData] = []
    errors: List[Dict[str, Union[str, int]]] = []
    seen_links = set()

    async def search_with_error_handling(indexer: Dict):
        """Wrapper to catch and record errors from individual indexer searches."""
        try:
            results = await search_indexer(session, indexer, query)
            return results, None
        except IndexerTemporarilyBlocked as e:
            error_dict = {
                "indexer": indexer['name'],
                "error": f"Temporarily blocked until {e.retry_time}",
                "blocked_until": e.retry_time
            }
            LOGGER.debug(f"Skipping blocked indexer: {indexer['name']}")
            return [], error_dict
        except IndexerRateLimitReached as e:
            error_dict = {
                "indexer": indexer['name'],
                "error": "Rate limit reached"
            }
            return [], error_dict
        except Exception as e:
            error_dict = {
                "indexer": indexer['name'],
                "error": str(e)
            }
            LOGGER.warning(f"Error searching indexer {indexer['name']}: {e}")
            return [], error_dict

    # Execute all searches in parallel
    search_tasks = [
        search_with_error_handling(indexer)
        for indexer in indexers
    ]
    results_and_errors = await gather(*search_tasks)

    # Process results and errors
    for results, error in results_and_errors:
        if error:
            errors.append(error)
        for result in results:
            if result['link'] not in seen_links:
                all_results.append(result)
                seen_links.add(result['link'])

    LOGGER.info(
        f"Found {len(all_results)} results from {len(indexers)} indexers "
        f"({len(errors)} errors)"
    )
    return all_results, errors
