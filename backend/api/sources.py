from flask import Blueprint, request, jsonify
from ..sources.airdcc import AirDCCSource
from ..models import get_setting

airdcc_bp = Blueprint('airdcc', __name__)

@airdcc_bp.route('/api/sources/airdcc/search', methods=['POST'])
def airdcc_search():
    query = request.json.get('query', '')
    filters = request.json.get('filters', {})
    
    config = {
        'server_url': get_setting('airdcc_server_url'),
        'username': get_setting('airdcc_username'),
        'password': get_setting('airdcc_password'),
        'timeout': int(get_setting('airdcc_timeout')),
        'max_results': int(get_setting('airdcc_max_results'))
    }
    
    source = AirDCCSource(config)
    results = source.search(query, filters)
    
    return jsonify({'results': [r.__dict__ for r in results]})

@airdcc_bp.route('/api/sources/airdcc/test', methods=['POST'])
def test_airdcc_connection():
    config = {
        'server_url': get_setting('airdcc_server_url'),
        'username': get_setting('airdcc_username'),
        'password': get_setting('airdcc_password')
    }
    
    source = AirDCCSource(config)
    is_connected = source.test_connection()
    
    return jsonify({'connected': is_connected})

@airdcc_bp.route('/api/sources/airdcc/download', methods=['POST'])
def airdcc_download():
    download_url = request.json.get('download_url', '')
    destination = request.json.get('destination', '')
    
    config = {
        'server_url': get_setting('airdcc_server_url'),
        'username': get_setting('airdcc_username'),
        'password': get_setting('airdcc_password'),
        'timeout': int(get_setting('airdcc_timeout'))
    }
    
    source = AirDCCSource(config)
    success = source.download(download_url, destination)
    
    return jsonify({'success': success})
