// Settings: Connect (notification connections)
// Sonarr/Radarr-style two-step flow:
// 1. Provider picker grid
// 2. Config modal with Name, Triggers, provider fields

var PROVIDER_LABELS = {
	apprise: 'Apprise',
	custom_script: 'Custom Script',
	discord: 'Discord',
	prowl: 'Prowl',
	webhook: 'Webhook'
};

var PROVIDER_INFO = {
	apprise: 'Connect to a self-hosted Apprise API server, or enter stateless Apprise URLs directly.',
	custom_script: 'Testing will execute the script with the EventType set to Test, ensure your script handles this correctly',
	discord: 'Paste your Discord channel webhook URL from Server Settings \u2192 Integrations \u2192 Webhooks.',
	prowl: 'Requires a Prowl API key from prowlapp.com.',
	webhook: ''
};

var providers = {};   // { provider_type: { fields: [...] } }
var editingId = null; // null = adding new, number = editing existing
var editingProviderType = null;
var currentApiKey = null;

// =====================
// Utility
// =====================

function providerLabel(type) {
	return PROVIDER_LABELS[type] || type;
}

function clearElement(el) {
	while (el.firstChild) el.removeChild(el.firstChild);
}

function buildSettingsFields(containerId, providerType, existing) {
	var container = document.getElementById(containerId);
	clearElement(container);

	var fields = (providers[providerType] || {}).fields || [];
	if (!fields.length) return;

	var table = document.createElement('table');
	for (var i = 0; i < fields.length; i++) {
		var field = fields[i];
		if (field.type === 'keyvalue') continue;
		var tr = document.createElement('tr');
		var th = document.createElement('th');
		var label = document.createElement('label');
		label.textContent = field.label;
		label.htmlFor = containerId + '-field-' + field.name;
		th.appendChild(label);

		var td = document.createElement('td');
		var input;
		if (field.type === 'select') {
			input = document.createElement('select');
			input.id = containerId + '-field-' + field.name;
			for (var j = 0; j < (field.options || []).length; j++) {
				var option = document.createElement('option');
				option.value = field.options[j];
				option.textContent = field.options[j];
				input.appendChild(option);
			}
			if (existing && existing[field.name]) input.value = existing[field.name];
			else if (field.default) input.value = field.default;
		} else {
			input = document.createElement('input');
			input.type = (field.type === 'password') ? 'password' : 'text';
			input.id = containerId + '-field-' + field.name;
			if (field.placeholder) input.placeholder = field.placeholder;
			if (existing && existing[field.name]) input.value = existing[field.name];
		}
		input.dataset.fieldName = field.name;
		td.appendChild(input);
		tr.appendChild(th);
		tr.appendChild(td);
		table.appendChild(tr);
	}
	container.appendChild(table);
}

function collectSettings(containerId) {
	var container = document.getElementById(containerId);
	var settings = {};
	var els = container.querySelectorAll('[data-field-name]');
	for (var i = 0; i < els.length; i++) {
		settings[els[i].dataset.fieldName] = els[i].value;
	}
	return settings;
}

function setTestButtonState(btn, state) {
	btn.classList.remove('show-success', 'show-fail');
	if (state === 'success') btn.classList.add('show-success');
	else if (state === 'fail') btn.classList.add('show-fail');
}

// =====================
// Connection cards
// =====================

function loadConnections() {
	fetchAPI('/notifications', currentApiKey)
		.then(function(data) {
			var list = document.getElementById('connection-list');
			clearElement(list);
			var connections = data.result || [];
			var noMsg = document.getElementById('no-connections');
			noMsg.style.display = connections.length ? 'none' : '';

			for (var i = 0; i < connections.length; i++) {
				var conn = connections[i];
				var card = document.createElement('button');
				card.className = 'connection-card';
				card.dataset.id = conn.id;

				var nameDiv = document.createElement('div');
				nameDiv.className = 'card-name';
				nameDiv.textContent = conn.name;

				var provDiv = document.createElement('div');
				provDiv.className = 'card-provider';
				provDiv.textContent = providerLabel(conn.provider_type);

				card.appendChild(nameDiv);
				card.appendChild(provDiv);

				if (!conn.enabled) {
					var badge = document.createElement('span');
					badge.className = 'card-badge disabled';
					badge.textContent = 'Disabled';
					card.appendChild(badge);
				}

				(function(connId) {
					card.onclick = function() { openEditWindow(connId); };
				})(conn.id);

				list.appendChild(card);
			}
		});
}

