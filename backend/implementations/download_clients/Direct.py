# -*- coding: utf-8 -*-

from backend.implementations.download_client_manager import DownloadClients
from backend.implementations.download_clients.base import BaseDirectDownload


@DownloadClients.register_client('direct')
class DirectDownload(BaseDirectDownload):
    ...
