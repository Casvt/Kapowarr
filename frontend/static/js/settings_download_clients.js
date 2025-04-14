function createUsernameInput(id) {
	const username_row = document.createElement('tr');
	const username_header = document.createElement('th');
	const username_label = document.createElement('label');
	username_label.innerText = 'Username';
	username_label.setAttribute('for', id);
	username_header.appendChild(username_label);
	username_row.appendChild(username_header)
	const username_container = document.createElement('td');
	const username_input = document.createElement('input');
	username_input.type = 'text'
	username_input.id = id;
	username_container.appendChild(username_input);
	username_row.appendChild(username_container);
	return username_row;
};

function createPasswordInput(id) {
	const password_row = document.createElement('tr');
	const password_header = document.createElement('th');
	const password_label = document.createElement('label');
	password_label.innerText = 'Password';
	password_label.setAttribute('for', id);
	password_header.appendChild(password_label);
	password_row.appendChild(password_header)
	const password_container = document.createElement('td');
	const password_input = document.createElement('input');
	password_input.type = 'password'
	password_input.id = id;
	password_container.appendChild(password_input);
	password_row.appendChild(password_container);
	return password_row;
};

function createApiTokenInput(id) {
	const token_row = document.createElement('tr');
	const token_header = document.createElement('th');
	const token_label = document.createElement('label');
	token_label.innerText = 'API Token';
	token_label.setAttribute('for', id);
	token_header.appendChild(token_label);
	token_row.appendChild(token_header)
	const token_container = document.createElement('td');
	const token_input = document.createElement('input');
	token_input.type = 'text'
	token_input.id = id;
	token_container.appendChild(token_input);
	token_row.appendChild(token_container);
	return token_row;
};

function loadEditTorrent(api_key, id) {
	const form = document.querySelector('#edit-torrent-form tbody');
	form.dataset.id = id;
	form.querySelectorAll(
		'tr:not(:has(input#edit-title-input, input#edit-baseurl-input))'
	).forEach(el => el.remove());
	document.querySelector('#test-torrent-edit').classList.remove(
		'show-success', 'show-fail'
	)
	hide([document.querySelector('#edit-error')]);

	fetchAPI(`/externalclients/${id}`, api_key)
	.then(client_data => {
		const client_type = client_data.result.client_type;
		form.dataset.type = client_type;
		fetchAPI('/externalclients/options', api_key)
		.then(options => {
			const client_options = options.result[client_type];

			form.querySelector('#edit-title-input').value =
				client_data.result.title || '';

			form.querySelector('#edit-baseurl-input').value =
				client_data.result.base_url;

			if (client_options.includes('username')) {
				const username_input = createUsernameInput('edit-username-input');
				username_input.querySelector('input').value =
					client_data.result.username || '';
				form.appendChild(username_input);
			};

			if (client_options.includes('password')) {
				const password_input = createPasswordInput('edit-password-input');
				password_input.querySelector('input').value =
					client_data.result.password || '';
				form.appendChild(password_input);
			};

			if (client_options.includes('api_token')) {
				const token_input = createApiTokenInput('edit-token-input');
				token_input.querySelector('input').value =
					client_data.result.api_token || '';
				form.appendChild(token_input);
			};

			showWindow('edit-torrent-window');
		});
	});
};

function saveEditTorrent() {
	usingApiKey()
	.then(api_key => {
		testEditTorrent(api_key).then(result => {
			if (!result)
				return;

			const form = document.querySelector('#edit-torrent-form tbody');
			const id = form.dataset.id;
			const data = {
				title: form.querySelector('#edit-title-input').value,
				base_url: form.querySelector('#edit-baseurl-input').value,
				username: form.querySelector('#edit-username-input')?.value || null,
				password: form.querySelector('#edit-password-input')?.value || null,
				api_token: form.querySelector('#edit-token-input')?.value || null
			};
			sendAPI('PUT', `/externalclients/${id}`, api_key, {}, data)
			.then(response => {
				loadTorrentClients(api_key);
				closeWindow();
			})
			.catch(e => {
				if (e.status === 400) {
					// Client is downloading
					const error = document.querySelector('#edit-error');
					error.innerText = '*Client is downloading';
					hide([], [error]);
				};
			});
		});
	});
};

