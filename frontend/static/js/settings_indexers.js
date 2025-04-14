let indexersCache = [];

// Load all indexers and populate the table
function loadIndexers() {
    usingApiKey()
    .then(api_key => {
        // Get indexers from the server
        fetchAPI('/indexers', api_key)
        .then(response => {
            indexersCache = response.result || [];
            
            // Clear existing entries
            const indexersTable = document.getElementById('indexers-list');
            indexersTable.innerHTML = '';
            
            // Add each indexer to the table
            indexersCache.forEach(indexer => {
                const row = document.createElement('tr');
                row.dataset.id = indexer.id;
                
                // Name
                const nameCell = document.createElement('td');
                nameCell.textContent = indexer.name;
                row.appendChild(nameCell);
                
                // Type
                const typeCell = document.createElement('td');
                typeCell.textContent = indexer.type || 'Newznab';
                row.appendChild(typeCell);
                
                // URL
                const urlCell = document.createElement('td');
                urlCell.textContent = indexer.url;
                row.appendChild(urlCell);
                
                // Status
                const statusCell = document.createElement('td');
                const statusIndicator = document.createElement('span');
                statusIndicator.className = indexer.enabled ? 'status-enabled' : 'status-disabled';
                statusIndicator.textContent = indexer.enabled ? 'Enabled' : 'Disabled';
                statusCell.appendChild(statusIndicator);
                row.appendChild(statusCell);
                
                // Actions
                const actionsCell = document.createElement('td');
                const editButton = document.createElement('button');
                editButton.className = 'edit-button';
                editButton.innerHTML = '<img src="' + url_base + '/static/img/edit.svg" alt="Edit">';
                editButton.onclick = () => showEditIndexer(indexer.id);
                actionsCell.appendChild(editButton);
                row.appendChild(actionsCell);
                
                indexersTable.appendChild(row);
            });
        });
    });
}

// Show add Newznab indexer window
function showAddNewznab() {
    // Reset form
    const form = document.getElementById('newznab-form');
    form.reset();
    
    // Reset test button
    document.getElementById('test-newznab').classList.remove('show-success', 'show-fail');
    
    // Hide error message
    hide([document.getElementById('newznab-error')]);
    
    // Show window
    showWindow('newznab-window');
}

// Add a new Newznab indexer
function addNewznabIndexer() {
    usingApiKey()
    .then(api_key => {
        testNewznabConnection(api_key).then(result => {
            if (!result) return;
            
            const data = {
                type: 'newznab',
                name: document.getElementById('newznab-name-input').value,
                url: document.getElementById('newznab-url-input').value,
                apiKey: document.getElementById('newznab-apikey-input').value,
                categories: document.getElementById('newznab-categories-input').value || '7000,7020',
                enabled: true
            };
            
            sendAPI('POST', '/indexers', api_key, {}, data)
            .then(response => {
                loadIndexers();
                closeWindow();
            })
            .catch(error => {
                console.error('Error adding indexer:', error);
                const errorElem = document.getElementById('newznab-error');
                errorElem.textContent = 'Failed to add indexer: ' + (error.message || 'Unknown error');
                hide([], [errorElem]);
            });
        });
    });
}

// Test Newznab connection
async function testNewznabConnection(api_key) {
    const errorElem = document.getElementById('newznab-error');
    hide([errorElem]);
    
    const testButton = document.getElementById('test-newznab');
    testButton.classList.remove('show-success', 'show-fail');
    
    const data = {
        type: 'newznab',  // Add this line to fix the error
        url: document.getElementById('newznab-url-input').value,
        apiKey: document.getElementById('newznab-apikey-input').value,
        categories: document.getElementById('newznab-categories-input').value || '7000,7020'
    };
    
    return await sendAPI('POST', '/indexers/test', api_key, {}, data)
    .then(response => response.json())
    .then(json => {
        if (json.result && json.result.success) {
            // Test successful
            testButton.classList.add('show-success');
            return true;
        } else {
            // Test failed
            testButton.classList.add('show-fail');
            errorElem.textContent = json.result ? json.result.description : 'Connection test failed';
            hide([], [errorElem]);
            return false;
        }
    })
    .catch(error => {
        console.error('Error testing connection:', error);
        testButton.classList.add('show-fail');
        errorElem.textContent = 'Failed to test connection: ' + (error.message || 'Unknown error');
        hide([], [errorElem]);
        return false;
    });
}

