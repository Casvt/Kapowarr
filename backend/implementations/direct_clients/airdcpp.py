# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from json import JSONDecodeError, dumps, loads
from time import perf_counter, time
from typing import Any, Callable, Dict, Generator, List, Sequence, Tuple, Union, Optional, TypeVar, cast
from urllib3.exceptions import ProtocolError

from backend.base.custom_exceptions import (ClientNotWorking,
                                            DownloadLimitReached, LinkBroken)
from backend.base.definitions import (BaseEnum, BlocklistReason, Constants,
                                      CredentialData, CredentialSource,
                                      DownloadSource)
from backend.base.helpers import Session
from backend.base.logging import LOGGER
from backend.implementations.credentials import Credentials

T = TypeVar('T', Dict[str, Any], List[Any], int)

class AirDCCommands(BaseEnum):
    AUTH = "sessions/authorize"
    GET_INSTANCE = "search"
    CREATE_INSTANCE = "search"
    PERFORM_SEARCH = "hub_search"
    DOWNLOAD = "download"
    GET_RESULTS = "results"


class AirDCPPClient:
    def __init__(
        self,
        url: Union[str, None] = None,
        token: Union[str, None] = None
    ) -> None:
        """Prepare AirDC++ client.

        Args:
            url (Union[str, None], optional): AirDC++ Web API URL.
                Defaults to None.

            token (Union[str, None], optional): Auth token.
                Defaults to None.
        """
        self.url = url
        self.token = token
        # Fix the double slash issue by ensuring only one slash between url and api path
        if url:
            if url.endswith('/'):
                self.base_url = f"{url}api/v1/"
            else:
                self.base_url = f"{url}/api/v1/"
        else:
            self.base_url = None
        return

    def api_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Union[Dict[str, Any], List[Any], int]:
        """Send a request to the AirDC++ API.

        Args:
            endpoint (str): API endpoint to call
            method (str, optional): HTTP method to use. Defaults to "GET".
            data (Dict[str, Any], optional): Data to send in the request. Defaults to None.

        Returns:
            Union[Dict[str, Any], List[Any], int]: Response from the API
        """
        if not self.base_url:
            raise ClientNotWorking("AirDC++ URL not configured")

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': Constants.BROWSER_USERAGENT
        }

        if self.token:
            headers['Authorization'] = f"Bearer {self.token}"

        with Session() as session:
            url = f"{self.base_url}{endpoint}"
            LOGGER.debug(f"AirDC++ API request: {method} {url}")
            
            if method == "GET":
                response = session.get(url, headers=headers)
            elif method == "POST":
                response = session.post(url, headers=headers, json=data if data else {})
            elif method == "DELETE":
                response = session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code >= 400:
                LOGGER.error(f"AirDC++ API error: {response.status_code} {response.text}")
                raise ClientNotWorking(f"AirDC++ API error: {response.status_code} {response.text}")

            try:
                return response.json()
            except JSONDecodeError:
                # Some endpoints may return empty responses
                return {}

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}, url={self.url}>'


class AirDCPPAccount:
    def __init__(
        self,
        client: AirDCPPClient,
        username: Union[str, None] = None,
        password: Union[str, None] = None
    ) -> None:
        """Authenticate with AirDC++.

        Args:
            client (AirDCPPClient): AirDC++ client to use
            username (Union[str, None], optional): Username. Defaults to None.
            password (Union[str, None], optional): Password. Defaults to None.
        """
        self.client = client

        try:
            if username and password:
                auth_data = self._login_user(username, password)
                if isinstance(auth_data, dict):
                    self.client.token = auth_data.get("auth_token")
                else:
                    raise ClientNotWorking("Invalid response from AirDC++ login")
            else:
                raise ClientNotWorking("Username and password are required for AirDC++ login")
        except Exception as e:
            LOGGER.error(f"Failed to login to AirDC++: {str(e)}")
            raise ClientNotWorking(f"Failed to login to AirDC++: {str(e)}")

        return

    def _login_user(self, username: str, password: str) -> Dict[str, Any]:
        """Log in to AirDC++ with username and password.

        Args:
            username (str): Username
            password (str): Password

        Returns:
            Dict[str, Any]: Authentication response
        """
        LOGGER.debug('Logging into AirDC++ with user account')
        
        auth_data = {
            "username": username,
            "password": password
        }
        
        response = self.client.api_request(AirDCCommands.AUTH.value, method="POST", data=auth_data)
        if isinstance(response, dict):
            return response
        else:
            raise ClientNotWorking("Invalid response format from AirDC++ login")


class AirDCPPABC(ABC):
    size: int
    progress: float
    speed: float
    pure_link: str
    file_name: str

    @abstractmethod
    def __init__(self, download_link: str) -> None:
        ...

    @abstractmethod
    def download(
        self,
        filename: str,
        websocket_updater: Callable[[], Any]
    ) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...


