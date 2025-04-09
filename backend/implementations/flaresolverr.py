# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping, Tuple, Union

from requests import RequestException

from backend.base.definitions import Constants
from backend.base.helpers import Session, Singleton
from backend.base.logging import LOGGER

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
        """Connect to a FlareSolverr instance.

        Args:
            base_url (str): The base URL of the FlareSolverr instance. Supply
            base URL without API extension.

        Returns:
            bool: Whether the connection was successful.
        """
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
        """
        If there was a connection to a FlareSolverr instance, disconnect.
        """
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

    def is_enabled(self) -> bool:
        """Check if FlareSolverr is enabled.

        Returns:
            bool: Whether FlareSolverr is enabled.
        """
        return bool(self.session_id and self.base_url)

    def get_ua_cookies(self, url: str) -> Tuple[str, Dict[str, str]]:
        """Get the user agent and cookies for a certain URL. The UA and cookies
        can be cleared by CF, so use them to avoid challenges. In case the URL
        is not CF protected, or hasn't explicitly been cleared yet, then the
        default UA is returned and no cookie definitions.

        Args:
            url (str): The URL to get the UA and cookies for.

        Returns:
            Tuple[str, Dict[str, str]]: First element is the UA, or default
            UA. Second element is a mapping of any extra cookies.
        """
        return (
            self.ua_mapping.get(url, Constants.DEFAULT_USERAGENT),
            self.cookie_mapping.get(url, {})
        )

    def handle_cf_block(
        self,
        url: str,
        headers: Mapping[str, str]
    ) -> Union[None, Dict[str, Any]]:
        """Let FS handle a URL to aquire cleared cookies and UA. These become
        available using `get_ua_cookies()` after this method completes.

        Args:
            url (str): The URL to clear.
            headers (Mapping[str, str]): The response headers from the
            (possibly) blocked request.

        Returns:
            Union[None, Dict[str, Any]]: None if FlareSolverr wasn't needed or
            couldn't solve the problem, or a dictionary with the FlareSolverr
            response.
        """
        if (
            headers.get(Constants.CF_CHALLENGE_HEADER[0])
            != Constants.CF_CHALLENGE_HEADER[1]
        ):
            # Request not failed because of CF block
            return

        if not (self.session_id and self.base_url):
            LOGGER.warning(
                "Request blocked by CloudFlare and FlareSolverr not setup"
            )
            return

        with Session() as session:
            result = session.post(
                self.base_url + self.api_base,
                json={
                    'cmd': 'request.get',
                    'session': self.session_id,
                    'url': url
                },
                headers={'Content-Type': 'application/json'}
            ).json()['solution']

            self.ua_mapping[url] = result["userAgent"]
            self.cookie_mapping[url] = {
                cookie["name"]: cookie["value"]
                for cookie in result["cookies"]
            }

        return result

    async def handle_cf_block_async(
        self,
        session: AsyncSession,
        url: str,
        headers: Mapping[str, str]
    ) -> Union[None, Dict[str, Any]]:
        """Let FS handle a URL to aquire cleared cookies and UA. These become
        available using `get_ua_cookies()` after this method completes.

        Args:
            session (AsyncSession): The session to make the request to FS with.
            url (str): The URL to clear.
            headers (Mapping[str, str]): The response headers from the
            (possibly) blocked request.

        Returns:
            Union[None, Dict[str, Any]]: None if FlareSolverr wasn't needed or
            couldn't solve the problem, or a dictionary with the FlareSolverr
            response.
        """
        if (
            headers.get(Constants.CF_CHALLENGE_HEADER[0])
            != Constants.CF_CHALLENGE_HEADER[1]
        ):
            # Request not failed because of CF block
            return

        if not (self.session_id and self.base_url):
            LOGGER.warning(
                "Request blocked by CloudFlare and FlareSolverr not setup"
            )
            return

        result = (await (await session.post(
            self.base_url + self.api_base,
            json={
                'cmd': 'request.get',
                'session': self.session_id,
                'url': url
            },
            headers={'Content-Type': 'application/json'}
        )).json())["solution"]

        self.ua_mapping[url] = result["userAgent"]
        self.cookie_mapping[url] = {
            cookie["name"]: cookie["value"]
            for cookie in result["cookies"]
        }

        return result