async function testEditTorrent(api_key) {
	const error = document.querySelector('#edit-error');
	hide([error]);
	const form = document.querySelector('#edit-torrent-form tbody');
	const test_button = document.querySelector('#test-torrent-edit');
	test_button.classList.remove('show-success', 'show-fail');
	const data = {
		client_type: form.dataset.type,
		base_url: form.querySelector('#edit-baseurl-input').value,
		username: form.querySelector('#edit-username-input')?.value || null,
		password: form.querySelector('#edit-password-input')?.value || null,
		api_token: form.querySelector('#edit-token-input')?.value || null,
	};
	return await sendAPI('POST', '/externalclients/test', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.result.success)
			// Test successful
			test_button.classList.add('show-success');
		else {
			// Test failed
			test_button.classList.add('show-fail');
			error.innerText = json.result.description;
			hide([], [error]);
		};
		return json.result.success;
	});
};

function deleteTorrent(api_key) {
	const id = document.querySelector('#edit-torrent-form tbody').dataset.id;
	sendAPI('DELETE', `/externalclients/${id}`, api_key)
	.then(response => {
		loadTorrentClients(api_key);
		closeWindow();
	})
	.catch(e => {
		if (e.status === 400) {
			// Client is downloading
			const error = document.querySelector('#edit-error');
			error.innerText = '*Client is downloading';
			hide([], [error]);
		};
	});
};

//Torrent Clients
function loadTorrentList(api_key) {
    const table = document.querySelector('#choose-torrent-list');
    table.innerHTML = '';

    // Use download_type=2 for TORRENT
    fetchAPI('/externalclients/options', api_key, { download_type: '2' })
    .then(json => {
        Object.keys(json.result).forEach(c => {
            const entry = document.createElement('button');
            entry.innerText = c;
            entry.onclick = e => loadAddTorrent(api_key, c);
            table.appendChild(entry);
        });
        showWindow('choose-torrent-window');
    });
};

function loadAddTorrent(api_key, client_type) {
	const form = document.querySelector('#add-torrent-form tbody');
	form.dataset.type = client_type;
	form.querySelectorAll(
		'tr:not(:has(input#add-title-input, input#add-baseurl-input))'
	).forEach(el => el.remove());
	document.querySelector('#test-torrent-add').classList.remove(
		'show-success', 'show-fail'
	)
	form.querySelectorAll(
		'#add-title-input, #add-baseurl-input'
	).forEach(el => el.value = '');

	fetchAPI('/externalclients/options', api_key)
	.then(json => {
		const client_options = json.result[client_type];

		if (client_options.includes('username'))
			form.appendChild(createUsernameInput('add-username-input'));

		if (client_options.includes('password'))
			form.appendChild(createPasswordInput('add-password-input'));

		if (client_options.includes('api_token'))
			form.appendChild(createApiTokenInput('add-token-input'));

		showWindow('add-torrent-window');
	});
};

function saveAddTorrent() {
	usingApiKey()
	.then(api_key => {
		testAddTorrent(api_key).then(result => {
			if (!result)
				return;

			const form = document.querySelector('#add-torrent-form tbody');
			const data = {
				client_type: form.dataset.type,
				title: form.querySelector('#add-title-input').value,
				base_url: form.querySelector('#add-baseurl-input').value,
				username: form.querySelector('#add-username-input')?.value || null,
				password: form.querySelector('#add-password-input')?.value || null,
				api_token: form.querySelector('#add-token-input')?.value || null
			};
			sendAPI('POST', '/externalclients', api_key, {}, data)
			.then(response => {
				loadTorrentClients(api_key);
				closeWindow();
			});
		});
	});
};

async function testAddTorrent(api_key) {
	const error = document.querySelector('#add-error');
	hide([error]);
	const form = document.querySelector('#add-torrent-form tbody');
	const test_button = document.querySelector('#test-torrent-add');
	test_button.classList.remove('show-success', 'show-fail');
	const data = {
		client_type: form.dataset.type,
		base_url: form.querySelector('#add-baseurl-input').value,
		username: form.querySelector('#add-username-input')?.value || null,
		password: form.querySelector('#add-password-input')?.value || null,
		api_token: form.querySelector('#add-token-input')?.value || null,
	};
	return await sendAPI('POST', '/externalclients/test', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.result.success)
			// Test successful
			test_button.classList.add('show-success');
		else
			// Test failed
			test_button.classList.add('show-fail');
			error.innerText = json.result.description;
			hide([], [error]);
		return json.result.success;
	});
};

