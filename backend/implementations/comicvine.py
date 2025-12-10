# -*- coding: utf-8 -*-

"""
Search for volumes/issues and fetch metadata for them on ComicVine
"""

from asyncio import gather, run, sleep
from json import JSONDecodeError
from re import IGNORECASE, compile
from typing import Any, Dict, List, Sequence, Union

from aiohttp import ContentTypeError
from aiohttp.client_exceptions import ClientError
from bs4 import BeautifulSoup, Tag

from backend.base.custom_exceptions import (CVRateLimitReached,
                                            InvalidComicVineApiKey,
                                            VolumeNotMatched)
from backend.base.definitions import (Constants, FilenameData,
                                      IssueMetadata, T, VolumeMetadata)
from backend.base.file_extraction import (extract_issue_number,
                                          extract_volume_number, volume_regex)
from backend.base.helpers import (AsyncSession, DictKeyedDict, Session,
                                  batched, force_range, force_suffix,
                                  normalise_string, normalise_year,
                                  to_full_string_cv_id, to_string_cv_id)
from backend.base.logging import LOGGER
from backend.implementations.matching import (
    match_title, select_best_volume_result_for_file)
from backend.internals.db import get_db
from backend.internals.settings import Settings

translation_regex = compile(
    r'^<p>\s*\w+(?<!English) publication(\.?</p>$|,\s| \(in the \w+(?<!English) language\)|, translates )|' +
    r'^<p>\s*published by the \w+(?<!English) wing of|' +
    r'^<p>\s*\w+(?<!English) translations? of|' +
    r'.*from \w+(?<!English)\.?</p>$|' +
    r'^<p>\s*publishes in \w+(?<!English)|' +
    r'^<p>\s*\w+(?<!English) language|' +
    r'^<p>\s*\w+(?<!English) edition of|' +
    r'^<p>\s*\w+(?<!English) reprint of|' +
    r'^<p>\s*\w+(?<!English) trade collection of|' +
    r'^<p>\s*Series of \w+(?<!English) collections\.?</p>$|' +
    r'.*reprints\.?</p>$',
    IGNORECASE)
headers = {'h2', 'h3', 'h4', 'h5', 'h6'}
lists = {'ul', 'ol'}


def _clean_description(description: str, short: bool = False) -> str:
    """Reduce the size of the volume/issue description (written in html) to only
    essential information. Removes images, lists (e.g. of authors), and fixes
    links that have a relative URL.

    Args:
        description (str): The description to clean.
        short (bool, optional): Only remove images and fix links.
            Defaults to False.

    Returns:
        str: The cleaned description.
    """
    if not description:
        return description

    soup = BeautifulSoup(description, 'html.parser')

    # Remove images
    for el in soup.find_all(["figure", "img"]):
        el.decompose()

    # Remove practically empty paragraphs
    for el in soup.find_all(["p"]):
        if not el.text.lstrip('.').strip():
            el.decompose()

    if not short:
        # Remove everything after the first title with list
        removed_elements = []
        for el in soup:
            if not isinstance(el, Tag):
                continue

            elif el.name is None:
                continue

            elif (
                removed_elements
                or el.name in headers
            ):
                removed_elements.append(el)

            elif el.name in lists:
                removed_elements.append(el)
                prev_sib = el.previous_sibling
                if (
                    prev_sib is not None
                    and prev_sib.text.endswith(':')
                ):
                    removed_elements.append(prev_sib)

            elif el.name == 'p':
                children = list(getattr(el, 'children', []))
                if (
                    1 <= len(children) <= 2
                    and children[0].name in ('b', 'i', 'strong')
                ):
                    removed_elements.append(el)

        for el in removed_elements:
            if isinstance(el, Tag):
                el.decompose()

    # Fix links
    for link in soup.find_all('a'):
        link: Tag
        link.attrs = {
            k: v
            for k, v in link.attrs.items()
            if not k.startswith('data-')
        }
        link['target'] = '_blank'
        link['href'] = link.attrs.get('href', '').lstrip('.').lstrip('/')
        if not link.attrs.get('href', 'http').startswith('http'):
            link['href'] = (
                Constants.CV_SITE_URL + '/' + link.attrs.get('href', '')
            )

    result = str(soup)
    return result


