# -*- coding: utf-8 -*-

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

SPECIFIC_VAI_ISSUE_FORMATS = (
    "{title} Vol {issue_number} ({year})",
    "{title} Vol {issue_number}"
)

GENERAL_VAI_ISSUE_FORMATS = SPECIFIC_VAI_ISSUE_FORMATS + ("{title}",)

SPECIFIC_ISSUE_FORMATS = (
    "{title} {issue_number}",
)

GENERAL_ISSUE_FORMATS = SPECIFIC_ISSUE_FORMATS + ("{title}",)


@QueryBuilders.register_builder(DownloadType.USENET)
class UsenetQueryBuilder(QueryBuilder):
    def _select_queries(self, query_keys: QueryKeys) -> Sequence[str]:
        if query_keys.special_version == SpecialVersion.TPB:
            return TPB_FORMATS

        elif query_keys.issue_number is None:
            if query_keys.special_version == SpecialVersion.VOLUME_AS_ISSUE:
                return VAI_FORMATS
            else:
                return VOLUME_FORMATS

        elif self.originally_volume_search:
            if query_keys.special_version == SpecialVersion.VOLUME_AS_ISSUE:
                return SPECIFIC_VAI_ISSUE_FORMATS
            else:
                return SPECIFIC_ISSUE_FORMATS

        else:
            if query_keys.special_version == SpecialVersion.VOLUME_AS_ISSUE:
                return GENERAL_VAI_ISSUE_FORMATS
            else:
                return GENERAL_ISSUE_FORMATS

    def next_query(
        self,
        search_action: SearchAction,
        query_keys: QueryKeys
    ) -> SearchQuery:
        if query_keys.issue_number and query_keys.issue_number.isdigit():
            query_keys.issue_number = query_keys.issue_number.zfill(3)

        return super().next_query(search_action, query_keys)