function loadTorrentClients(api_key) {
    // Use download_type=2 for TORRENT
    fetchAPI('/externalclients', api_key, { download_type: '2' })
    .then(json => {
        const table = document.querySelector('#torrent-client-list');
        document.querySelectorAll('#torrent-client-list > :not(:first-child)')
            .forEach(el => el.remove());

        json.result.forEach(client => {
            const entry = document.createElement('button');
            entry.onclick = (e) => loadEditTorrent(api_key, client.id);
            entry.innerText = client.title;
            table.appendChild(entry);
        });
    });
};

function fillCredentials(api_key) {
	fetchAPI('/credentials', api_key)
	.then(json => {
		document.querySelectorAll('#mega-creds, #pixeldrain-creds, #airdcpp-creds').forEach(
			c => c.innerHTML = ''
		);
		json.result.forEach(result => {
			if (result.source === 'mega') {
				const row = document.querySelector('.pre-build-els .mega-cred-entry').cloneNode(true);
				row.querySelector('.mega-email').innerText = result.email;
				row.querySelector('.mega-password').innerText = result.password;
				row.querySelector('.delete-credential').onclick =
					e => sendAPI('DELETE', `/credentials/${result.id}`, api_key)
						.then(response => row.remove());
				document.querySelector('#mega-creds').appendChild(row);
			}
			else if (result.source === 'pixeldrain') {
				const row = document.querySelector('.pre-build-els .pixeldrain-cred-entry').cloneNode(true);
				row.querySelector('.pixeldrain-key').innerText = result.api_key;
				row.querySelector('.delete-credential').onclick =
					e => sendAPI('DELETE', `/credentials/${result.id}`, api_key)
						.then(response => row.remove());
				document.querySelector('#pixeldrain-creds').appendChild(row);
			}
			else if (result.source === 'airdcpp') {
				const row = document.querySelector('.pre-build-els .airdcpp-cred-entry').cloneNode(true);
				row.querySelector('.airdcpp-url').innerText = result.api_key;
				row.querySelector('.airdcpp-username').innerText = result.username;
				row.querySelector('.delete-credential').onclick =
					e => sendAPI('DELETE', `/credentials/${result.id}`, api_key)
						.then(response => row.remove());
				document.querySelector('#airdcpp-creds').appendChild(row);
			}
		});
	});
	
	document.querySelectorAll('#mega-form input, #pixeldrain-form input, #airdcpp-form input').forEach(
		i => i.value = ''
	);
};

function addCredential() {
	hide([document.querySelector('#builtin-window p.error')]);

	const source = document.querySelector("#builtin-window").dataset.tag;
	let data;
	if (source === 'mega')
		data = {
			source: source,
			email: document.querySelector('#add-mega .mega-email input').value,
			password: document.querySelector('#add-mega .mega-password input').value
		};

	else if (source === 'pixeldrain')
		data = {
			source: source,
			api_key: document.querySelector('#add-pixeldrain .pixeldrain-key input').value
		};
	
	else if (source === 'airdcpp')
		data = {
			source: source,
			api_key: document.querySelector('#add-airdcpp .airdcpp-url input').value,
			username: document.querySelector('#add-airdcpp .airdcpp-username input').value,
			password: document.querySelector('#add-airdcpp .airdcpp-password input').value
		};
	
	usingApiKey().then(api_key => {
		sendAPI('POST', '/credentials', api_key, {}, data)
		.then(response => fillCredentials(api_key))
		.catch(e => {
			if (e.status === 400)
				e.json().then(json => {
					document.querySelector('#builtin-window p.error').innerText = json.result.description;
					hide([], [document.querySelector('#builtin-window p.error')]);
				});
			else
				console.log(e);
		});
	});
};

