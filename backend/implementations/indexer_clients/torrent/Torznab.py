# -*- coding: utf-8 -*-

from datetime import datetime
from html import unescape
from typing import Any, List, Union
from urllib.parse import unquote
from xml.etree import ElementTree

from requests import RequestException

from backend.base.custom_exceptions import ClientNotWorking, CredentialInvalid
from backend.base.definitions import (BrokenClientReason, DownloadType,
                                      IndexerClientField as ICF, QueryResult,
                                      SearchQuery, SearchResultData)
from backend.base.file_extraction import extract_filename_data
from backend.base.helpers import AsyncSession, Session, build_magnet_link
from backend.implementations.indexer_client_manager import (BaseIndexerClient,
                                                            IndexerClients)


@IndexerClients.register_client(
    DownloadType.TORRENT, 'Torznab',
    (
        ICF.TITLE, ICF.ENABLED, ICF.URL,
        ICF.API_PATH, ICF.API_KEY, ICF.CATEGORIES
    ),
    allow_multiple_instances=True
)
class TorznabIndexer(BaseIndexerClient):
    def __init__(self, indexer_id: int) -> None:
        super().__init__(indexer_id)

        self.session: Union[AsyncSession, None] = None

        return

    def __process_item(
        self,
        item: ElementTree.Element
    ) -> Union[SearchResultData, None]:
        torznab_keys = {
            tor_key.attrib["name"].lower(): tor_key.attrib["value"]
            for tor_key in item.findall(
                "{http://torznab.com/schemas/2015/feed}attr"
            )
            if "name" in tor_key.attrib and "value" in tor_key.attrib
        }

        # Title
        title = item.findtext("title")
        if not title:
            return None

        # Link
        magnet_link = torznab_keys.get("magneturl") or ''

        guid = item.findtext("guid")
        if not magnet_link and guid and guid.startswith("magnet:?"):
            magnet_link = guid

        if not magnet_link and "infohash" in torznab_keys:
            magnet_link = build_magnet_link(
                torznab_keys["infohash"].lower(), title
            )

        enclosure_el = item.find('enclosure')
        if not magnet_link and enclosure_el is not None:
            magnet_link = enclosure_el.attrib.get('url') or ''

        link = item.findtext("link")
        if not magnet_link and link:
            magnet_link = link

        if not magnet_link:
            return None
        magnet_link = unquote(unescape(magnet_link))

        # Size
        size = torznab_keys.get("size", "")
        if (
            not size
            and enclosure_el is not None
            and enclosure_el.attrib.get("length")
        ):
            size = enclosure_el.attrib.get("length", "")
        if not size:
            size = item.findtext("size") or size
        if size.isdigit():
            parsed_size = int(size)
        else:
            parsed_size = -1

        # Seeders/Leechers
        seeders, leechers = None, None
        if torznab_keys.get("seeders", "").isdigit():
            seeders = int(torznab_keys["seeders"])
        if torznab_keys.get("peers", "").isdigit():
            leechers = int(torznab_keys["peers"])

        return {
            **extract_filename_data(
                title,
                assume_volume_number=False,
                fix_year=True
            ),
            "link": magnet_link,
            "display_title": title,
            "size": parsed_size,
            "indexer_id": self._id,
            "indexer_title": self._title,
            "seeders": seeders,
            "leechers": leechers
        }

    async def search(self, query: SearchQuery) -> QueryResult:
        if not self.session:
            self.session = AsyncSession()

        results = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                't': 'search',
                'apikey': self._api_key,
                'extended': 1,
                'q': query['query'],
                'cat': str(self._categories or [])
            },
            quiet_fail=True
        )
        if not results:
            return QueryResult([], next_page_available=False)

        formatted_results: List[SearchResultData] = []
        for item in ElementTree.XML(results).iter("item"):
            processed_item = self.__process_item(item)
            if processed_item is not None:
                formatted_results.append(processed_item)

        return QueryResult(
            formatted_results,
            next_page_available=False
        )

    async def discover(self, last_check: datetime) -> List[SearchResultData]:
        if not self.session:
            self.session = AsyncSession()

        rss_results = await self.session.get_text(
            self._url + (self._api_path or ''),
            params={
                "t": "search",
                "apikey": self._api_key,
                "extended": 1,
                "q": "",
                "cat": str(self._categories or [])
            },
            quiet_fail=True
        )
        if not rss_results:
            return []

        formatted_results: List[SearchResultData] = []
        for item in ElementTree.XML(rss_results).iter("item"):
            processed_item = self.__process_item(item)
            if processed_item is None:
                continue

            date = item.findtext('pubDate')
            if not date:
                continue
            parsed_date = (
                datetime
                .strptime(date, "%a, %d %b %Y %H:%M:%S %z")
                .replace(tzinfo=None)
            )
            if last_check > parsed_date:
                continue

            formatted_results.append(processed_item)

        return formatted_results

    async def shutdown(self) -> None:
        if self.session:
            await self.session.close()
        return

    @classmethod
    def test(cls, url: str, **extra_fields: Any) -> None:
        api_path: str = extra_fields["api_path"]
        api_key: str = extra_fields["api_key"]

        with Session() as session:
            try:
                response = session.get(
                    url + (api_path or ''),
                    params={
                        "t": "caps",
                        "apikey": api_key
                    }
                )

            except RequestException:
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.status_code in (401, 403):
            raise CredentialInvalid

        if not response.ok:
            raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

        if response.headers["Content-Type"].split(";")[0] not in (
            "application/xml",
            "application/rss",
            "application/rss+xml"
        ):
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        root = ElementTree.XML(response.text)
        if (
            root.tag == "error"
            and 100 <= int(root.attrib.get("code") or -1) <= 107
        ):
            raise CredentialInvalid

        if root.tag != "caps":
            raise ClientNotWorking(BrokenClientReason.NOT_CLIENT_INSTANCE)

        return
