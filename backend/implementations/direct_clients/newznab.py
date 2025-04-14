# -*- coding: utf-8 -*-

"""
Newznab client implementation for Kapowarr.
"""

from __future__ import annotations

import re

import xml.etree.ElementTree as ET
from os.path import join, basename
from threading import Event
from time import time, perf_counter
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.parse

from backend.base.custom_exceptions import ClientNotWorking, LinkBroken
from backend.base.definitions import (
    BlocklistReason, Constants, CredentialSource, DownloadSource, DownloadType
)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.credentials import Credentials
from backend.implementations.external_clients import ExternalClients


class NewznabABC:
    """Abstract base class for Newznab operations."""
    size: int
    progress: float
    speed: float
    pure_link: str
    file_name: str

    def __init__(self, download_link: str) -> None:
        """Initialize Newznab client with download link.
        
        Args:
            download_link (str): The NZB download link
        """
        pass

    def download(
        self,
        filename: str,
        websocket_updater: Callable[[], Any]
    ) -> None:
        """Download the NZB and content.
        
        Args:
            filename (str): Path where to save the downloaded file
            websocket_updater (Callable[[], Any]): Function to call to update websocket status
        """
        pass

    def stop(self) -> None:
        """Stop the download."""
        pass


class NewznabClient(NewznabABC):
    """Client for handling Newznab API interactions."""
    
    def __init__(self, download_link: str) -> None:
        """Initialize the Newznab client.
        
        Args:
            download_link (str): NZB download link
        """
        LOGGER.debug(f"Initializing NewznabClient with download link: {download_link}")
        
        self.download_link = download_link
        self.pure_link = download_link
        self.__r = None
        
        self.downloading: bool = False
        self.progress = 0.0
        self.speed = 0.0
        self.size = 0

        self._get_credentials()
        
        self._fetch_nzb_metadata()
        
        return

    
    def _get_credentials(self) -> None:
        """Get the Newznab API credentials."""
        from backend.internals.db import get_db
        
        self.api_key = None
        self.api_url = None
        
        host = urllib.parse.urlparse(self.download_link).netloc
        
        db = get_db()
        indexer = db.execute(
            'SELECT url, api_key FROM indexers WHERE type = "newznab" AND enabled = 1 AND url LIKE ?',
            (f"%{host}%",)
        ).fetchone()
        
        if indexer:
            self.api_url = indexer['url']
            self.api_key = indexer['api_key']
        else:
            LOGGER.warning(f"No Newznab indexer found for {host}")
            
        return

    def _fetch_nzb_metadata(self) -> None:
        """Fetch metadata about the NZB file."""
        try:
            with Session() as session:
                url = self.download_link
                LOGGER.debug(f"Fetching NZB metadata from URL: {url}")
                
                head_response = session.head(url)
                if head_response.status_code != 200:
                    raise ClientNotWorking(f"Failed to get NZB metadata: HTTP {head_response.status_code}")
                
                self.size = int(head_response.headers.get("Content-Length", 0))
                
                if "Content-Disposition" in head_response.headers:
                    import re
                    cd = head_response.headers["Content-Disposition"]
                    filename_match = re.search(r'filename="?([^";]+)', cd)
                    if filename_match:
                        self.file_name = filename_match.group(1)
                    else:
                        self.file_name = basename(url.split("?")[0])
                else:
                    self.file_name = basename(url.split("?")[0])
                
                if not self.file_name.lower().endswith('.nzb'):
                    self.file_name += '.nzb'
                
                LOGGER.debug(f"NZB metadata: size={self.size}, filename={self.file_name}")
                
        except Exception as e:
            LOGGER.error(f"Error fetching NZB metadata: {e}")
            raise ClientNotWorking(f"Failed to get NZB metadata: {str(e)}")
        
        return

    
    def download(self, filename: str, websocket_updater: Callable[[], Any]) -> None:
        """Download the NZB using SABnzbd."""
        LOGGER.debug(f"Starting Newznab download for: {self.download_link}")
        websocket_updater()
        self.downloading = True
        
        try:
            sabnzbd_client = ExternalClients.get_least_used_client(DownloadType.USENET)
            LOGGER.debug(f"Found SABnzbd client: {sabnzbd_client.id} - {sabnzbd_client.title}")
            
            url = self.download_link
            LOGGER.debug(f"Sending download URL to SABnzbd: {url}")
            
            from backend.internals.settings import Settings
            settings = Settings().sv
            
            self.external_id = sabnzbd_client.add_download(
                url, 
                settings.download_folder,
                self.file_name
            )
            
            LOGGER.debug(f"SABnzbd response ID: {self.external_id}")
            
            self.sabnzbd_client = sabnzbd_client

            self.progress = 0.0
            websocket_updater()
            
            LOGGER.info(f"NZB download handed off to SABnzbd with ID: {self.external_id}")
            
        except Exception as e:
            LOGGER.error(f"Error sending NZB to SABnzbd: {e}")
            raise ClientNotWorking(f"Failed to send NZB to SABnzbd: {str(e)}")
        finally:
            self.__r = None

    def update_status(self) -> None:
        """Update download status from SABnzbd."""
        if hasattr(self, 'sabnzbd_client') and hasattr(self, 'external_id'):
            try:
                status = self.sabnzbd_client.get_download(self.external_id)
                if status:
                    self.progress = status['progress']
                    self.speed = status['speed']
                    self.size = status['size']
                    LOGGER.debug(f"Updated Newznab download status: {self.progress}% complete")
            except Exception as e:
                LOGGER.error(f"Error updating download status: {e}")
    
    def stop(self) -> None:
        """Stop the download."""
        self.downloading = False
        if (
            self.__r
            and self.__r._fp
            and not isinstance(self.__r._fp, str)
        ):
            try:
                self.__r._fp.fp.raw._sock.shutdown(2)
            except Exception as e:
                LOGGER.error(f"Error stopping download: {e}")
        return