// Add handling for Newznab credentials
function setupCredentialManagement(source, fieldMapping, api_key) {
    const credContainer = document.getElementById(`${source}-creds`);
    const addForm = document.getElementById(`add-${source}`);
    const templateRow = document.querySelector(`.${source}-cred-entry`);
    
    if (!credContainer || !addForm || !templateRow) return;
    
    // Load credentials
    loadCredentials();
    
    // Set up form submission
    const form = document.getElementById(`${source}-form`);
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        addCredential();
    });
    
    // Function to load credentials
    function loadCredentials() {
        credContainer.innerHTML = '';
        
        // Use fetchAPI for GET requests
        fetchAPI('/credentials', api_key, { source: source })
        .then(response => {
            response.result.forEach(cred => {
                addCredentialRow(cred);
            });
        });
    }
    
    // Function to add a credential row to the UI
    function addCredentialRow(cred) {
        const row = templateRow.cloneNode(true);
        row.dataset.id = cred.id;
        
        // Set values in the row
        if (fieldMapping.nameField && row.querySelector(`.${source}-name`)) {
            row.querySelector(`.${source}-name`).textContent = cred[fieldMapping.nameField] || 'unnamed';
        }
        
        if (fieldMapping.urlField && row.querySelector(`.${source}-url`)) {
            row.querySelector(`.${source}-url`).textContent = cred[fieldMapping.urlField] || '';
        }
        
        if (fieldMapping.apiKeyField && row.querySelector(`.${source}-apikey`)) {
            const apiKey = cred[fieldMapping.apiKeyField] || '';
            row.querySelector(`.${source}-apikey`).textContent = 
                apiKey.length > 10 ? apiKey.substring(0, 8) + '...' : apiKey;
        }
        
        // Set up delete button
        const deleteBtn = row.querySelector('.delete-credential');
        deleteBtn.addEventListener('click', function() {
            deleteCredential(cred.id);
        });
        
        credContainer.appendChild(row);
    }
    
    // Function to add a new credential
    function addCredential() {
        const nameInput = addForm.querySelector(`.${source}-name input`);
        const urlInput = addForm.querySelector(`.${source}-url input`);
        const apiKeyInput = addForm.querySelector(`.${source}-apikey input`);
        
        if (!nameInput || !urlInput || !apiKeyInput) return;
        
        const data = {};
        data[fieldMapping.nameField] = nameInput.value;
        data[fieldMapping.urlField] = urlInput.value;
        data[fieldMapping.apiKeyField] = apiKeyInput.value;
        
        sendAPI('POST', '/credentials', api_key, {}, {
            source: source,
            ...data
        })
        .then(response => {
            // Clear inputs
            nameInput.value = '';
            urlInput.value = '';
            apiKeyInput.value = '';
            
            // Reload credentials
            loadCredentials();
        })
        .catch(error => {
            console.error('Error adding credential:', error);
        });
    }
    
    // Function to delete a credential
    function deleteCredential(id) {
        sendAPI('DELETE', `/credentials/${id}`, api_key)
        .then(response => {
            loadCredentials();
        })
        .catch(error => {
            console.error('Error deleting credential:', error);
        });
    }
}

//Usenet Clients
function loadUsenetList(api_key) {
    const table = document.querySelector('#choose-usenet-list');
    table.innerHTML = '';

    fetchAPI('/externalclients/options', api_key, { download_type: '3' })
    .then(json => {
        Object.keys(json.result).forEach(c => {
            const entry = document.createElement('button');
            entry.innerText = c;
            entry.onclick = e => loadAddUsenet(api_key, c);
            table.appendChild(entry);
        });
        showWindow('choose-usenet-window');
    });
};

function loadAddUsenet(api_key, client_type) {
    const form = document.querySelector('#add-usenet-form tbody');
    form.dataset.type = client_type;
    form.querySelectorAll(
        'tr:not(:has(input#add-usenet-title-input, input#add-usenet-baseurl-input))'
    ).forEach(el => el.remove());
    document.querySelector('#test-usenet-add').classList.remove(
        'show-success', 'show-fail'
    )
    form.querySelectorAll(
        '#add-usenet-title-input, #add-usenet-baseurl-input'
    ).forEach(el => el.value = '');

    fetchAPI('/externalclients/options', api_key)
    .then(json => {
        const client_options = json.result[client_type];

        if (client_options.includes('username'))
            form.appendChild(createUsernameInput('add-usenet-username-input'));

        if (client_options.includes('password'))
            form.appendChild(createPasswordInput('add-usenet-password-input'));

        if (client_options.includes('api_token'))
            form.appendChild(createApiTokenInput('add-usenet-token-input'));

        showWindow('add-usenet-window');
    });
};

function loadUsenetClients(api_key) {
    fetchAPI('/externalclients', api_key, { download_type: '3' })
    .then(json => {
        const table = document.querySelector('#usenet-client-list');
        document.querySelectorAll('#usenet-client-list > :not(:first-child)')
            .forEach(el => el.remove());

        json.result.forEach(client => {
            const entry = document.createElement('button');
            entry.onclick = (e) => loadEditUsenet(api_key, client.id);
            entry.innerText = client.title;
            table.appendChild(entry);
        });
    });
};