class AirDCPP(AirDCPPABC):
    def __init__(self, download_link: str) -> None:
        """Initialize AirDC++ download.

        Args:
            download_link (str): Link to download
        """
        self.download_link = download_link
        self.client = None
        self.search_instance_id = None
        self.result_id = None
        self.__r = None
        self.downloading = False
        self.progress = 0.0
        self.speed = 0.0
        
        try:
            # Extract information from the download link
            # Format: airdcpp://session_id/result_id/filename
            parts = download_link.replace("airdcpp://", "").split("/", 2)
            self.search_instance_id = parts[0]
            self.result_id = parts[1]
            self.file_name = parts[2]
            
            # Set a default size - we won't rely on getting it from the search result
            self.size = 0
            self.pure_link = download_link
            
            # Get the client without trying to fetch result info
            self.client = self._get_client()
            if not self.client:
                raise ClientNotWorking("AirDC++ client is not configured")
                
        except Exception as e:
            LOGGER.error(f"Failed to initialize AirDC++ download: {str(e)}")
            raise ClientNotWorking(f"Failed to initialize AirDC++ download: {str(e)}")

        return


    def _get_client(self) -> Optional[AirDCPPClient]:
        """Get an authenticated AirDC++ client.

        Returns:
            Optional[AirDCPPClient]: Authenticated client or None
        """
        cred = Credentials()
        for airdcpp_cred in cred.get_from_source(CredentialSource.AIRDCPP):
            auth_token = (
                cred
                .auth_tokens.get(CredentialSource.AIRDCPP, {})
                .get(airdcpp_cred.email or '', (None, 0))
            )
            
            client = AirDCPPClient(airdcpp_cred.api_key)  # Using api_key field for URL
            
            if auth_token[1] > time():
                client.token = auth_token[0]
                return client

            try:
                AirDCPPAccount(
                    client,
                    airdcpp_cred.username,
                    airdcpp_cred.password
                )
                
                cred.auth_tokens.setdefault(CredentialSource.AIRDCPP, {})[
                    airdcpp_cred.email or ''
                ] = (client.token, round(time()) + 3600)
                
                return client

            except ClientNotWorking:
                LOGGER.error(
                    'Login credentials for AirDC++ are invalid. Login failed.'
                )
        
        return None

    def download(self, filename: str, websocket_updater: Callable[[], Any]) -> None:
        if not self.client:
            raise ClientNotWorking("AirDC++ client is not configured")

        websocket_updater()
        self.downloading = True
        size_downloaded = 0

        try:
            # Get the settings download folder directly
            from backend.internals.settings import Settings
            settings = Settings().sv
            target_directory = settings.download_folder
            
            # Initiate download with the correct target directory
            download_response = self.client.api_request(
                f"search/{self.search_instance_id}/results/{self.result_id}/download",
                method="POST",
                data={"target_directory": target_directory}
            )
            
            if isinstance(download_response, dict) and "bundle_info" in download_response:
                bundle_id = download_response["bundle_info"]["id"]
                
                # Monitor download progress
                start_time = perf_counter()
                last_size = 0
                no_progress_count = 0
                
                # Keep checking status until download completes or is stopped
                while self.downloading:
                    # Get bundle status
                    bundle_info_response = self.client.api_request(
                        f"queue/bundles/{bundle_id}",
                        method="GET"
                    )
                    
                    if not isinstance(bundle_info_response, dict):
                        LOGGER.error(f"Invalid bundle info response: {bundle_info_response}")
                        break
                    
                    # Get bundle size if available
                    if "size" in bundle_info_response:
                        self.size = bundle_info_response["size"]
                    
                    # Get downloaded bytes
                    size_downloaded = bundle_info_response.get("downloaded_bytes", 0)
                    
                    # Calculate progress percentage properly
                    if self.size > 0:
                        self.progress = min(round(size_downloaded / self.size * 100, 2), 100.0)
                    else:
                        # Default to a reasonable progress indicator when size is unknown
                        status = bundle_info_response.get("status", {})
                        if isinstance(status, dict) and status.get("downloaded", False):
                            self.progress = 100.0
                        else:
                            self.progress = 0.0
                    
                    # Get speed from bundle info if available
                    if "speed" in bundle_info_response:
                        self.speed = bundle_info_response["speed"]
                    else:
                        # Calculate speed from difference in downloaded bytes
                        current_time = perf_counter()
                        elapsed = current_time - start_time
                        if elapsed > 0 and size_downloaded > last_size:
                            self.speed = round((size_downloaded - last_size) / elapsed, 2)
                        
                    start_time = perf_counter()
                    last_size = size_downloaded
                    
                    # Check for download completion
                    status = bundle_info_response.get("status", {})
                    if isinstance(status, dict) and status.get("id") in ["downloaded", "completed", "shared"]:
                        self.progress = 100.0
                        break
                    
                    # Check for stalled download
                    if size_downloaded == last_size:
                        no_progress_count += 1
                        if no_progress_count >= 10:  # Wait longer before assuming completion
                            if isinstance(status, dict) and status.get("downloaded", False):
                                self.progress = 100.0
                                break
                    else:
                        no_progress_count = 0
                    
                    # Update UI
                    websocket_updater()
                    
                    # Small sleep to avoid hammering the API
                    from time import sleep
                    sleep(1)
            else:
                LOGGER.error("Failed to start download: No bundle info returned")
                raise ClientNotWorking("Failed to start download")
            
        except Exception as e:
            LOGGER.error(f"Download failed: {str(e)}")
            if "download limit" in str(e).lower():
                raise DownloadLimitReached(DownloadSource.AIRDCPP)
            raise ClientNotWorking(f"Download failed: {str(e)}")

        # Mark download as complete
        self.progress = 100.0
        self.__r = None
        return

    def stop(self) -> None:
        """Stop the download."""
        self.downloading = False
        if self.__r and hasattr(self.__r, '_fp') and self.__r._fp and not isinstance(self.__r._fp, str):
            try:
                self.__r._fp.fp.raw._sock.shutdown(2)  # SHUT_RDWR
            except:
                pass
        return