// =====================
// Provider picker
// =====================

function openProviderPicker() {
	var grid = document.getElementById('provider-grid');
	clearElement(grid);

	var types = Object.keys(providers);
	for (var i = 0; i < types.length; i++) {
		var type = types[i];
		var card = document.createElement('button');
		card.className = 'provider-card';

		var nameSpan = document.createElement('span');
		nameSpan.className = 'provider-card-name';
		nameSpan.textContent = providerLabel(type);
		card.appendChild(nameSpan);

		(function(providerType) {
			card.onclick = function() {
				closeWindow();
				openAddWindow(providerType);
			};
		})(type);

		grid.appendChild(card);
	}

	showWindow('choose-provider-window');
}

// =====================
// Add connection
// =====================

function openAddWindow(providerType) {
	editingId = null;
	editingProviderType = providerType;

	// Update modal title
	var win = document.getElementById('edit-notification-window');
	win.querySelector('.window-header h2').textContent =
		'Add Connection - ' + providerLabel(providerType);

	// Show/hide info banner
	var info = document.getElementById('edit-info');
	var infoText = PROVIDER_INFO[providerType] || '';
	if (infoText) {
		info.textContent = infoText;
		info.classList.remove('hidden');
	} else {
		info.classList.add('hidden');
	}

	// Reset form
	document.getElementById('edit-notification-form').reset();
	document.getElementById('edit-name-input').value = providerLabel(providerType);
	document.getElementById('edit-error').classList.add('hidden');
	setTestButtonState(document.getElementById('test-edit-connection'), 'idle');

	// Default trigger states
	document.getElementById('edit-on-download').checked = true;
	document.getElementById('edit-on-volume-add').checked = true;
	document.getElementById('edit-on-app-update').checked = true;

	// Build provider-specific fields
	buildSettingsFields('edit-settings-fields', providerType, null);

	// Hide delete button for new connections
	document.getElementById('delete-connection-edit').style.display = 'none';

	showWindow('edit-notification-window');
}

// =====================
// Edit connection
// =====================

function openEditWindow(id) {
	editingId = id;

	document.getElementById('edit-error').classList.add('hidden');
	setTestButtonState(document.getElementById('test-edit-connection'), 'idle');

	fetchAPI('/notifications/' + id, currentApiKey)
		.then(function(data) {
			var conn = data.result;
			editingProviderType = conn.provider_type;

			// Update modal title
			var win = document.getElementById('edit-notification-window');
			win.querySelector('.window-header h2').textContent =
				'Edit Connection - ' + providerLabel(conn.provider_type);

			// Show/hide info banner
			var info = document.getElementById('edit-info');
			var infoText = PROVIDER_INFO[conn.provider_type] || '';
			if (infoText) {
				info.textContent = infoText;
				info.classList.remove('hidden');
			} else {
				info.classList.add('hidden');
			}

			document.getElementById('edit-name-input').value = conn.name;
			buildSettingsFields('edit-settings-fields', conn.provider_type, conn.settings);

			document.getElementById('edit-on-download').checked = !!conn.on_download;
			document.getElementById('edit-on-volume-add').checked = !!conn.on_volume_add;
			document.getElementById('edit-on-app-update').checked = !!conn.on_application_update;

			// Show delete button for existing connections
			document.getElementById('delete-connection-edit').style.display = '';

			showWindow('edit-notification-window');
		});
}

// =====================
// Save (add or update)
// =====================

