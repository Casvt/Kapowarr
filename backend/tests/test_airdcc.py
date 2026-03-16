import unittest
from unittest.mock import Mock, patch
from ..sources.airdcc import AirDCCSource

class TestAirDCCSource(unittest.TestCase):
    def setUp(self):
        self.config = {
            'server_url': 'http://test-airdcc:5115',
            'username': 'testuser',
            'password': 'testpass',
            'timeout': 30,
            'max_results': 100
        }
        self.source = AirDCCSource(self.config)
    
    @patch('requests.Session.get')
    def test_search_success(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'name': 'Test Comic',
                    'download_url': 'http://test.com/comic.cbz',
                    'size': 1048576,
                    'format': 'cbz',
                    'quality': 'high',
                    'seeders': 10,
                    'leechers': 2
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        results = self.source.search('test comic')
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Test Comic')
        self.assertEqual(results[0].source, 'airdcc')
    
    @patch('requests.Session.get')
    def test_connection_test_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = self.source.test_connection()
        
        self.assertTrue(result)
    
    @patch('requests.Session.get')
    def test_connection_test_failure(self, mock_get):
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        result = self.source.test_connection()
        
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
