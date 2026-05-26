# -*- coding: utf-8 -*-

from backend.base.custom_exceptions import DownloadLinkBroken
from backend.base.definitions import DownloadClientIdentifier
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload

WETRANSFER_API_LINK = "https://wetransfer.com/api/v4/transfers/{transfer_id}/download"


@DownloadClients.register_client(DownloadClientIdentifier.WETRANSFER)
class WeTransferDownload(BaseDirectDownload):
    def _convert_to_pure_link(self) -> str:
        transfer_id, security_hash = self.download_link.split("/")[-2:]
        r = self._ssn.post(
            WETRANSFER_API_LINK.format(transfer_id=transfer_id),
            json={
                "intent": "entire_transfer",
                "security_hash": security_hash
            },
            headers={"x-requested-with": "XMLHttpRequest"}
        )
        if not r.ok:
            raise DownloadLinkBroken(self.download_link)

        direct_link = r.json().get("direct_link")

        if not direct_link:
            raise DownloadLinkBroken(self.download_link)

        return direct_link