document.getElementById('edit-notification-form').onsubmit = function(e) {
	e.preventDefault();
	var data = {
		name: document.getElementById('edit-name-input').value,
		provider_type: editingProviderType,
		settings: collectSettings('edit-settings-fields'),
		on_download: document.getElementById('edit-on-download').checked,
		on_volume_add: document.getElementById('edit-on-volume-add').checked,
		on_application_update: document.getElementById('edit-on-app-update').checked,
		enabled: true
	};

	var method = editingId ? 'PUT' : 'POST';
	var url = editingId ? '/notifications/' + editingId : '/notifications';

	sendAPI(method, url, currentApiKey, {}, data)
		.then(function(r) { return r.json(); })
		.then(function(resp) {
			if (resp.error) {
				var errEl = document.getElementById('edit-error');
				errEl.textContent = (resp.result && resp.result.message) || resp.error;
				errEl.classList.remove('hidden');
			} else {
				closeWindow();
				loadConnections();
			}
		});
};

// =====================
// Delete
// =====================

document.getElementById('delete-connection-edit').onclick = function() {
	if (editingId) {
		sendAPI('DELETE', '/notifications/' + editingId, currentApiKey)
			.then(function() {
				closeWindow();
				loadConnections();
			});
	}
};

// =====================
// Test
// =====================

document.getElementById('test-edit-connection').onclick = function() {
	var btn = this;
	setTestButtonState(btn, 'idle');

	if (!editingId) {
		// Save first, then test
		var data = {
			name: document.getElementById('edit-name-input').value,
			provider_type: editingProviderType,
			settings: collectSettings('edit-settings-fields'),
			on_download: document.getElementById('edit-on-download').checked,
			on_health_check: document.getElementById('edit-on-health-check').checked,
			on_volume_add: document.getElementById('edit-on-volume-add').checked,
			on_application_update: document.getElementById('edit-on-app-update').checked,
			enabled: true
		};
		sendAPI('POST', '/notifications', currentApiKey, {}, data)
			.then(function(r) { return r.json(); })
			.then(function(resp) {
				if (resp.error) {
					setTestButtonState(btn, 'fail');
					return;
				}
				editingId = resp.result.id;
				// Now test the saved connection
				sendAPI('POST', '/notifications/' + editingId + '/test', currentApiKey)
					.then(function(r) { return r.json(); })
					.then(function(testResp) {
						setTestButtonState(btn,
							(testResp.result && testResp.result.success)
								? 'success' : 'fail');
					})
					.catch(function() { setTestButtonState(btn, 'fail'); });
			})
			.catch(function() { setTestButtonState(btn, 'fail'); });
	} else {
		// Save changes first, then test
		var updateData = {
			name: document.getElementById('edit-name-input').value,
			provider_type: editingProviderType,
			settings: collectSettings('edit-settings-fields'),
			on_download: document.getElementById('edit-on-download').checked,
			on_health_check: document.getElementById('edit-on-health-check').checked,
			on_volume_add: document.getElementById('edit-on-volume-add').checked,
			on_application_update: document.getElementById('edit-on-app-update').checked,
			enabled: true
		};
		sendAPI('PUT', '/notifications/' + editingId, currentApiKey, {}, updateData)
			.then(function(r) { return r.json(); })
			.then(function(resp) {
				if (resp.error) {
					setTestButtonState(btn, 'fail');
					return;
				}
				sendAPI('POST', '/notifications/' + editingId + '/test', currentApiKey)
					.then(function(r) { return r.json(); })
					.then(function(testResp) {
						setTestButtonState(btn,
							(testResp.result && testResp.result.success)
								? 'success' : 'fail');
					})
					.catch(function() { setTestButtonState(btn, 'fail'); });
			})
			.catch(function() { setTestButtonState(btn, 'fail'); });
	}
};

// =====================
// Init
// =====================

document.getElementById('add-connection').onclick = function() {
	openProviderPicker();
};

usingApiKey()
.then(function(api_key) {
	currentApiKey = api_key;
	fetchAPI('/notifications/providers', api_key)
		.then(function(data) {
			providers = data.result || {};
			loadConnections();
		});
});
