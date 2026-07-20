# -*- coding: utf-8 -*-

from backend.base.definitions import (DownloadType, QueryBuilder,
                                      QueryKeys, SearchAction, SearchQuery,
                                      SpecialVersion)
from backend.implementations.query_builder_manager import QueryBuilders

TPB_FORMATS = (
    "{title} Vol. {volume_number} ({year}) TPB",
    "{title} ({year}) TPB",
    "{title} Vol. {volume_number} TPB",
    "{title}"
)

VAI_FORMATS = (
    "{title} ({year})",
    "{title}"
)

VOLUME_FORMATS = (
    "{title} ({year})",
    "{title} Vol. {volume_number} ({year})",
    "{title} Vol. {volume_number}",
    "{title}"
)

SPECIFIC_ISSUE_FORMATS = (
    "{title} #{issue_number} ({year})",
    "{title} #{issue_number}",
)

GENERAL_ISSUE_FORMATS = SPECIFIC_ISSUE_FORMATS + ("{title}",)


@QueryBuilders.register_builder(DownloadType.DDL)
class DDLQueryBuilder(QueryBuilder):
    def next_query(
        self,
        search_action: SearchAction,
        query_keys: QueryKeys
    ) -> SearchQuery:
        super()._update_state(search_action)

        if query_keys.special_version == SpecialVersion.TPB:
            queries = TPB_FORMATS

        elif query_keys.special_version == SpecialVersion.VOLUME_AS_ISSUE:
            queries = VAI_FORMATS

        elif query_keys.issue_number is None:
            queries = VOLUME_FORMATS

        elif self.originally_volume_search:
            queries = SPECIFIC_ISSUE_FORMATS

        else:
            queries = GENERAL_ISSUE_FORMATS

        query = queries[self.query_variation_index]

        if query_keys.year is None:
            query = query.replace('({year})', '').strip()

        result = query.format(
            title=query_keys.titles[self.alias_index],
            year=query_keys.year,
            volume_number=query_keys.volume_number,
            issue_number=query_keys.issue_number
        )

        return {
            "query": result,
            "page": self.page,
            "total_available_variations": len(queries)
        }