// Show edit indexer window
function showEditIndexer(id) {
    usingApiKey()
    .then(api_key => {
        const indexer = indexersCache.find(i => i.id === id);
        if (!indexer) return;
        
        const form = document.getElementById('edit-indexer-form');
        form.dataset.id = id;
        form.dataset.type = indexer.type || 'newznab';
        
        // Populate form fields
        document.getElementById('edit-name-input').value = indexer.name || '';
        document.getElementById('edit-url-input').value = indexer.url || '';
        document.getElementById('edit-apikey-input').value = indexer.apiKey || '';
        document.getElementById('edit-categories-input').value = indexer.categories || '7000,7020';
        
        // Reset test button and hide error
        document.getElementById('test-indexer-edit').classList.remove('show-success', 'show-fail');
        hide([document.getElementById('edit-error')]);
        
        // Show window
        showWindow('edit-indexer-window');
    });
}

// Save edited indexer
function saveEditedIndexer() {
    usingApiKey()
    .then(api_key => {
        testEditIndexer(api_key).then(result => {
            if (!result) return;
            
            const form = document.getElementById('edit-indexer-form');
            const id = form.dataset.id;
            
            const data = {
                type: form.dataset.type,
                name: document.getElementById('edit-name-input').value,
                url: document.getElementById('edit-url-input').value,
                apiKey: document.getElementById('edit-apikey-input').value,
                categories: document.getElementById('edit-categories-input').value || '7000,7020',
                enabled: true  // We could add a checkbox for this if needed
            };
            
            sendAPI('PUT', `/indexers/${id}`, api_key, {}, data)
            .then(response => {
                loadIndexers();
                closeWindow();
            })
            .catch(error => {
                console.error('Error updating indexer:', error);
                const errorElem = document.getElementById('edit-error');
                errorElem.textContent = 'Failed to update indexer: ' + (error.message || 'Unknown error');
                hide([], [errorElem]);
            });
        });
    });
}

// Test edited indexer connection
async function testEditIndexer(api_key) {
    const errorElem = document.getElementById('edit-error');
    hide([errorElem]);
    
    const testButton = document.getElementById('test-indexer-edit');
    testButton.classList.remove('show-success', 'show-fail');
    
    const form = document.getElementById('edit-indexer-form');
    
    const data = {
        type: form.dataset.type,  // Add this line to fix the error
        url: document.getElementById('edit-url-input').value,
        apiKey: document.getElementById('edit-apikey-input').value,
        categories: document.getElementById('edit-categories-input').value || '7000,7020'
    };
    
    return await sendAPI('POST', '/indexers/test', api_key, {}, data)
    .then(response => response.json())
    .then(json => {
        if (json.result && json.result.success) {
            // Test successful
            testButton.classList.add('show-success');
            return true;
        } else {
            // Test failed
            testButton.classList.add('show-fail');
            errorElem.textContent = json.result ? json.result.description : 'Connection test failed';
            hide([], [errorElem]);
            return false;
        }
    })
    .catch(error => {
        console.error('Error testing connection:', error);
        testButton.classList.add('show-fail');
        errorElem.textContent = 'Failed to test connection: ' + (error.message || 'Unknown error');
        hide([], [errorElem]);
        return false;
    });
}

// Delete indexer
function deleteIndexer() {
    usingApiKey()
    .then(api_key => {
        const form = document.getElementById('edit-indexer-form');
        const id = form.dataset.id;
        
        if (confirm('Are you sure you want to delete this indexer?')) {
            sendAPI('DELETE', `/indexers/${id}`, api_key)
            .then(response => {
                loadIndexers();
                closeWindow();
            })
            .catch(error => {
                console.error('Error deleting indexer:', error);
                const errorElem = document.getElementById('edit-error');
                errorElem.textContent = 'Failed to delete indexer: ' + (error.message || 'Unknown error');
                hide([], [errorElem]);
            });
        }
    });
}

// Set up event listeners once DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load all indexers
    loadIndexers();
    
    // Add Newznab indexer button
    document.getElementById('add-newznab-indexer').addEventListener('click', function() {
        showAddNewznab();
    });
    
    // Add Newznab form submit
    document.getElementById('newznab-form').addEventListener('submit', function(e) {
        e.preventDefault();
        addNewznabIndexer();
    });
    
    // Test Newznab connection
    document.getElementById('test-newznab').addEventListener('click', function() {
        usingApiKey().then(api_key => testNewznabConnection(api_key));
    });
    
    // Edit form submit
    document.getElementById('edit-indexer-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveEditedIndexer();
    });
    
    // Edit form test connection
    document.getElementById('test-indexer-edit').addEventListener('click', function() {
        usingApiKey().then(api_key => testEditIndexer(api_key));
    });
    
    // Delete indexer
    document.getElementById('delete-indexer-edit').addEventListener('click', function() {
        deleteIndexer();
    });
});