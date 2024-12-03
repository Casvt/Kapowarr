# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Mapping, Tuple, Union

from requests import RequestException

from backend.base.definitions import Constants
from backend.base.helpers import Session, Singleton

if TYPE_CHECKING:
    from backend.base.helpers import AsyncSession


class FlareSolverr(metaclass=Singleton):
    cookie_mapping: Dict[str, Dict[str, str]] = {}
    ua_mapping: Dict[str, str] = {}

    def __init__(self) -> None:
        self.api_base = Constants.FS_API_BASE

        self.session_id: Union[str, None] = None
        self.base_url: Union[str, None] = None

        return

    def enable_flaresolverr(self, base_url: str) -> bool:
        with Session() as session:
            try:
                result = session.post(
                    base_url + self.api_base,
                    json={'cmd': 'sessions.create'},
                    headers={'Content-Type': 'application/json'}
                )

                if result.status_code != 200:
                    return False

                result = result.json()
                self.session_id = result["session"]
                self.base_url = base_url

            except RequestException:
                return False
        return True

    def disable_flaresolverr(self) -> None:
        if not (self.session_id and self.base_url):
            return

        with Session() as session:
            session.post(
                self.base_url + self.api_base,
                json={
                    'cmd': 'sessions.destroy',
                    'session': self.session_id
                },
                headers={'Content-Type': 'application/json'}
            )

        self.base_url = None
        self.session_id = None
        return

    def get_ua_cookies(self, url: str) -> Tuple[str, Dict[str, str]]:
        return (
            self.ua_mapping.get(url, Constants.DEFAULT_USERAGENT),
            self.cookie_mapping.get(url, {})
        )

    def handle_cf_block(
        self,
        url: str,
        headers: Mapping[str, str]
    ) -> None:
        if not (self.session_id and self.base_url):
            return

        if (
            headers.get(Constants.CF_CHALLENGE_HEADER[0])
            != Constants.CF_CHALLENGE_HEADER[1]
        ):
            # Request not failed because of CF block
            return

        with Session() as session:
            result = session.post(
                self.base_url + self.api_base,
                json={
                    'cmd': 'request.get',
                    'session': self.session_id,
                    'returnOnlyCookies': True,
                    'url': url
                },
                headers={'Content-Type': 'application/json'}
            ).json()['solution']

            self.ua_mapping[url] = result["userAgent"]
            self.cookie_mapping[url] = {
                cookie["name"]: cookie["value"]
                for cookie in result["cookies"]
            }

        return

    async def handle_cf_block_async(
        self,
        session: AsyncSession,
        url: str,
        headers: Mapping[str, str]
    ) -> None:
        if not (self.session_id and self.base_url):
            return

        if (
            headers.get(Constants.CF_CHALLENGE_HEADER[0])
            != Constants.CF_CHALLENGE_HEADER[1]
        ):
            # Request not failed because of CF block
            return

        result = (await (await session.post(
            self.base_url + self.api_base,
            json={
                'cmd': 'request.get',
                'session': self.session_id,
                'returnOnlyCookies': True,
                'url': url
            },
            headers={'Content-Type': 'application/json'}
        )).json())["solution"]

        self.ua_mapping[url] = result["userAgent"]
        self.cookie_mapping[url] = {
            cookie["name"]: cookie["value"]
            for cookie in result["cookies"]
        }

        return
