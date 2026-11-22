# -*- coding: utf-8 -*-

"""
Query builder for Newznab (usenet) indexers. Newznab searches match on words,
so the queries use plain words: no '#' or parentheses. Release names usually
pad issue numbers ("Series 039 (2020)"), so issue searches try both the padded
and the plain number.
"""

from typing import Sequence

from backend.base.definitions import (DownloadType, QueryBuilder,
                                      QueryKeys, SearchAction, SearchQuery,
                                      SpecialVersion)
from backend.implementations.query_builder_manager import QueryBuilders

VOLUME_FORMATS = (
    "{title} {year}",
    "{title} Vol {volume_number}",
    "{title}"
)

TPB_FORMATS = (
    "{title} Vol {volume_number} TPB",
    "{title} TPB",
    "{title} {year}",
    "{title}"
)

VAI_FORMATS = (
    "{title} {year}",
    "{title}"
)

SPECIFIC_ISSUE_FORMATS = (
    "{title} {padded_issue_number}",
    "{title} {issue_number}",
)

GENERAL_ISSUE_FORMATS = SPECIFIC_ISSUE_FORMATS + ("{title}",)


def _padded(issue_number: str) -> str:
    "Pad a whole issue number to three digits, like release names do"
    if issue_number.isdigit():
        return issue_number.zfill(3)
    return issue_number


@QueryBuilders.register_builder(DownloadType.USENET)
class UsenetQueryBuilder(QueryBuilder):
    def _select_queries(self, query_keys: QueryKeys) -> Sequence[str]:
        if query_keys.special_version == SpecialVersion.TPB:
            return TPB_FORMATS

        elif query_keys.special_version == SpecialVersion.VOLUME_AS_ISSUE:
            return VAI_FORMATS

        elif query_keys.issue_number is None:
            return VOLUME_FORMATS

        if self.originally_volume_search:
            queries = SPECIFIC_ISSUE_FORMATS
        else:
            queries = GENERAL_ISSUE_FORMATS

        if _padded(query_keys.issue_number) == query_keys.issue_number:
            # The padded variation equals the plain one (e.g. issue 100)
            queries = tuple(
                q
                for q in queries
                if "{padded_issue_number}" not in q
            )
        return queries

    def next_query(
        self,
        search_action: SearchAction,
        query_keys: QueryKeys
    ) -> SearchQuery:
        self._update_state(search_action)

        queries = self._select_queries(query_keys)
        query = queries[min(self.query_variation_index, len(queries) - 1)]

        if query_keys.issue_number is None:
            year = query_keys.year
        else:
            year = query_keys.issue_year or query_keys.year
        if year is None:
            query = query.replace('{year}', '')

        issue_number = query_keys.issue_number or ''
        result = query.format(
            title=query_keys.titles[self.alias_index],
            year=year,
            volume_number=query_keys.volume_number,
            issue_number=issue_number,
            padded_issue_number=_padded(issue_number)
        )

        return {
            "query": " ".join(result.split()),
            "page": self.page,
            "total_available_variations": len(queries)
        }
