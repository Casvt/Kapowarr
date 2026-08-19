# -*- coding: utf-8 -*-

from __future__ import annotations

from asyncio import Semaphore
from datetime import datetime, timezone
from time import time
from typing import TYPE_CHECKING, Any, Dict, Mapping, Tuple, Union
from urllib.parse import urlparse

from requests import RequestException

from backend.base.definitions import Constants, ProxyType, StatusType
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.internals.settings import Settings
from backend.internals.status import StatusHandlers

if TYPE_CHECKING:
    from backend.base.helpers import AsyncSession


class FSCache:
    cookie_mapping: Dict[str, Tuple[str, float]] = {}
    ua_mapping: Dict[str, str] = {}

    @staticmethod
    def _build_cookie(cookie: Dict[str, Any]) -> str:
        result = f"{cookie['value']}; SameSite={cookie['sameSite']}; Partitioned"
        if cookie["httpOnly"]:
            result += "; HttpOnly"
        if cookie["secure"]:
            result += "; Secure"
        if cookie["path"]:
            result += f"; Path={cookie['path']}"
        if cookie["domain"]:
            result += f"; Domain={cookie['domain'].lstrip('.')}"
        if cookie["expiry"]:
            timestamp = datetime.fromtimestamp(
                cookie["expiry"], tz=timezone.utc
            )
            result += f"; Expires={timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')}"
        return result

    @classmethod
    def get_ua_cookies(cls, url: str) -> Tuple[str, str]:
        """Get the user agent and cookies for a certain URL. The UA and cookies
        can be cleared by CF, so use them to avoid challenges. In case the URL
        is not CF protected, or hasn't explicitly been cleared yet, then the
        default UA is returned and no cookie definitions.

        Args:
            url (str): The URL to get the UA and cookie for.

        Returns:
            Tuple[str, str]: First element is the UA, or default UA. Second
                element is the clearance cookie value.
        """
        domain = urlparse(url).netloc

        ua = cls.ua_mapping.get(domain, Constants.DEFAULT_USERAGENT)
        cookie = cls.cookie_mapping.get(domain, ('', 0.0))

        if cookie[0] and time() > cookie[1]:
            # Expired
            cls.ua_mapping.pop(domain, None)
            cls.cookie_mapping.pop(domain, None)
            ua = Constants.DEFAULT_USERAGENT
            cookie = ('', 0.0)

        return (ua, cookie[0])

    @classmethod
    def set_ua_cookies(cls, url: str, fs_response: Dict[str, Any]) -> None:
        """Cache the user agent and cookies for CF clearance.

        Args:
            url (str): The URL that the clearance is for.
            fs_response (Dict[str, Any]): The response from FS.
        """
        domain = urlparse(url).netloc
        for cookie in fs_response["cookies"]:
            if cookie["name"] == "cf_clearance":
                cls.ua_mapping[domain] = fs_response["userAgent"]
                cls.cookie_mapping[domain] = (
                    cls._build_cookie(cookie),
                    cookie["expiry"]
                )
                break

        return


class FlareSolverr:
    def __init__(self) -> None:
        settings = Settings().sv
        self.session_semaphore: Union[Semaphore, None] = None

        self.base_url = settings.flaresolverr_base_url or None

        self.proxy_data: Union[Dict[str, Any], None] = None
        if settings.proxy_type != ProxyType.NONE:
            self.proxy_data = {
                "proxy": {
                    "url": "%s://%s:%d" % (
                        settings.proxy_type.value.rstrip('h'),
                        settings.proxy_host, settings.proxy_port
                    )
                }
            }
            if settings.proxy_username and settings.proxy_password:
                self.proxy_data["proxy"]["username"] = settings.proxy_username
                self.proxy_data["proxy"]["password"] = settings.proxy_password

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
            headers={'Content-Type': 'application/json'},
            timeout=Constants.REQUEST_TIMEOUT + Constants.FS_RESOLVE_TIMEOUT
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
            headers={'Content-Type': 'application/json'},
            timeout=Constants.REQUEST_TIMEOUT + Constants.FS_RESOLVE_TIMEOUT
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

    def get_ua_cookies(self, url: str) -> Tuple[str, str]:
        """Get the user agent and cookies for a certain URL. The UA and cookies
        can be cleared by CF, so use them to avoid challenges. In case the URL
        is not CF protected, or hasn't explicitly been cleared yet, then the
        default UA is returned and no cookie definitions.

        Args:
            url (str): The URL to get the UA and cookie for.

        Returns:
            Tuple[str, str]: First element is the UA, or default UA. Second
                element is the clearance cookie value.
        """
        return FSCache.get_ua_cookies(url)

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
            StatusHandlers().report(StatusType.CF_CHALLENGE_WITH_NO_FS, '')
            return

        with Session() as session:
            result = self.__api_request(
                self.base_url, session,
                {
                    'cmd': 'request.get',
                    'url': url,
                    'maxTimeout': Constants.FS_RESOLVE_TIMEOUT * 1000,
                    **(self.proxy_data or {})
                }
            )["solution"]

        if result["response"] is None:
            # FlareSolverr responded, but content of
            # returned webpage is empty.
            return

        FSCache.set_ua_cookies(url, result)

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
            StatusHandlers().report(StatusType.CF_CHALLENGE_WITH_NO_FS, '')
            return

        # Technically this makes it a max amount of FS sessions per AsyncSession
        # instance, but in most cases the application only has one AsyncSession
        # running at any point in time.
        if self.session_semaphore is None:
            self.session_semaphore = Semaphore(
                Constants.MAX_CONCURRENT_FS_SESSIONS
            )

        async with self.session_semaphore:
            result = (await self.__async_api_request(
                self.base_url, session,
                {
                    'cmd': 'request.get',
                    'url': url,
                    'maxTimeout': Constants.FS_RESOLVE_TIMEOUT * 1000,
                    **(self.proxy_data or {})
                }
            ))["solution"]

        if result["response"] is None:
            # FlareSolverr responded, but content of
            # returned webpage is empty.
            return

        FSCache.set_ua_cookies(url, result)

        return result
