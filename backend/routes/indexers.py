# -*- coding: utf-8 -*-

"""Routes for managing indexers."""

from flask import Blueprint, render_template, request, jsonify
from backend.internals.db import get_db, commit
from backend.base.custom_exceptions import ExternalClientNotFound, KeyNotFound, InvalidKeyValue
from functools import wraps

indexers_blueprint = Blueprint('indexers', __name__)

# Define our own simple error handler for this file
def local_error_handler(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_name = e.__class__.__name__
            
            # Check for api_response
            if hasattr(e, 'api_response'):
                # Get the response
                response = getattr(e, 'api_response')
                
                # Make sure it's a dictionary
                if isinstance(response, dict):
                    return jsonify(response), response.get('code', 500)
                
            # Generic error response for standard exceptions
            return jsonify({
                'error': error_name,
                'result': {'description': str(e)},
                'code': 500
            }), 500
    return wrapper


@indexers_blueprint.route('/settings/indexers')
def indexers_page():
    """Render the indexers settings page."""
    return render_template('settings_indexers.html')

@indexers_blueprint.route('/api/indexers', methods=['GET'])
@local_error_handler
def get_indexers():
    """Get all configured indexers."""
    db = get_db()
    indexers = db.execute(
        'SELECT id, name, type, url, api_key AS apiKey, categories, enabled FROM indexers'
    ).fetchall()
    
    return jsonify({
        'result': [dict(indexer) for indexer in indexers],
        'code': 200
    }), 200

@indexers_blueprint.route('/api/indexers/<int:indexer_id>', methods=['GET'])
@local_error_handler
def get_indexer(indexer_id):
    """Get a specific indexer by ID."""
    db = get_db()
    indexer = db.execute(
        'SELECT id, name, type, url, api_key AS apiKey, categories, enabled FROM indexers WHERE id = ?', 
        (indexer_id,)
    ).fetchone()
    
    if not indexer:
        raise ExternalClientNotFound()
    
    return jsonify({
        'result': dict(indexer),
        'code': 200
    }), 200

@indexers_blueprint.route('/api/indexers', methods=['POST'])
@local_error_handler
def add_indexer():
    """Add a new indexer."""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'type', 'url', 'apiKey']
    for field in required_fields:
        if field not in data:
            raise KeyNotFound(field)
        
        if not data[field]:
            raise InvalidKeyValue(field)
    
    # Add the indexer to the database
    db = get_db()
    
    categories = data.get('categories', '7000,7020')
    enabled = data.get('enabled', 1)
    
    result = db.execute(
        'INSERT INTO indexers (name, type, url, api_key, categories, enabled) VALUES (?, ?, ?, ?, ?, ?)',
        (data['name'], data['type'], data['url'], data['apiKey'], categories, enabled)
    )
    
    commit()
    
    # Return the newly created indexer
    indexer = db.execute(
        'SELECT id, name, type, url, api_key AS apiKey, categories, enabled FROM indexers WHERE id = ?',
        (result.lastrowid,)
    ).fetchone()
    
    return jsonify({
        'result': dict(indexer),
        'code': 200
    }), 200

@indexers_blueprint.route('/api/indexers/<int:indexer_id>', methods=['PUT'])
@local_error_handler
def update_indexer(indexer_id):
    """Update an existing indexer."""
    db = get_db()
    
    # Check if indexer exists
    indexer = db.execute(
        'SELECT * FROM indexers WHERE id = ?', 
        (indexer_id,)
    ).fetchone()
    
    if not indexer:
        raise ExternalClientNotFound()
    
    data = request.get_json()
    
    # Prepare update fields
    fields = []
    params = []
    
    if 'name' in data:
        fields.append('name = ?')
        params.append(data['name'])
    
    if 'type' in data:
        fields.append('type = ?')
        params.append(data['type'])
    
    if 'url' in data:
        fields.append('url = ?')
        params.append(data['url'])
    
    if 'apiKey' in data:
        fields.append('api_key = ?')
        params.append(data['apiKey'])
    
    if 'categories' in data:
        fields.append('categories = ?')
        params.append(data['categories'])
    
    if 'enabled' in data is not None:
        fields.append('enabled = ?')
        params.append(1 if data['enabled'] else 0)
    
    if not fields:
        return jsonify({
            'result': dict(indexer),
            'code': 200
        }), 200
    
    # Update the indexer
    params.append(indexer_id)
    db.execute(
        f'UPDATE indexers SET {", ".join(fields)} WHERE id = ?',
        params
    )
    commit()
    
    # Return the updated indexer
    updated_indexer = db.execute(
        'SELECT id, name, type, url, api_key AS apiKey, categories, enabled FROM indexers WHERE id = ?',
        (indexer_id,)
    ).fetchone()
    
    return jsonify({
        'result': dict(updated_indexer),
        'code': 200
    }), 200

@indexers_blueprint.route('/api/indexers/<int:indexer_id>', methods=['DELETE'])
@local_error_handler
def delete_indexer(indexer_id):
    """Delete an indexer."""
    db = get_db()
    
    # Check if indexer exists
    indexer = db.execute(
        'SELECT * FROM indexers WHERE id = ?', 
        (indexer_id,)
    ).fetchone()
    
    if not indexer:
        raise ExternalClientNotFound()
    
    # Delete the indexer
    db.execute('DELETE FROM indexers WHERE id = ?', (indexer_id,))
    commit()
    
    return jsonify({
        'result': {},
        'code': 200
    }), 200

@indexers_blueprint.route('/api/indexers/test', methods=['POST'])
@local_error_handler
def test_indexer():
    """Test an indexer connection."""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['type', 'url', 'apiKey']
    for field in required_fields:
        if field not in data:
            raise KeyNotFound(field)
    
    # Test the connection based on indexer type
    try:
        if data['type'] == 'newznab':
            from backend.implementations.direct_clients.newznab import NewznabSearch
            
            # Test the connection
            search = NewznabSearch(data['url'], data['apiKey'])
            # Simple test search to verify connection
            search.search("test")
            
        # Add additional indexer types here as needed
        
        return jsonify({
            'result': {"success": True},
            'code': 200
        }), 200
        
    except Exception as e:
        return jsonify({
            'result': {"success": False, "description": str(e)},
            'code': 200
        }), 200
