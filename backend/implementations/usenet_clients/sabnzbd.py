# -*- coding: utf-8 -*-

import os

from time import time
from typing import Any, Dict, List, Union, Optional
from urllib.parse import urljoin

from requests.exceptions import RequestException

from backend.base.custom_exceptions import ExternalClientNotWorking
from backend.base.definitions import Constants, DownloadState, DownloadType, FileConstants
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.external_clients import BaseExternalClient
from backend.internals.settings import Settings


class SABnzbd(BaseExternalClient):
    client_type = 'SABnzbd'
    download_type = DownloadType.USENET

    required_tokens = ('title', 'base_url', 'api_token')

    state_mapping = {
        'Downloading': DownloadState.DOWNLOADING_STATE,
        'Queued': DownloadState.QUEUED_STATE,
        'Paused': DownloadState.PAUSED_STATE,
        'Checking': DownloadState.DOWNLOADING_STATE,
        'Verifying': DownloadState.DOWNLOADING_STATE,
        'Repairing': DownloadState.DOWNLOADING_STATE,
        'Extracting': DownloadState.IMPORTING_STATE,
        'Moving': DownloadState.IMPORTING_STATE,
        'Completed': DownloadState.DOWNLOADING_STATE,
        'Failed': DownloadState.FAILED_STATE,
    }

    def __init__(self, client_id: int) -> None:
        super().__init__(client_id)
        
        self.ssn: Union[Session, None] = None
        self.settings = Settings()
        return

    @staticmethod
    def _connect(
        base_url: str,
        api_token: Union[str, None]
    ) -> Union[Session, str]:
        """Test connection to SABnzbd instance.
        
        Args:
            base_url (str): Base URL of the SABnzbd instance
            api_token (Union[str, None]): API key for SABnzbd
            
        Returns:
            Union[Session, str]: Session object if successful, error message if failed
        """
        if not api_token:
            return "API key is required for SABnzbd"
            
        ssn = Session()
        
        try:
            response = ssn.get(
                f"{base_url}/api",
                params={
                    'output': 'json',
                    'mode': 'queue',
                    'apikey': api_token
                }
            )
            
            if response.status_code == 403:
                return "Invalid API key"
                
            if response.status_code != 200:
                return f"Connection failed with status code {response.status_code}"
            
            data = response.json()
            if 'error' in data:
                return f"SABnzbd error: {data['error']}"
                

            if 'queue' not in data:
                return "Invalid response from SABnzbd"
                
        except RequestException as e:
            LOGGER.exception("Can't connect to SABnzbd instance: ")
            return f"Can't connect; invalid base URL: {str(e)}"
        
        return ssn

    def add_download(self, download_link: str, target_folder: str, download_name: Union[str, None]) -> str:
        LOGGER.debug(f"SABnzbd.add_download called with: {download_link}")
        LOGGER.debug(f"Target folder: {target_folder}, download_name: {download_name}")
        
        if not self.ssn:
            result = self._connect(self.base_url, self.api_token)
            if isinstance(result, str):
                LOGGER.error(f"Failed to connect to SABnzbd: {result}")
                raise ExternalClientNotWorking(result)
            self.ssn = result

        is_direct_link = download_link.lower().startswith('http')
        LOGGER.debug(f"Is direct link: {is_direct_link}")
        
        if is_direct_link:
            if 'prowlarr' in download_link.lower() and 'download' in download_link:
                LOGGER.debug(f"Detected Prowlarr URL, sending complete URL to SABnzbd")

            params = {
                'output': 'json',
                'mode': 'addurl',
                'apikey': self.api_token,
                'name': download_link,
                'cat': Constants.USENET_TAG,
                'priority': 0,
            }

            if download_name:
                params['nzbname'] = download_name
            
            LOGGER.debug(f"Files will be downloaded to SABnzbd category '{Constants.USENET_TAG}' folder")
            
            response = self.ssn.get(f"{self.base_url}/api", params=params)
            LOGGER.debug(f"SABnzbd API response status: {response.status_code}")
            LOGGER.debug(f"SABnzbd API response: {response.text}")
            
        else:
            LOGGER.error("Non-URL NZB handling not implemented")
            raise ExternalClientNotWorking("Only direct NZB URLs are supported")
        
        if response.status_code != 200:
            raise ExternalClientNotWorking(f"Failed to add download: {response.text}")
            
        data = response.json()
        if not data or 'status' not in data or data['status'] is False:
            error_msg = data.get('error', 'Unknown error')
            raise ExternalClientNotWorking(f"Failed to add download: {error_msg}")

        nzo_id = data.get('nzo_ids', ['unknown_id'])[0]
        LOGGER.info(f"Successfully added to SABnzbd with ID: {nzo_id}")
        return nzo_id


    def get_download(self, download_id: str) -> Union[dict, None]:
        """Get download status from SABnzbd.
        
        Args:
            download_id (str): SABnzbd nzo_id
                
        Returns:
            Union[dict, None]: Download status info or None if not found
        """
        if not self.ssn:
            result = self._connect(self.base_url, self.api_token)
            if isinstance(result, str):
                raise ExternalClientNotWorking(result)
            self.ssn = result

        # Check if it's in the queue
        queue_response = self.ssn.get(
            f"{self.base_url}/api",
            params={
                'output': 'json',
                'mode': 'queue',
                'apikey': self.api_token
            }
        )
        
        if queue_response.status_code != 200:
            raise ExternalClientNotWorking(f"Failed to get queue: {queue_response.text}")
            
        queue_data = queue_response.json()
        
        if 'queue' in queue_data and 'slots' in queue_data['queue']:
            for item in queue_data['queue']['slots']:
                if item.get('nzo_id') == download_id:
                    status = item.get('status', 'Queued')
                    mb_left = float(item.get('mbleft', 0))
                    mb_total = float(item.get('mb', 0))
                    
                    progress = 0
                    if mb_total > 0:
                        progress = round(((mb_total - mb_left) / mb_total) * 100, 2)
                    
                    return {
                        'size': int(mb_total * 1024 * 1024),
                        'progress': progress,
                        'speed': int(item.get('speed', 0)),
                        'state': self.state_mapping.get(status, DownloadState.DOWNLOADING_STATE)
                    }
        
        # If not in queue, check history
        history_response = self.ssn.get(
            f"{self.base_url}/api",
            params={
                'output': 'json',
                'mode': 'history',
                'apikey': self.api_token
            }
        )
        
        if history_response.status_code != 200:
            raise ExternalClientNotWorking(f"Failed to get history: {history_response.text}")
            
        history_data = history_response.json()
        
        if 'history' in history_data and 'slots' in history_data['history']:
            for item in history_data['history']['slots']:
                if item.get('nzo_id') == download_id:
                    status = item.get('status', 'Completed')
                    
                    if status == 'Completed':
                        state = DownloadState.DOWNLOADING_STATE
                    elif status == 'Failed':
                        state = DownloadState.FAILED_STATE
                    else:
                        state = DownloadState.IMPORTING_STATE
                    
                    # Get the storage path from SABnzbd - this is the final destination
                    storage_path = item.get('storage', '')
                    LOGGER.debug(f"SABnzbd reported storage path: {storage_path}")
                    
                    # Find the main comic file in the storage path
                    final_files = []
                    if storage_path and os.path.exists(storage_path):
                        # Look for comic files in the storage path
                        if os.path.isdir(storage_path):
                            # Scan for comic files in the directory
                            for root, _, files in os.walk(storage_path):
                                for file in files:
                                    if any(file.lower().endswith(ext) for ext in FileConstants.CONTAINER_EXTENSIONS):
                                        final_files.append(os.path.join(root, file))
                        else:
                            final_files.append(storage_path)
                        
                        if final_files:
                            LOGGER.info(f"Found files at storage path: {final_files}")
                        else:
                            LOGGER.warning(f"No comic files found at storage path: {storage_path}")
                    else:
                        LOGGER.warning(f"Storage path not found: {storage_path}")
                    
                    return {
                        'size': int(item.get('bytes', 0)),
                        'progress': 100,
                        'speed': 0,
                        'state': state,
                        'final_files': final_files
                    }

        return None


    def delete_download(self, download_id: str, delete_files: bool) -> None:
        """Delete a download from SABnzbd.
        
        Args:
            download_id (str): SABnzbd nzo_id
            delete_files (bool): Whether to delete files from disk
        """
        if not self.ssn:
            result = self._connect(self.base_url, self.api_token)
            if isinstance(result, str):
                raise ExternalClientNotWorking(result)
            self.ssn = result
        
        queue_delete_response = self.ssn.get(
            f"{self.base_url}/api",
            params={
                'output': 'json',
                'mode': 'queue',
                'name': 'delete',
                'apikey': self.api_token,
                'value': download_id,
                'del_files': int(delete_files)
            }
        )
        
        history_delete_response = self.ssn.get(
            f"{self.base_url}/api",
            params={
                'output': 'json',
                'mode': 'history',
                'name': 'delete',
                'apikey': self.api_token,
                'value': download_id,
                'del_files': int(delete_files)
            }
        )
        
        return

    @staticmethod
    def test(
        base_url: str,
        username: Union[str, None] = None,
        password: Union[str, None] = None,
        api_token: Union[str, None] = None
    ) -> Union[str, None]:
        """Test connection to SABnzbd.
        
        Args:
            base_url (str): Base URL of the SABnzbd instance
            username (Union[str, None]): Not used for SABnzbd
            password (Union[str, None]): Not used for SABnzbd
            api_token (Union[str, None]): API key for SABnzbd
            
        Returns:
            Union[str, None]: Error message if connection failed, None if successful
        """
        result = SABnzbd._connect(base_url, api_token)
        if isinstance(result, str):
            return result
        return None