function loadEditUsenet(api_key, id) {
    const form = document.querySelector('#edit-usenet-form tbody');
    form.dataset.id = id;
    form.querySelectorAll(
        'tr:not(:has(input#edit-usenet-title-input, input#edit-usenet-baseurl-input))'
    ).forEach(el => el.remove());
    document.querySelector('#test-usenet-edit').classList.remove(
        'show-success', 'show-fail'
    )
    hide([document.querySelector('#edit-usenet-error')]);

    fetchAPI(`/externalclients/${id}`, api_key)
    .then(client_data => {
        const client_type = client_data.result.client_type;
        form.dataset.type = client_type;
        fetchAPI('/externalclients/options', api_key)
        .then(options => {
            const client_options = options.result[client_type];

            form.querySelector('#edit-usenet-title-input').value =
                client_data.result.title || '';

            form.querySelector('#edit-usenet-baseurl-input').value =
                client_data.result.base_url;

            if (client_options.includes('username')) {
                const username_input = createUsernameInput('edit-usenet-username-input');
                username_input.querySelector('input').value =
                    client_data.result.username || '';
                form.appendChild(username_input);
            };

            if (client_options.includes('password')) {
                const password_input = createPasswordInput('edit-usenet-password-input');
                password_input.querySelector('input').value =
                    client_data.result.password || '';
                form.appendChild(password_input);
            };

            if (client_options.includes('api_token')) {
                const token_input = createApiTokenInput('edit-usenet-token-input');
                token_input.querySelector('input').value =
                    client_data.result.api_token || '';
                form.appendChild(token_input);
            };

            showWindow('edit-usenet-window');
        });
    });
}

function saveEditUsenet() {
    usingApiKey()
    .then(api_key => {
        testEditUsenet(api_key).then(result => {
            if (!result)
                return;

            const form = document.querySelector('#edit-usenet-form tbody');
            const id = form.dataset.id;
            const data = {
                title: form.querySelector('#edit-usenet-title-input').value,
                base_url: form.querySelector('#edit-usenet-baseurl-input').value,
                username: form.querySelector('#edit-usenet-username-input')?.value || null,
                password: form.querySelector('#edit-usenet-password-input')?.value || null,
                api_token: form.querySelector('#edit-usenet-token-input')?.value || null
            };
            sendAPI('PUT', `/externalclients/${id}`, api_key, {}, data)
            .then(response => {
                loadUsenetClients(api_key);
                closeWindow();
            })
            .catch(e => {
                if (e.status === 400) {
                    // Client is downloading
                    const error = document.querySelector('#edit-usenet-error');
                    error.innerText = '*Client is downloading';
                    hide([], [error]);
                }
            });
        });
    });
}

async function testEditUsenet(api_key) {
    const error = document.querySelector('#edit-usenet-error');
    hide([error]);
    const form = document.querySelector('#edit-usenet-form tbody');
    const test_button = document.querySelector('#test-usenet-edit');
    test_button.classList.remove('show-success', 'show-fail');
    const data = {
        client_type: form.dataset.type,
        base_url: form.querySelector('#edit-usenet-baseurl-input').value,
        username: form.querySelector('#edit-usenet-username-input')?.value || null,
        password: form.querySelector('#edit-usenet-password-input')?.value || null,
        api_token: form.querySelector('#edit-usenet-token-input')?.value || null,
    };
    return await sendAPI('POST', '/externalclients/test', api_key, {}, data)
    .then(response => response.json())
    .then(json => {
        if (json.result.success)
            // Test successful
            test_button.classList.add('show-success');
        else {
            // Test failed
            test_button.classList.add('show-fail');
            error.innerText = json.result.description;
            hide([], [error]);
        }
        return json.result.success;
    });
}

function deleteUsenet(api_key) {
    const id = document.querySelector('#edit-usenet-form tbody').dataset.id;
    sendAPI('DELETE', `/externalclients/${id}`, api_key)
    .then(response => {
        loadUsenetClients(api_key);
        closeWindow();
    })
    .catch(e => {
        if (e.status === 400) {
            // Client is downloading
            const error = document.querySelector('#edit-usenet-error');
            error.innerText = '*Client is downloading';
            hide([], [error]);
        }
    });
}

