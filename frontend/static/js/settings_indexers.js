function loadAddIndexer() {
	const form = document.querySelector('#add-indexer-form');
	hide([document.querySelector('#add-error')]);
	
	// Clear form inputs
	form.querySelectorAll('input').forEach(el => {
		if (el.id === 'add-categories-input') {
			el.value = '7030';
		} else {
			el.value = '';
		}
	});
	form.querySelector('#add-type-input').value = 'newznab';
	
	showWindow('add-indexer-window');
}

function saveAddIndexer() {
	usingApiKey()
	.then(api_key => {
		const form = document.querySelector('#add-indexer-form');
		const data = {
			name: form.querySelector('#add-name-input').value,
			base_url: form.querySelector('#add-baseurl-input').value,
			api_key: form.querySelector('#add-apikey-input').value,
			indexer_type: form.querySelector('#add-type-input').value,
			categories: form.querySelector('#add-categories-input').value || '7030'
		};
		
		sendAPI('POST', '/indexers', api_key, {}, data)
		.then(response => response.json())
		.then(json => {
			if (json.error) {
				const error = document.querySelector('#add-error');
				error.innerText = json.error;
				hide([], [error]);
			} else {
				loadIndexers(api_key);
				closeWindow();
			}
		})
		.catch(e => {
			const error = document.querySelector('#add-error');
			error.innerText = 'Failed to add indexer';
			hide([], [error]);
		});
	});
}

function loadEditIndexer(api_key, id) {
	const form = document.querySelector('#edit-indexer-form');
	form.dataset.id = id;
	hide([document.querySelector('#edit-error')]);
	
	fetchAPI(`/indexers/${id}`, api_key)
	.then(json => {
		if (json.result) {
			const indexer = json.result;
			form.querySelector('#edit-name-input').value = indexer.name || '';
			form.querySelector('#edit-baseurl-input').value = indexer.base_url || '';
			form.querySelector('#edit-apikey-input').value = indexer.api_key || '';
			form.querySelector('#edit-type-input').value = indexer.indexer_type || 'newznab';
			form.querySelector('#edit-categories-input').value = indexer.categories || '7030';
			form.querySelector('#edit-enabled-input').checked = indexer.enabled === 1;
			
			showWindow('edit-indexer-window');
		}
	})
	.catch(e => {
		console.error('Failed to load indexer:', e);
	});
}

function saveEditIndexer() {
	usingApiKey()
	.then(api_key => {
		const form = document.querySelector('#edit-indexer-form');
		const id = form.dataset.id;
		const data = {
			name: form.querySelector('#edit-name-input').value,
			base_url: form.querySelector('#edit-baseurl-input').value,
			api_key: form.querySelector('#edit-apikey-input').value,
			indexer_type: form.querySelector('#edit-type-input').value,
			categories: form.querySelector('#edit-categories-input').value || '7030',
			enabled: form.querySelector('#edit-enabled-input').checked ? 1 : 0
		};
		
		sendAPI('PUT', `/indexers/${id}`, api_key, {}, data)
		.then(response => response.json())
		.then(json => {
			if (json.error) {
				const error = document.querySelector('#edit-error');
				error.innerText = json.error;
				hide([], [error]);
			} else {
				loadIndexers(api_key);
				closeWindow();
			}
		})
		.catch(e => {
			const error = document.querySelector('#edit-error');
			error.innerText = 'Failed to update indexer';
			hide([], [error]);
		});
	});
}

function deleteIndexer() {
	usingApiKey()
	.then(api_key => {
		const id = document.querySelector('#edit-indexer-form').dataset.id;
		sendAPI('DELETE', `/indexers/${id}`, api_key)
		.then(response => {
			loadIndexers(api_key);
			closeWindow();
		})
		.catch(e => {
			const error = document.querySelector('#edit-error');
			error.innerText = 'Failed to delete indexer';
			hide([], [error]);
		});
	});
}

