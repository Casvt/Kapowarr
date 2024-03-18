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
	document.querySelector('#edit-torrent-window > div > p.error')
		.classList.add('hidden');

	fetch(`${url_base}/api/torrentclients/${id}?api_key=${api_key}`)
	.then(response => response.json())
	.then(client_data => {
		const client_type = client_data.result.type;
		form.dataset.type = client_type;
		fetch(`${url_base}/api/torrentclients/options?api_key=${api_key}`)
		.then(response => response.json())
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
			fetch(`${url_base}/api/torrentclients/${id}?api_key=${api_key}`, {
				'method': 'PUT',
				'headers': {'Content-Type': 'application/json'},
				'body': JSON.stringify(data)
			})
			.then(response => {
				loadTorrentClients(api_key);
				closeWindow();
			});
		});
	});
};

async function testEditTorrent(api_key) {
	const form = document.querySelector('#edit-torrent-form tbody');
	const test_button = document.querySelector('#test-torrent-edit');
	test_button.classList.remove('show-success', 'show-fail');
	const data = {
		type: form.dataset.type,
		base_url: form.querySelector('#edit-baseurl-input').value,
		username: form.querySelector('#edit-username-input')?.value || null,
		password: form.querySelector('#edit-password-input')?.value || null,
		api_token: form.querySelector('#edit-token-input')?.value || null,
	};
	return await fetch(`${url_base}/api/torrentclients/test?api_key=${api_key}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(data)
	})
	.then(response => response.json())
	.then(json => {
		if (json.result.result)
			// Test successful
			test_button.classList.add('show-success');
		else
			// Test failed
			test_button.classList.add('show-fail');
		return json.result.result;
	});
};

function deleteTorrent(api_key) {
	const id = document.querySelector('#edit-torrent-form tbody').dataset.id;
	fetch(`${url_base}/api/torrentclients/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		if (!response.ok) Promise.reject(response.status);
		loadTorrentClients(api_key);
		closeWindow();
	})
	.catch(e => {
		if (e === 400) {
			// Client is downloading
			document.querySelector('#edit-torrent-window > div > p.error')
				.classList.remove('hidden');
		};
	});
};

function loadTorrentList(api_key) {
	const table = document.querySelector('#choose-torrent-list');
	table.innerHTML = '';
	
	fetch(`${url_base}/api/torrentclients/options?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		Object.keys(json.result).forEach(c => {
			const entry = document.createElement('button');
			entry.innerText = c;
			entry.onclick = (e) => loadAddTorrent(api_key, c);
			table.appendChild(entry);
		});
		showWindow('choose-torrent-window');
	});
};

function loadAddTorrent(api_key, type) {
	const form = document.querySelector('#add-torrent-form tbody');
	form.dataset.type = type;
	form.querySelectorAll(
		'tr:not(:has(input#add-title-input, input#add-baseurl-input))'
	).forEach(el => el.remove());
	document.querySelector('#test-torrent-add').classList.remove(
		'show-success', 'show-fail'
	)
	form.querySelectorAll(
		'#add-title-input, #add-baseurl-input'
	).forEach(el => el.value = '');
	
	fetch(`${url_base}/api/torrentclients/options?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const client_options = json.result[type];

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
				type: form.dataset.type,
				title: form.querySelector('#add-title-input').value,
				base_url: form.querySelector('#add-baseurl-input').value,
				username: form.querySelector('#add-username-input')?.value || null,
				password: form.querySelector('#add-password-input')?.value || null,
				api_token: form.querySelector('#add-token-input')?.value || null
			};
			fetch(`${url_base}/api/torrentclients?api_key=${api_key}`, {
				'method': 'POST',
				'headers': {'Content-Type': 'application/json'},
				'body': JSON.stringify(data)
			})
			.then(response => {
				loadTorrentClients(api_key);
				closeWindow();
			});
		});
	});
};

async function testAddTorrent(api_key) {
	const form = document.querySelector('#add-torrent-form tbody');
	const test_button = document.querySelector('#test-torrent-add');
	test_button.classList.remove('show-success', 'show-fail');
	const data = {
		type: form.dataset.type,
		base_url: form.querySelector('#add-baseurl-input').value,
		username: form.querySelector('#add-username-input')?.value || null,
		password: form.querySelector('#add-password-input')?.value || null,
		api_token: form.querySelector('#add-token-input')?.value || null,
	};
	return await fetch(`${url_base}/api/torrentclients/test?api_key=${api_key}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(data)
	})
	.then(response => response.json())
	.then(json => {
		if (json.result.result)
			// Test successful
			test_button.classList.add('show-success');
		else
			// Test failed
			test_button.classList.add('show-fail');
		return json.result.result;
	});
};

function loadTorrentClients(api_key) {
	fetch(`${url_base}/api/torrentclients?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#torrent-client-list');
		document.querySelectorAll('#torrent-client-list > :not(:first-child)')
			.forEach(el => el.remove());

		json.result.forEach(client => {
			const entry = document.createElement('button');
			entry.onclick = (e) => loadEditTorrent(api_key, client.id);
			entry.type = 'button';
			entry.innerText = client.title;
			table.appendChild(entry);
		});
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	loadTorrentClients(api_key);
	document.querySelector('#delete-torrent-edit').onclick = e => deleteTorrent(api_key);
	document.querySelector('#test-torrent-edit').onclick = e => testEditTorrent(api_key);
	document.querySelector('#test-torrent-add').onclick = e => testAddTorrent(api_key);
	document.querySelector('#torrent-client-list > .add-client-button').onclick = e => loadTorrentList(api_key);
});

document.querySelector('#edit-torrent-form').action = 'javascript:saveEditTorrent()';
document.querySelector('#add-torrent-form').action = 'javascript:saveAddTorrent()';
