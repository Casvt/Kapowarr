function fillSettings(api_key) {
	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#download-folder-input').value = json.result.download_folder;
		document.querySelector('#seeding-handling-input').value = json.result.seeding_handling;
		document.querySelector('#delete-torrents-input').checked = json.result.delete_completed_torrents;
		fillPref(json.result.service_preference);
	});
};

function saveSettings(api_key) {
	document.querySelector('#download-folder-input').classList.remove('error-input');
	const data = {
		'download_folder': document.querySelector('#download-folder-input').value,
		'seeding_handling': document.querySelector('#seeding-handling-input').value,
		'delete_completed_torrents': document.querySelector('#delete-torrents-input').checked,
		'service_preference': [...document.querySelectorAll('#pref-table select')].map(e => e.value)
	};
	fetch(`${url_base}/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
	})
	.catch(e => {
		if (e === 404) {
			document.querySelector('#download-folder-input').classList.add('error-input');
		} else {
			console.log(e);
		};
	});
};

// 
// Empty download folder
// 
function emptyFolder(api_key) {
	fetch(`${url_base}/api/activity/folder?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		document.querySelector('#empty-download-folder').innerText = 'Done';
	});
};

//
// Service preference
//
function fillPref(pref) {
	const selects = document.querySelectorAll('#pref-table select');
	for (let i = 0; i < pref.length; i++) {
		const service = pref[i];
		const select = selects[i];
		select.addEventListener('change', updatePrefOrder);
		pref.forEach(option => {
			const entry = document.createElement('option');
			entry.value = option;
			entry.innerText = option.charAt(0).toUpperCase() + option.slice(1);
			if (option === service)
				entry.selected = true;
			select.appendChild(entry);
		});
	};
};

function updatePrefOrder(e) {
	const other_selects = document.querySelectorAll(
		`#pref-table select:not([data-place="${e.target.dataset.place}"])`
	);
	// Find select that has the value of the target select
	for (let i = 0; i < other_selects.length; i++) {
		if (other_selects[i].value === e.target.value) {
			// Set it to old value of target select
			all_values = [...document.querySelector('#pref-table select').options].map(e => e.value)
			used_values = new Set([...document.querySelectorAll('#pref-table select')].map(s => s.value));
			open_value = all_values.filter(e => !used_values.has(e))[0];
			other_selects[i].value = open_value;
			break;
		};
	};
};

// 
// Credentials
// 
function fillCredentials(api_key) {
	fetch(`${url_base}/api/credentials?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#cred-list');
		table.innerHTML = '';
		json.result.forEach(cred => {
			const entry = document.createElement('tr');
			entry.dataset.id = cred.id

			const service = document.createElement('td');
			service.innerText = cred.source.charAt(0).toUpperCase() + cred.source.slice(1);
			entry.appendChild(service);
			
			const email = document.createElement('td');
			email.innerText = cred.email;
			entry.appendChild(email);
			
			const password = document.createElement('td');
			password.innerText = cred.password;
			entry.appendChild(password);

			const delete_cred_container = document.createElement('td');
			delete_cred_container.classList.add('action-column');
			const delete_cred = document.createElement('button');
			delete_cred.addEventListener('click', e => deleteCredential(cred.id, api_key));
			delete_cred.setAttribute('type', 'button');
			const delete_cred_icon = document.createElement('img');
			delete_cred_icon.src = `${url_base}/static/img/delete.svg`;
			delete_cred.appendChild(delete_cred_icon);
			delete_cred_container.appendChild(delete_cred);
			entry.appendChild(delete_cred_container);

			table.appendChild(entry);
		});
	});
};

function fillServices(api_key) {
	const table = document.querySelector('#cred-service-input');
	const button = document.querySelector('#toggle-cred');
	fetch(`${url_base}/api/credentials/open?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		if (!json.result.length) {
			// No services open so hide add button
			button.classList.add('hidden');
		} else {
			// Services available to be added
			button.classList.remove('hidden');
			table.innerHTML = '';
			json.result.forEach(service => {
				const entry = document.createElement('option');
				entry.value = service;
				entry.innerText = service.charAt(0).toUpperCase() + service.slice(1);
				table.appendChild(entry);
			});
		};
	});
};

function toggleAddCredential(e) {
	const row = document.querySelector('#add-row');
	if (row.classList.contains('hidden')) {
		// show row
		row.classList.remove('hidden');
	} else {
		// hide row
		row.classList.add('hidden');
		document.querySelector('#cred-error').classList.add('hidden');
		document.querySelector('#cred-email-input').value = '';
		document.querySelector('#cred-password-input').value = '';
	};
};

function addCredential(api_key) {
	const service = document.querySelector('#cred-service-input').value;
	const email = document.querySelector('#cred-email-input').value;
	const password = document.querySelector('#cred-password-input').value;

	fetch(`${url_base}/api/credentials?api_key=${api_key}&source=${service}&email=${email}&password=${password}`, {
		'method': 'POST'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);

		fillServices(api_key);
		fillCredentials(api_key);
		toggleAddCredential(1);
	})
	.catch(e => {
		if (e === 400) document.querySelector('#cred-error').classList.remove('hidden');
	});
};

function deleteCredential(id, api_key) {
	fetch(`${url_base}/api/credentials/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		
		document.querySelector(`tr[data-id="${id}"]`).remove();
		fillServices(api_key);
	})
	.catch(e => console.log(e));
};

// code run on load
usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	fillServices(api_key);
	fillCredentials(api_key);
	
	addEventListener('#save-button', 'click', e => saveSettings(api_key));
	addEventListener('#empty-download-folder', 'click', e => emptyFolder(api_key));
	addEventListener('#add-cred', 'click', e => addCredential(api_key));
	addEventListener('#toggle-cred', 'click', toggleAddCredential);
});