function testIndexer(formId, resultId) {
	usingApiKey()
	.then(api_key => {
		const form = document.querySelector(`#${formId}`);
		const resultEl = document.querySelector(`#${resultId}`);
		const button = formId === 'add-indexer-form' 
			? document.querySelector('#test-add-indexer')
			: document.querySelector('#test-edit-indexer');
		
		// Get form values
		const data = {
			base_url: form.querySelector(`#${formId === 'add-indexer-form' ? 'add' : 'edit'}-baseurl-input`).value,
			api_key: form.querySelector(`#${formId === 'add-indexer-form' ? 'add' : 'edit'}-apikey-input`).value,
			indexer_type: form.querySelector(`#${formId === 'add-indexer-form' ? 'add' : 'edit'}-type-input`).value,
			categories: form.querySelector(`#${formId === 'add-indexer-form' ? 'add' : 'edit'}-categories-input`).value || '7030'
		};
		
		// Show testing state
		button.disabled = true;
		button.innerText = 'Testing...';
		resultEl.innerText = '';
		resultEl.classList.add('hidden');
		
		// Perform test
		sendAPI('POST', '/indexers/test', api_key, {}, data)
		.then(response => response.json())
		.then(json => {
			button.disabled = false;
			button.innerText = 'Test Connection';
			
			if (json.result && json.result.success) {
				resultEl.innerText = `✓ ${json.result.message} (${json.result.response_time_ms}ms)`;
				resultEl.classList.remove('error');
				resultEl.classList.add('success');
			} else {
				resultEl.innerText = `✗ ${json.result ? json.result.message : 'Test failed'}`;
				resultEl.classList.remove('success');
				resultEl.classList.add('error');
			}
			resultEl.classList.remove('hidden');
		})
		.catch(e => {
			button.disabled = false;
			button.innerText = 'Test Connection';
			resultEl.innerText = `✗ Test failed: ${e.message || 'Unknown error'}`;
			resultEl.classList.remove('success');
			resultEl.classList.add('error');
			resultEl.classList.remove('hidden');
		});
	});
}

function loadIndexers(api_key) {
	fetchAPI('/indexers', api_key)
	.then(json => {
		const container = document.querySelector('#indexer-list');
		
		// Remove all existing indexer buttons except the add button
		document.querySelectorAll('#indexer-list > :not(#add-indexer)')
			.forEach(el => el.remove());
		
		if (json.result && json.result.length > 0) {
			json.result.forEach(indexer => {
				const entry = document.createElement('button');
				entry.onclick = () => loadEditIndexer(api_key, indexer.id);
				
				// Show name and type, with visual indicator if disabled
				const typeLabel = indexer.indexer_type === 'newznab' ? 'Newznab' : 'Torznab';
				const statusIndicator = indexer.enabled ? '' : ' (Disabled)';
				entry.innerText = `${indexer.name} (${typeLabel})${statusIndicator}`;
				
				// Add visual styling for disabled indexers
				if (!indexer.enabled) {
					entry.style.opacity = '0.5';
				}
				
				container.appendChild(entry);
			});
		}
	})
	.catch(e => {
		console.error('Failed to load indexers:', e);
	});
}

// Initialize page
usingApiKey()
.then(api_key => {
	loadIndexers(api_key);
	
	// Set up event listeners
	document.querySelector('#add-indexer').onclick = loadAddIndexer;
	document.querySelector('#submit-indexer-add').onclick = saveAddIndexer;
	document.querySelector('#submit-indexer-edit').onclick = saveEditIndexer;
	document.querySelector('#delete-indexer-edit').onclick = deleteIndexer;
	document.querySelector('#test-add-indexer').onclick = () => testIndexer('add-indexer-form', 'add-test-result');
	document.querySelector('#test-edit-indexer').onclick = () => testIndexer('edit-indexer-form', 'edit-test-result');
});
