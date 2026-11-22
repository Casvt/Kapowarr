# -*- coding: utf-8 -*-

"""
Newznab indexer client. Searches a Newznab compatible API (a usenet indexer
like NZBGeek or NZBFinder, or an indexer proxied by Prowlarr/NZBHydra2) for
NZB files.
"""

from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Tuple, Union
from xml.etree.ElementTree import Element, ParseError, fromstring

from requests import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, DownloadType,
                                      IndexerClientField as ICF, QueryResult,
                                      SearchQuery, SearchResultData)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession, Session
from backend.base.logging import LOGGER
from backend.implementations.indexer_client_manager import (BaseIndexerClient,
                                                            IndexerClients)

PAGE_SIZE = 100

NEWZNAB_NS = "{http://www.newznab.com/DTD/2010/feeds/attributes/}"

RECENT_TITLES: "OrderedDict[str, str]" = OrderedDict()
"""
NZB link -> release title of recent search results. The download prepper
only gets the link, and the NZB itself doesn't reliably contain the release
name (its meta name is often a raw usenet subject).
"""
RECENT_TITLES_MAX = 10_000


def remember_title(link: str, title: str) -> None:
    "Remember the release title of an NZB link"
    RECENT_TITLES[link] = title
    RECENT_TITLES.move_to_end(link)
    while len(RECENT_TITLES) > RECENT_TITLES_MAX:
        RECENT_TITLES.popitem(last=False)
    return


NEWZNAB_AUTH_ERRORS = ("100", "101", "102")
"""
Newznab error codes for incorrect user credentials, account suspended and
insufficient privileges
"""


def _newznab_error(root: Element) -> Union[Tuple[str, str], None]:
    """Get the Newznab error in a response, if it is one.

    Args:
        root (Element): The root of the XML response.

    Returns:
        Union[Tuple[str, str], None]: The error code and description, or
            `None` if the response isn't an error.
    """
    if root.tag != 'error':
        return None
    return (root.get('code') or '', root.get('description') or '')


def _parse_items(
    root: Element
) -> Tuple[List[Dict[str, Any]], Union[int, None], Union[int, None]]:
    """Get the releases out of a Newznab search response.

    Args:
        root (Element): The root of the XML (RSS) response.

    Returns:
        Tuple[List[Dict[str, Any]], Union[int, None], Union[int, None]]:
            The releases (title, link, size, pub_date), the offset and the
            total number of results, if the indexer supplied them.
    """
    channel = root.find('channel')
    if channel is None:
        return [], None, None

    offset, total = None, None
    response = channel.find(f'{NEWZNAB_NS}response')
    if response is not None:
        try:
            offset = int(response.get('offset') or 0)
            total = int(response.get('total') or 0)
        except ValueError:
            pass

    items: List[Dict[str, Any]] = []
    for item in channel.findall('item'):
        title = (item.findtext('title') or '').strip()

        link = (item.findtext('link') or '').strip()
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.get('url'):
            link = enclosure.get('url') or link

        if not title or not link:
            continue

        size = -1
        attrs = {
            attr.get('name'): attr.get('value')
            for attr in item.findall(f'{NEWZNAB_NS}attr')
        }
        for candidate in (
            attrs.get('size'),
            item.findtext('size'),
            enclosure.get('length') if enclosure is not None else None
        ):
            try:
                if candidate and int(candidate) > 0:
                    size = int(candidate)
                    break
            except ValueError:
                continue

        pub_date = None
        raw_date = item.findtext('pubDate')
        if raw_date:
            try:
                pub_date = parsedate_to_datetime(raw_date)
            except (TypeError, ValueError):
                pub_date = None

        items.append({
            'title': title,
            'link': link,
            'size': size,
            'pub_date': pub_date
        })

    return items, offset, total


@IndexerClients.register_client(
    DownloadType.USENET, 'Newznab',
    (
        ICF.TITLE, ICF.ENABLED, ICF.URL,
        ICF.API_PATH, ICF.API_KEY, ICF.CATEGORIES
    ),
    allow_multiple_instances=True
)
class NewznabIndexer(BaseIndexerClient):
    def __init__(self, indexer_id: int) -> None:
        super().__init__(indexer_id)
        self.session: Union[AsyncSession, None] = None
        return

    def _to_search_result(self, item: Dict[str, Any]) -> SearchResultData:
        remember_title(item['link'], item['title'])
        return {
            **extract_filename_data(
                item['title'],
                assume_volume_number=False,
                fix_year=True
            ),
            "link": item['link'],
            "display_title": item['title'],
            "size": item['size'],
            "indexer_id": self._id,
            "indexer_title": self._title,
            "seeders": None,
            "leechers": None
        }

    async def _request(self, params: Dict[str, Any]) -> Union[Element, None]:
        if not self.session:
            self.session = AsyncSession()

        text = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                **params,
                'apikey': self._api_key or '',
                'cat': str(self._categories or [])
            },
            quiet_fail=True
        )
        if not text:
            return None

        try:
            root = fromstring(text)
        except ParseError:
            LOGGER.warning(
                f"Newznab indexer {self._title} returned an invalid response"
            )
            return None

        error = _newznab_error(root)
        if error:
            LOGGER.warning(
                f"Newznab indexer {self._title} returned error {error[0]}: "
                f"{error[1]}"
            )
            return None

        return root

    async def search(self, query: SearchQuery) -> QueryResult:
        offset = (query['page'] - 1) * PAGE_SIZE
        root = await self._request({
            't': 'search',
            'q': query['query'],
            'offset': offset,
            'limit': PAGE_SIZE,
            'extended': 1
        })
        if root is None:
            return QueryResult([], next_page_available=False)

        items, response_offset, total = _parse_items(root)
        if total is not None:
            next_page_available = (
                (response_offset or offset) + len(items) < total
            )
        else:
            next_page_available = len(items) >= PAGE_SIZE

        return QueryResult(
            [self._to_search_result(item) for item in items],
            next_page_available=next_page_available
        )

    async def discover(self, last_check: datetime) -> List[SearchResultData]:
        root = await self._request({
            't': 'search',
            'limit': PAGE_SIZE,
            'extended': 1
        })
        if root is None:
            return []

        if last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=timezone.utc)

        items, _, _ = _parse_items(root)
        return [
            self._to_search_result(item)
            for item in items
            if item['pub_date'] is None or item['pub_date'] > last_check
        ]

    async def shutdown(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        return

    @classmethod
    def test(cls, url: str, **extra_fields: Any) -> None:
        api_path: str = extra_fields[ICF.API_PATH.value]
        api_key: str = extra_fields[ICF.API_KEY.value]
        categories: str = extra_fields[ICF.CATEGORIES.value]

        with Session() as session:
            try:
                # Searching instead of asking for the capabilities, because
                # some indexers allow `t=caps` without (valid) API key.
                response = session.get(
                    url + (api_path or ''),
                    params={
                        't': 'search',
                        'q': 'test',
                        'limit': 1,
                        'apikey': api_key or '',
                        'cat': categories
                    }
                )

            except RequestException:
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code in (401, 403):
            # E.g. Prowlarr answers a wrong API key with an empty 401
            raise CredentialInvalid

        try:
            root = fromstring(response.text)
        except ParseError:
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        error = _newznab_error(root)
        if error:
            if error[0] in NEWZNAB_AUTH_ERRORS:
                raise CredentialInvalid
            LOGGER.error(
                f"Newznab indexer returned error {error[0]}: {error[1]}"
            )
            raise ClientNotWorking(
                BrokenClientReason.FAILED_PROCESSING_RESPONSE
            )

        if root.tag != 'rss':
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)
        return