class AirDCPPSearch:
    """Class for handling AirDC++ searches."""
    
    def __init__(self, url: Union[str, None] = None, token: Union[str, None] = None):
        """Initialize search with AirDC++ API connection.
        
        Args:
            url (str, optional): AirDC++ Web API URL. Defaults to None.
            token (str, optional): Auth token. Defaults to None.
        """
        self.client = AirDCPPClient(url, token)
        self.search_instance_id = None
        
    def create_search_instance(self) -> Optional[str]:
        """Create a new search instance in AirDC++.
        
        Returns:
            Optional[str]: The ID of the created search instance or None if creation failed
        """
        try:
            result = self.client.api_request(
                AirDCCommands.CREATE_INSTANCE.value,
                method="POST"
            )
            if isinstance(result, dict):
                self.search_instance_id = result.get("id")
                return self.search_instance_id
            else:
                LOGGER.error(f"Unexpected response type from create_search_instance: {type(result)}")
                return None
        except Exception as e:
            LOGGER.error(f"Failed to create search instance: {str(e)}")
            return None
            
    def perform_search(self, query: str, wait_time: int = 15) -> List[Dict[str, Any]]:
        """Perform a search on AirDC++ hubs.
        
        Args:
            query (str): Search query
            wait_time (int, optional): Time to wait for results in seconds. Defaults to 15.
            
        Returns:
            List[Dict[str, Any]]: Search results
        """
        if not self.search_instance_id:
            self.create_search_instance()
            
        if not self.search_instance_id:
            LOGGER.error("Failed to create search instance")
            return []
            
        try:
            # Prepare search query
            search_data = {
                "query": {
                    "pattern": query
                },
                "priority": 5
            }
            
            # Start search
            self.client.api_request(
                f"search/{self.search_instance_id}/{AirDCCommands.PERFORM_SEARCH.value}",
                method="POST",
                data=search_data
            )
            
            # Wait for results
            from time import sleep
            sleep(wait_time)
            
            # Get results
            results = self.client.api_request(
                f"search/{self.search_instance_id}/{AirDCCommands.GET_RESULTS.value}/0/100",
                method="GET"
            )
            
            if isinstance(results, list):
                return results
            elif isinstance(results, dict) and "results" in results:
                # Some APIs return results in a nested structure
                results_list = results.get("results")
                if isinstance(results_list, list):
                    return results_list
            
            LOGGER.error(f"Unexpected results format: {type(results)}")
            return []
                
        except Exception as e:
            LOGGER.error(f"Search failed: {str(e)}")
            return []
            
    def download_result(self, result_id: str, target_directory: str) -> Dict[str, Any]:
        """Download a search result.
        
        Args:
            result_id (str): ID of the result to download
            target_directory (str): Directory to download to
            
        Returns:
            Dict[str, Any]: Download response
        """
        try:
            response = self.client.api_request(
                f"search/{self.search_instance_id}/results/{result_id}/download",
                method="POST",
                data={"target_directory": target_directory}
            )
            
            if isinstance(response, dict):
                return response
            else:
                LOGGER.error(f"Unexpected response type from download_result: {type(response)}")
                return {}
                
        except Exception as e:
            LOGGER.error(f"Download failed: {str(e)}")
            return {}
            
    def close_search_instance(self) -> None:
        """Close the search instance."""
        if self.search_instance_id:
            try:
                self.client.api_request(
                    f"search/{self.search_instance_id}",
                    method="DELETE"
                )
                self.search_instance_id = None
            except Exception as e:
                LOGGER.error(f"Failed to close search instance: {str(e)}")


def create_airdcpp_link(search_instance_id: str, result_id: str, filename: str) -> str:
    """Create an AirDC++ download link.
    
    Args:
        search_instance_id (str): ID of the search instance
        result_id (str): ID of the search result
        filename (str): Name of the file
        
    Returns:
        str: AirDC++ download link
    """
    return f"airdcpp://{search_instance_id}/{result_id}/{filename}"