class NewznabSearch:
    """Class to search Newznab indexers."""
    
    def __init__(self, api_url: str, api_key: str) -> None:
        """Initialize the Newznab search."""
        self.api_url = api_url
        self.api_key = api_key
        
    def search(self, query: str, category: str = "7000,7020", limit: int = 1000) -> List[Dict[str, Any]]:
        """Search for comics using the Newznab API."""
        try:
            with Session() as session:
                params = {
                    "t": "search",
                    "apikey": self.api_key,
                    "q": query,
                    "cat": category,
                    "extended": "1",
                    "limit": str(limit),
                    "o": "xml"
                }
                
                url = f"{self.api_url}{'&' if '?' in self.api_url else '?'}" + urllib.parse.urlencode(params)
                
                LOGGER.debug(f"Newznab search URL: {url}")
                response = session.get(url)
                response.raise_for_status()
                
                results = []
                root = ET.fromstring(response.content)
                
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    title = title_elem.text if title_elem is not None else ""
                    
                    if not title:
                        continue
                    
                    # Skip ALL parts of a collection/multipart file/par with [X/Y] pattern
                    if re.search(r'\[\d+/\d+\]', title):
                        continue
                    
                    download_url = None
                    enclosure = item.find("enclosure")
                    if enclosure is not None and enclosure.get("url"):
                        download_url = enclosure.get("url")
                    
                    if not download_url:
                        LOGGER.warning(f"No download URL found for item: {title}")
                        continue
                    
                    size_elem = item.find(".//attr[@name='size']")
                    size_value = int(size_elem.get("value", "0")) if size_elem is not None else 0
                    
                    # Only add non-collection files
                    results.append({
                        "title": title,
                        "link": download_url,
                        "size": size_value,
                        "source": "newznab"
                    })
                
                return results
                        
        except Exception as e:
            LOGGER.error(f"Newznab search error: {e}")
            return []