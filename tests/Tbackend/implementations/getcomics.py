import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.base.definitions import SearchQuery
from backend.implementations.indexer_clients.ddl.GetComics import \
    GetComicsIndexer

INDEXER_MODULE = "backend.implementations.indexer_clients.ddl.GetComics"


def _query(page: int) -> SearchQuery:
    return {
        "query": 'Example Series #19 (2024) & "special" / ?',
        "page": page,
        "total_available_variations": 1
    }


def _result_page(issue: int, next_page: bool) -> str:
    article = (
        '<article class="post">'
        '<a class="post-category">DC Comics</a>'
        '<h1 class="post-title">'
        f'<a href="https://getcomics.example/issue-{issue}/">'
        f'Example Series #{issue} (2024)</a></h1>'
        '<div><p>Size : 10 MB</p></div></article>'
    )
    pagination = (
        '<a class="page-numbers" href="/?s=example&amp;paged=2">2</a>'
        if next_page else '<span class="page-numbers current">2</span>'
    )
    return article + pagination


class getcomics_search(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        with patch(f"{INDEXER_MODULE}.BaseIndexerClient.__init__",
                   return_value=None):
            self.client = GetComicsIndexer(7)
        self.client._id = 7
        self.client._title = "Test GetComics"
        self.client._url = "https://getcomics.example"
        self.session = MagicMock()
        self.session.get_text = AsyncMock(return_value="")
        self.client.session = self.session

    async def test_search_url_and_query_parameters(self) -> None:
        """Use query pagination without altering the search term or caller data."""
        for base in (
            "https://getcomics.example",
            "https://getcomics.example/",
            "https://getcomics.example/catalog/"
        ):
            for page in (1, 2, 3):
                with self.subTest(base=base, page=page):
                    self.client._url = base
                    self.client.request_count = 0
                    self.session.get_text.reset_mock()
                    query = _query(page)
                    original = query.copy()

                    result = await self.client.search(query)

                    expected = {"s": query["query"]}
                    if page > 1:
                        expected["paged"] = page
                    self.session.get_text.assert_awaited_once_with(
                        base.rstrip('/') + '/',
                        params=expected,
                        quiet_fail=True
                    )
                    self.assertEqual(query, original)
                    self.assertEqual(result.results, [])
                    self.assertFalse(result.next_page_available)
                    self.assertEqual(self.client.request_count, 1)

    async def test_distinct_pages_preserve_results_and_pagination(self) -> None:
        """Parse each page and stop offering pages when the final one is current."""
        self.session.get_text.side_effect = [
            _result_page(1, True),
            _result_page(2, False)
        ]

        first = await self.client.search(_query(1))
        last = await self.client.search(_query(2))

        self.assertTrue(first.next_page_available)
        self.assertFalse(last.next_page_available)
        for issue, page in ((1, first), (2, last)):
            with self.subTest(issue=issue):
                self.assertEqual(len(page.results), 1)
                result = page.results[0]
                self.assertEqual(result["display_title"],
                                 f"Example Series #{issue} (2024)")
                self.assertEqual(result["link"],
                                 f"https://getcomics.example/issue-{issue}/")
                self.assertEqual(result["issue_number"], float(issue))
                self.assertEqual(result["size"], 10_000_000)
                self.assertEqual(result["indexer_id"], 7)
                self.assertEqual(result["indexer_title"], "Test GetComics")
                self.assertIsNone(result["seeders"])
                self.assertIsNone(result["leechers"])
        self.assertEqual(self.client.request_count, 2)

    async def test_search_initializes_session_when_needed(self) -> None:
        """Session creation should still be lazy."""
        self.client.session = None
        with patch(f"{INDEXER_MODULE}.AsyncSession",
                   return_value=self.session) as session_class:
            await self.client.search(_query(1))
        session_class.assert_called_once_with()
        self.assertIs(self.client.session, self.session)

    async def test_search_retains_existing_request_pacing(self) -> None:
        """Changing pagination must not remove the existing request delay."""
        self.client.request_count = 6
        with patch(f"{INDEXER_MODULE}.sleep", new_callable=AsyncMock) as delay:
            await self.client.search(_query(2))
        delay.assert_awaited_once_with(1.0)
        self.assertEqual(self.client.request_count, 7)

    async def test_discover_keeps_sitemap_url(self) -> None:
        """RSS discovery does not use search query pagination."""
        result = await self.client.discover(datetime(2026, 1, 1))
        self.session.get_text.assert_awaited_once_with(
            "https://getcomics.example/sitemap/",
            quiet_fail=True
        )
        self.assertEqual(result, [])
