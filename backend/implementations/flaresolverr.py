# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Mapping, Tuple, Union

from requests import RequestException

from backend.base.definitions import Constants
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.internals.settings import Settings

if TYPE_CHECKING:
    from backend.base.helpers import AsyncSession


class FlareSolverr:
    cookie_mapping: Dict[str, Dict[str, str]] = {}
    ua_mapping: Dict[str, str] = {}

    def __init__(self) -> None:
        self.base_url = Settings().sv.flaresolverr_base_url or None
        return

    @staticmethod
    def __api_request(
        base_url: str,
        session: Session,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return session.post(
            base_url + Constants.FS_API_BASE,
            json=data,
            headers={'Content-Type': 'application/json'}
        ).json()

    @staticmethod
    async def __async_api_request(
        base_url: str,
        session: AsyncSession,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await (await session.post(
            base_url + Constants.FS_API_BASE,
            json=data,
            headers={'Content-Type': 'application/json'}
        )).json()

    @staticmethod
    def test_flaresolverr(base_url: str) -> bool:
        """Test the connection to a FlareSolverr instance.

        Args:
            base_url (str): The base URL of the FlareSolverr instance. Supply
                base URL without API extension.

        Returns:
            bool: Whether the connection was successful.
        """
        with Session() as session:
            try:
                result = session.get(f"{base_url}/health")

                if result.status_code != 200:
                    return False

                result = result.json()
                if result.get("status") != "ok":
                    return False

            except RequestException:
                return False
        return True

    def is_enabled(self) -> bool:
        """Check if FlareSolverr is enabled.

        Returns:
            bool: Whether FlareSolverr is enabled.
        """
        return self.base_url is not None

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

        if not self.base_url:
            LOGGER.warning(
                "Request blocked by CloudFlare and FlareSolverr not setup"
            )
            return

        with Session() as session:
            # The reason we manually create and close a session for one request
            # is that it's way faster than making just the request and letting
            # FS make the temporary session itself. Why it's so much faster to
            # make a session ourselves compared to FlareSolverr making it for
            # one request, I don't know. It's orders of magnitude faster.

            # Start session
            session_id = self.__api_request(
                self.base_url, session,
                {'cmd': 'sessions.create'}
            )["session"]

            # Get result
            result = self.__api_request(
                self.base_url, session,
                {
                    'cmd': 'request.get',
                    'session': session_id,
                    'url': url
                }
            )["solution"]

            # Close session
            self.__api_request(
                self.base_url, session,
                {
                    'cmd': 'sessions.destroy',
                    'session': session_id
                }
            )

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

        if not self.base_url:
            LOGGER.warning(
                "Request blocked by CloudFlare and FlareSolverr not setup"
            )
            return

        # Start session
        session_id = (await self.__async_api_request(
            self.base_url, session,
            {'cmd': 'sessions.create'}
        ))["session"]

        # Get result
        result = (await self.__async_api_request(
            self.base_url, session,
            {
                'cmd': 'request.get',
                'session': session_id,
                'url': url
            }
        ))["solution"]

        # Close session
        await self.__async_api_request(
            self.base_url, session,
            {
                'cmd': 'sessions.destroy',
                'session': session_id
            }
        )

        self.ua_mapping[url] = result["userAgent"]
        self.cookie_mapping[url] = {
            cookie["name"]: cookie["value"]
            for cookie in result["cookies"]
        }

        return result
