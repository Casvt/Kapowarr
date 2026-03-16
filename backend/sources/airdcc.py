import requests
import logging
from typing import List, Dict, Optional
from ..models import ComicIssue, SearchResult

class AirDCCSource:
    def __init__(self, config: Dict):
        self.base_url = config.get('server_url', 'http://localhost:5115')
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.timeout = config.get('search_timeout', 30)
        self.max_results = config.get('max_results', 100)
        self.session = requests.Session()
        
        if self.username and self.password:
            self.session.auth = (self.username, self.password)
    
    def search(self, query: str, filters: Optional[Dict] = None) -> List[SearchResult]:
        """
        Search for comics on AirDCC++ hub
        """
        try:
            search_url = f"{self.base_url}/api/search"
            params = {
                'q': query,
                'type': 'comic',
                'limit': self.max_results
            }
            
            if filters:
                params.update(filters)
            
            response = self.session.get(search_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            results = []
            for item in response.json().get('results', []):
                results.append(SearchResult(
                    title=item.get('name', ''),
                    source='airdcc',
                    file_url=item.get('download_url', ''),
                    size=item.get('size', 0),
                    format=item.get('format', ''),
                    quality=item.get('quality', ''),
                    seeders=item.get('seeders', 0),
                    leechers=item.get('leechers', 0),
                    metadata=item.get('metadata', {})
                ))
            
            return results
            
        except requests.RequestException as e:
            logging.error(f"AirDCC++ search failed: {e}")
            return []
    
    def download(self, download_url: str, destination: str, progress_callback=None) -> bool:
        """
        Download file from AirDCC++
        """
        try:
            response = self.session.get(download_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            return True
            
        except requests.RequestException as e:
            logging.error(f"AirDCC++ download failed: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test connection to AirDCC++ server
        """
        try:
            response = self.session.get(f"{self.base_url}/api/status", timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False