function saveAddUsenet() {
    usingApiKey()
    .then(api_key => {
        testAddUsenet(api_key).then(result => {
            if (!result)
                return;

            const form = document.querySelector('#add-usenet-form tbody');
            const data = {
                client_type: form.dataset.type,
                title: form.querySelector('#add-usenet-title-input').value,
                base_url: form.querySelector('#add-usenet-baseurl-input').value,
                username: form.querySelector('#add-usenet-username-input')?.value || null,
                password: form.querySelector('#add-usenet-password-input')?.value || null,
                api_token: form.querySelector('#add-usenet-token-input')?.value || null
            };
            sendAPI('POST', '/externalclients', api_key, {}, data)
            .then(response => {
                loadUsenetClients(api_key);
                closeWindow();
            });
        });
    });
}

async function testAddUsenet(api_key) {
    const error = document.querySelector('#add-usenet-error');
    hide([error]);
    const form = document.querySelector('#add-usenet-form tbody');
    const test_button = document.querySelector('#test-usenet-add');
    test_button.classList.remove('show-success', 'show-fail');
    const data = {
        client_type: form.dataset.type,
        base_url: form.querySelector('#add-usenet-baseurl-input').value,
        username: form.querySelector('#add-usenet-username-input')?.value || null,
        password: form.querySelector('#add-usenet-password-input')?.value || null,
        api_token: form.querySelector('#add-usenet-token-input')?.value || null,
    };
    return await sendAPI('POST', '/externalclients/test', api_key, {}, data)
    .then(response => response.json())
    .then(json => {
        if (json.result.success)
            // Test successful
            test_button.classList.add('show-success');
        else {
            // Test failed
            test_button.classList.add('show-fail');
            error.innerText = json.result.description;
            hide([], [error]);
        }
        return json.result.success;
    });
}

// Set up document event listeners when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Newznab credentials
    usingApiKey().then(api_key => {
        setupCredentialManagement('newznab', {
            nameField: 'email',      // Using email field to store the name
            urlField: 'username',    // Using username field to store the API URL
            apiKeyField: 'api_key'   // Using api_key field as intended
        }, api_key);
    });
    
    // Add event listener for the Newznab client button
    document.getElementById('newznab-client').addEventListener('click', function() {
        document.getElementById('builtin-window').dataset.tag = 'newznab';
        showWindow('builtin-window');
    });
    
    // Set up form action handlers
    document.querySelector('#edit-torrent-form').action = 'javascript:saveEditTorrent()';
    document.querySelector('#add-torrent-form').action = 'javascript:saveAddTorrent()';
    document.querySelector('#edit-usenet-form').action = 'javascript:saveEditUsenet()';
    document.querySelector('#add-usenet-form').action = 'javascript:saveAddUsenet()';
    document.querySelectorAll('#cred-container > form').forEach(
        f => f.action = 'javascript:addCredential();'
    );
    
    // Set up builtin client buttons
    document.querySelectorAll('#builtin-client-list > button').forEach(b => {
        const tag = b.dataset.tag;
        b.onclick = e => {
            document.querySelector('#builtin-window').dataset.tag = tag;
            hide([document.querySelector('#builtin-window p.error')]);
            document.querySelectorAll('#builtin-window input').forEach(i => i.value = '');
            showWindow('builtin-window');
        };
    });
});

// Main initialization - only call this once
usingApiKey()
.then(api_key => {
    fillCredentials(api_key);
    loadTorrentClients(api_key);
    loadUsenetClients(api_key);
    
    // Event handlers for torrent clients
    document.querySelector('#delete-torrent-edit').onclick = e => deleteTorrent(api_key);
    document.querySelector('#test-torrent-edit').onclick = e => testEditTorrent(api_key);
    document.querySelector('#test-torrent-add').onclick = e => testAddTorrent(api_key);
    document.querySelector('#add-torrent-client').onclick = e => loadTorrentList(api_key);
    
    // Event handlers for usenet clients
    document.querySelector('#delete-usenet-edit').onclick = e => deleteUsenet(api_key);
    document.querySelector('#test-usenet-edit').onclick = e => testEditUsenet(api_key);
    document.querySelector('#test-usenet-add').onclick = e => testAddUsenet(api_key);
    document.querySelector('#add-usenet-client').onclick = e => loadUsenetList(api_key);
});