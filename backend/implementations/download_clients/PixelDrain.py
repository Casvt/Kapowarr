# -*- coding: utf-8 -*-

from base64 import b64encode
from typing import Union

from requests import RequestException, Response

from backend.base.custom_exceptions import (ClientNotWorking,
                                            CredentialInvalid,
                                            DownloadServiceRateLimitReached)
from backend.base.definitions import (BrokenClientReason, Constants,
                                      CredentialData, CredentialSource,
                                      DownloadClientIdentifier,
                                      DownloadService, StatusType)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.credentials import Credentials
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload
from backend.internals.status import StatusHandlers


@DownloadClients.register_client(DownloadClientIdentifier.PIXELDRAIN)
class PixelDrainDownload(BaseDirectDownload):
    @staticmethod
    def login(api_key: str) -> None:
        LOGGER.debug("Logging into Pixeldrain with user api key")
        with Session() as session:
            enc_api_key = b64encode(
                f":{api_key}".encode()
            ).decode()

            try:
                r = session.get(
                    Constants.PIXELDRAIN_API_URL + "/user",
                    headers={
                        "Authorization": "Basic " + enc_api_key
                    }
                )

            except RequestException:
                raise ClientNotWorking(BrokenClientReason.CONNECTION_ERROR)

            if r.status_code == 401:
                raise CredentialInvalid

            response = r.json()
            if (response["subscription"]["type"] or "free").lower() == "free":
                # Free account, so fetch standard rate limits
                limits = session.get(
                    Constants.PIXELDRAIN_API_URL + '/misc/rate_limits',
                    headers={
                        "Authorization": "Basic " + enc_api_key
                    }
                ).json()

                transfer_limit_used = limits["transfer_limit_used"]
                transfer_limit = limits["transfer_limit"]

            else:
                # Paid account, so grab transfer limits from user data
                transfer_limit_used = response["monthly_transfer_used"]
                transfer_limit = response["monthly_transfer_cap"]
                if transfer_limit == -1:
                    transfer_limit = float("inf")

        LOGGER.debug(
            f"Pixeldrain account transfer state: {transfer_limit_used}/{transfer_limit}"
        )
        if transfer_limit_used > transfer_limit:
            StatusHandlers().report(
                StatusType.DOWNLOAD_SERVICE_RATE_LIMIT,
                DownloadService.PIXELDRAIN.value
            )
            raise DownloadServiceRateLimitReached(DownloadService.PIXELDRAIN)
        return None

    def _convert_to_pure_link(self) -> str:
        self._api_key = None
        self._first_fetch = True
        download_id = self.download_link.rstrip("/").split("/")[-1]
        return Constants.PIXELDRAIN_API_URL + '/file/' + download_id

    def _fetch_pure_link(self, start_byte: Union[int, None] = None) -> Response:
        if self._first_fetch:
            cred = Credentials()
            for pd_cred in cred.get_from_source(CredentialSource.PIXELDRAIN):
                try:
                    # Let ClientNotWorking bubble up
                    self.login(pd_cred.api_key or '')

                except (CredentialInvalid, DownloadServiceRateLimitReached):
                    continue

                else:
                    # Key works and has not reached limit
                    self._api_key = pd_cred.api_key
                    break

            self._first_fetch = False

        headers = {}

        if start_byte is not None and self._supports_range_header:
            headers["Range"] = f"bytes={start_byte}-"

        if self._api_key:
            headers["Authorization"] = "Basic " + b64encode(
                f":{self._api_key}".encode()
            ).decode()

        return self._ssn.get(
            self.pure_link,
            headers=headers,
            stream=True
        )


@DownloadClients.register_client(DownloadClientIdentifier.PIXELDRAIN_FOLDER)
class PixelDrainFolderDownload(PixelDrainDownload):
    def _convert_to_pure_link(self) -> str:
        self._api_key = None
        self._first_fetch = True
        download_id = self.download_link.rstrip("/").split("/")[-1]
        return Constants.PIXELDRAIN_API_URL + '/list/' + download_id + '/zip'


@Credentials.register_validator(CredentialSource.PIXELDRAIN)
def pd_login_validator(credential_data: CredentialData) -> CredentialData:
    try:
        PixelDrainDownload.login(
            credential_data.api_key or ''
        )

    except DownloadServiceRateLimitReached:
        # Limit reached but credential working
        pass

    credential_data.email = None
    credential_data.username = None
    credential_data.password = None
    return credential_data