class ComicVine:
    volume_field_list = ','.join((
        'aliases',
        'count_of_issues',
        'deck',
        'description',
        'id',
        'image',
        'issues',
        'name',
        'publisher',
        'site_detail_url',
        'start_year'
    ))
    issue_field_list = ','.join((
        'id',
        'issue_number',
        'name',
        'cover_date',
        'store_date',
        'description',
        'volume'
    ))
    search_field_list = ','.join((
        'aliases',
        'count_of_issues',
        'deck',
        'description',
        'id',
        'image',
        'name',
        'publisher',
        'site_detail_url',
        'start_year'
    ))

    def __init__(self, comicvine_api_key: Union[str, None] = None) -> None:
        """Start interacting with ComicVine.

        Args:
            comicvine_api_key (Union[str, None], optional): Instead of using the
                CV API key set in the settings, use the supplied one.
                Defaults to None.

        Raises:
            InvalidComicVineApiKey: No ComicVine API key is set in the settings
                and no key is given.
        """
        settings = Settings().get_settings()

        self.date_type = settings.date_type.value
        api_key = comicvine_api_key or settings.comicvine_api_key
        if not api_key:
            raise InvalidComicVineApiKey

        self.ssn = Session()
        self._params = {'format': 'json', 'api_key': api_key}
        self.ssn.params.update(self._params) # type: ignore
        return

    async def __call_api(
        self,
        session: AsyncSession,
        url_path: str,
        params: Dict[str, Any] = {},
        default: Union[T, None] = None
    ) -> Union[Dict[str, Any], T]:
        """Make an API call asynchronously (with error handling).

        Args:
            session (AsyncSession): The session to make the request with.

            url_path (str): The API endpoint to make the call to.
                For example: '/volumes'.

            params (Dict[str, Any], optional): The URL parameters that should go
                with the request. The standard parameters (api_key and format)
                are already included.
                Defaults to {}.

            default (Union[T, None], optional): Return given value in case of
                exception, instead of raising exception.
                Defaults to None.

        Raises:
            CVRateLimitReached: The rate limit for this endpoint has been
                reached, and no `default` was supplied.
            InvalidComicVineApiKey: The API key is not valid.
            VolumeNotMatched: The ID doesn't map to any volume.

        Returns:
            Union[Dict[str, Any], T]: The raw API response or the value of
                `default` on error.
        """
        url_path = force_suffix('/' + url_path.lstrip('/'), '/')

        try:
            response = await session.get(
                Constants.CV_API_URL + url_path,
                params={**self._params, **params}
            )
            result: Dict[str, Any] = await response.json()

            if result['status_code'] == 107:
                raise ClientError
            elif result['status_code'] == 101:
                raise VolumeNotMatched
            elif result['status_code'] == 100:
                raise InvalidComicVineApiKey

            return result

        except (ClientError, ContentTypeError, JSONDecodeError):
            if default is not None:
                return default
            raise CVRateLimitReached

    def __format_volume_output(
        self,
        volume_data: Dict[str, Any]
    ) -> VolumeMetadata:
        """Format the API output containing the metadata of a volume.

        Args:
            volume_data (Dict[str, Any]): The API output.

        Returns:
            VolumeMetadata: The formatted data.
        """
        # Determine volume number
        volume_result = volume_regex.search(volume_data['deck'] or '')
        if volume_result:
            volume_number = force_range(extract_volume_number(
                volume_result.group(1)
            ))[0]
            if volume_number is None:
                volume_number = 1
        else:
            volume_number = 1

        # Determine description
        description = _clean_description(volume_data['description'])

        # Determine translation value
        translated = translation_regex.match(
            description or ''
        ) is not None

        result: VolumeMetadata = {
            'comicvine_id': int(volume_data['id']),
            'title': normalise_string(volume_data['name'] or ''),
            'year': normalise_year(volume_data.get('start_year', '')),
            'volume_number': volume_number,
            'cover_link': volume_data['image']['small_url'],
            'cover': None,
            'description': description,
            'site_url': volume_data['site_detail_url'],

            'aliases': [
                a.strip()
                for a in (volume_data.get('aliases') or '').split('\r\n')
                if a
            ],

            'publisher': (
                volume_data.get('publisher') or {}
            ).get('name'),

            'issue_count': int(volume_data['count_of_issues']),

            'translated': translated,
            'already_added': None, # Only used when searching
            'issues': None # Only used for certain fetches
        }

        return result

    def __format_issue_output(
        self,
        issue_data: Dict[str, Any]
    ) -> IssueMetadata:
        """Format the API output containing the metadata of the issue.

        Args:
            issue_data (Dict[str, Any]): The API output.

        Returns:
            IssueMetadata: The formatted data.
        """
        calculated_issue_number = force_range(extract_issue_number(
            issue_data['issue_number']
        ))[0]
        if calculated_issue_number is None:
            calculated_issue_number = 0.0

        result: IssueMetadata = {
            'comicvine_id': int(issue_data['id']),
            'volume_id': int(issue_data['volume']['id']),
            'issue_number': issue_data['issue_number'].replace('/', '-').strip(),
            'calculated_issue_number': calculated_issue_number,
            'title': normalise_string(issue_data['name'] or '') or None,
            'date': issue_data[self.date_type] or None,
            'description': _clean_description(
                issue_data['description'],
                short=True
            )
        }

        return result

    def __format_search_output(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[VolumeMetadata]:
        """Format the API output containing volume search results.

        Args:
            search_results (List[Dict[str, Any]]): The API output.

        Returns:
            List[VolumeMetadata]: The formatted data.
        """
        cursor = get_db()

        formatted_results = [
            self.__format_volume_output(r)
            for r in search_results
        ]

        # Mark entries that are already added
        volume_ids: Dict[int, int] = dict(cursor.execute(f"""
            SELECT comicvine_id, id
            FROM volumes
            WHERE comicvine_id IN ({','.join('?' for _ in formatted_results)})
            LIMIT 50;
            """,
            tuple(r["comicvine_id"] for r in formatted_results)
        ))

        for r in formatted_results:
            r['already_added'] = volume_ids.get(r["comicvine_id"])

        LOGGER.debug(
            'Searching for volumes with query result: %s',
            formatted_results
        )
        return formatted_results

    def test_key(self) -> bool:
        """Test if the API key works.

        Returns:
            bool: Whether the key works.
        """
        async def _test_key():
            try:
                async with AsyncSession() as session:
                    # Simply make a call to any endpoint to check. This endpoint
                    # isn't used by Kapowarr so by using it now we don't
                    # unnecessarily get closer to the rate limit of
                    # important endpoints.
                    await self.__call_api(
                        session,
                        '/publisher/4010-31',
                        {'field_list': 'id'}
                    )

            except (CVRateLimitReached, InvalidComicVineApiKey):
                return False

            return True

        return run(_test_key())

    async def fetch_volume(self, cv_id: Union[str, int]) -> VolumeMetadata:
        """Get the metadata of a volume, including its issues.

        Args:
            cv_id (Union[str, int]): The CV ID of the volume.

        Raises:
            VolumeNotMatched: The ID doesn't map to any volume.
            CVRateLimitReached: The ComicVine rate limit is reached.
            InvalidComicVineApiKey: The API key is not valid.

        Returns:
            VolumeMetadata: The metadata of the volume, including issues.
        """
        try:
            cv_id = to_full_string_cv_id((cv_id,))[0]
        except ValueError:
            raise VolumeNotMatched

        LOGGER.debug(f'Fetching volume data for {cv_id}')

        async with AsyncSession() as session:
            result = await self.__call_api(
                session,
                f'/volume/{cv_id}',
                {'field_list': self.volume_field_list}
            )

            volume_info = self.__format_volume_output(result['results'])
            volume_info['issues'] = await self.fetch_issues((cv_id,))

            LOGGER.debug('Fetching volume data result: %s', volume_info)

            volume_info['cover'] = await session.get_content(
                volume_info['cover_link'],
                quiet_fail=True
            ) or None

            return volume_info

    async def fetch_volumes(
        self,
        cv_ids: Sequence[Union[str, int]]
    ) -> List[VolumeMetadata]:
        """Get the metadata of the volumes, without their issues.

        Args:
            cv_ids (Sequence[Union[str, int]]): The CV IDs of the volumes.

        Raises:
            VolumeNotMatched: An ID doesn't map to any volume.
            InvalidComicVineApiKey: The API key is not valid.

        Returns:
            List[VolumeMetadata]: The metadata of the volumes, without issues.
                The list of volumes could be incomplete if the rate limit was
                reached.
        """
        try:
            formatted_cv_ids = to_string_cv_id(cv_ids)
        except ValueError:
            raise VolumeNotMatched

        LOGGER.debug(f'Fetching volume data for {formatted_cv_ids}')

        # Each request to CV can return 100 volumes. Make 10 requests at the
        # same time (one batch). Wait/cooldown in between batches. Spending time
        # fetching covers immediately after each batch increases cooldown.
        volume_infos = []
        batch_brake_time = Constants.CV_BRAKE_TIME * 10
        async with AsyncSession() as session:
            for i, request_batch in enumerate(batched(formatted_cv_ids, 1000)):

                if i:
                    LOGGER.debug(
                        "Waiting %ss to keep the CV rate limit happy",
                        batch_brake_time
                    )
                    await sleep(batch_brake_time)

                tasks = (
                    self.__call_api(
                        session,
                        '/volumes',
                        {
                            'field_list': self.volume_field_list,
                            'filter': f'id:{"|".join(id_batch)}'
                        },
                        {'results': []}
                    )
                    for id_batch in batched(request_batch, 100)
                )
                responses = await gather(*tasks)

                # Format volume responses and prep cover requests
                batch_volumes: List[VolumeMetadata] = [
                    self.__format_volume_output(result)
                    for batch in responses
                    for result in batch['results']
                ]
                cover_map: Dict[int, Any] = {
                    volume['comicvine_id']: session.get_content(
                        volume['cover_link'],
                        quiet_fail=True
                    )
                    for volume in batch_volumes
                }

                # Fetch covers and add them to the volume info
                cover_responses = dict(zip(
                    cover_map.keys(),
                    await gather(*cover_map.values())
                ))
                for volume in batch_volumes:
                    volume['cover'] = cover_responses.get(
                        volume['comicvine_id']
                    ) or None

                volume_infos.extend(batch_volumes)

            return volume_infos

    async def fetch_issues(
        self,
        cv_ids: Sequence[Union[str, int]]
    ) -> List[IssueMetadata]:
        """Get the metadata of the issues of volumes.

        Args:
            cv_ids (Sequence[Union[str, int]]): The CV IDs of the volumes.

        Raises:
            VolumeNotMatched: An ID doesn't map to any volume.
            InvalidComicVineApiKey: The API key is not valid.

        Returns:
            List[IssueMetadata]: The metadata of all the issues inside the
                volumes. The list of issues could be incomplete if the rate
                limit was reached.
        """
        try:
            formatted_cv_ids = to_string_cv_id(cv_ids)
        except ValueError:
            raise VolumeNotMatched

        LOGGER.debug(f'Fetching issue data for volumes {formatted_cv_ids}')

        issue_infos = []
        batch_brake_time = Constants.CV_BRAKE_TIME * 10
        async with AsyncSession() as session:
            for id_batch in batched(formatted_cv_ids, 50):
                batch_filter = "|".join(id_batch)
                try:
                    results = await self.__call_api(
                        session,
                        '/issues',
                        {
                            'field_list': self.issue_field_list,
                            'filter': f'volume:{batch_filter}'
                        }
                    )

                except CVRateLimitReached:
                    break

                issue_infos.extend((
                    self.__format_issue_output(r)
                    for r in results['results']
                ))

                if results['number_of_total_results'] > 100:

                    for i, offset_batch in enumerate(batched(
                        range(100, results['number_of_total_results'], 100),
                        10
                    )):

                        if i:
                            LOGGER.debug(
                                "Waiting %ss to keep the CV rate limit happy",
                                batch_brake_time
                            )
                            await sleep(batch_brake_time)

                        tasks = (
                            self.__call_api(
                                session,
                                '/issues',
                                {
                                    'field_list': self.issue_field_list,
                                    'filter': f'volume:{batch_filter}',
                                    'offset': offset
                                },
                                {'results': []}
                            )
                            for offset in offset_batch
                        )
                        responses = await gather(*tasks)

                        for batch in responses:
                            issue_infos.extend((
                                self.__format_issue_output(r)
                                for r in batch['results']
                            ))

            return issue_infos

    async def __search_volume(
        self, query: str
    ) -> List[Dict[str, Any]]:
        try:
            query = to_full_string_cv_id((query,))[0]

        except ValueError:
            return []

        async with AsyncSession() as session:
            result = await self.__call_api(
                session,
                f'/volume/{query}',
                {'field_list': self.search_field_list}
            )
            return [result['results']]

    async def __search_query(
        self, query: str
    ) -> List[Dict[str, Any]]:
        async with AsyncSession() as session:
            results = await self.__call_api(
                session,
                '/search',
                {
                    'query': query,
                    'resources': 'volume',
                    'limit': 50,
                    'field_list': self.search_field_list
                },
                {'results': []}
            )
            return results['results']

    async def search_volumes(
        self,
        query: str
    ) -> List[VolumeMetadata]:
        """Search for volumes.

        Args:
            query (str): The query to use when searching.

        Raises:
            CVRateLimitReached: The rate limit for this endpoint has been reached.
            InvalidComicVineApiKey: The API key is not valid.

        Returns:
            List[VolumeMetadata]: The search results.
        """
        LOGGER.debug(f'Searching for volumes with the query {query}')

        try:
            if query.startswith(('4050-', 'cv:')):
                results = await self.__search_volume(query)
            else:
                results = await self.__search_query(query)

        except VolumeNotMatched:
            return []

        if not results:
            return []

        return self.__format_search_output(results)

    async def filenames_to_cvs(self,
        file_datas: Sequence[FilenameData],
        only_english: bool
    ) -> DictKeyedDict:
        """Match filenames to CV volumes.

        Args:
            file_datas (Sequence[FilenameData]): The filename data to find CV
                volumes for.
            only_english (bool): Only match to english volumes.

        Returns:
            DictKeyedDict: A map of the filename to its CV match.
        """
        matches = DictKeyedDict()

        # If multiple filenames have the same series title, avoid searching for
        # it multiple times. Instead search for all unique titles and then later
        # match the filename back to the title's search results. This makes it
        # one search PER SERIES TITLE instead of one search PER FILENAME.
        titles_to_files: Dict[str, List[FilenameData]] = {}
        for file_data in file_datas:
            (titles_to_files
                .setdefault(file_data['series'].lower(), [])
                .append(file_data)
            )

        # Titles to search results
        responses = await gather(
            *(
                self.search_volumes(title)
                for title in titles_to_files
            ),
            return_exceptions=True
        )

        # Filter for each title: title, only_english
        titles_to_results: Dict[str, List[VolumeMetadata]] = {}
        for title, response in zip(titles_to_files, responses):
            if isinstance(response, CVRateLimitReached):
                # Rate limit
                continue

            elif isinstance(response, BaseException):
                raise response

            titles_to_results[title] = [
                r for r in response
                if match_title(title, r['title'])
                and (
                    only_english and not r['translated']
                    or
                    not only_english
                )
            ]

        for title, files in titles_to_files.items():
            for file in files:
                result = select_best_volume_result_for_file(
                    file, titles_to_results[title]
                )

                if result is None:
                    matches[file] = {
                        'id': None,
                        'title': None,
                        'issue_count': None,
                        'link': None
                    }

                else:
                    matches[file] = {
                        'id': result['comicvine_id'],
                        'title': f"{result['title']} ({result['year']})",
                        'issue_count': result['issue_count'],
                        'link': result['site_url']
                    }

        return matches
