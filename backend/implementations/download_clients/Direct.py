# -*- coding: utf-8 -*-

from backend.base.definitions import DownloadClientIdentifier
from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload


@DownloadClients.register_client(DownloadClientIdentifier.DIRECT)
class DirectDownload(BaseDirectDownload):
    ...
