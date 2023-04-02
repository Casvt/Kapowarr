function fillSettings() {
	fetch(`/api/settings?api_key=${api_key}`)
	.then(response => {
		return response.json();
	})
	.then(json => {
		document.getElementById('volume-folder-naming-input').value = json.result.volume_folder_naming;
		document.getElementById('file-naming-input').value = json.result.file_naming;
		document.getElementById('file-naming-tpb-input').value = json.result.file_naming_tpb;
	});
	fillRootFolder();
};

function fillRootFolder() {
	fetch(`/api/rootfolder?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.getElementById('root-folder-list');
		table.innerHTML = '';
		json.result.forEach(root_folder => {
			const entry = document.createElement('tr');
			entry.classList.add('root-folder-entry');
			entry.dataset.id = root_folder.id

			const path = document.createElement('td');
			path.innerText = root_folder.folder;
			entry.appendChild(path);

			const delete_root_folder_container = document.createElement('td');
			delete_root_folder_container.classList.add('action-column');
			const delete_root_folder = document.createElement('button');
			delete_root_folder.addEventListener('click', e => deleteRootFolder(root_folder.id));
			delete_root_folder.setAttribute('type', 'button');
			const delete_root_folder_icon = document.createElement('img');
			delete_root_folder_icon.src = '/static/img/delete.svg';
			delete_root_folder.appendChild(delete_root_folder_icon);
			delete_root_folder_container.appendChild(delete_root_folder);
			entry.appendChild(delete_root_folder_container);

			table.appendChild(entry);
		});
	});
}

function deleteRootFolder(id) {
	fetch(`/api/rootfolder/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		// catch errors
		if (!response.ok) {
			return Promise.reject(response.status);
		};
		
		document.querySelector(`tr[data-id="${id}"]`).remove();
	})
	.catch(e => {
		if (e === 400) {
			const message = document.createElement('p');
			message.classList.add('error');
			message.innerText = 'Root folder is still in use by a volume';
			document.querySelector(`tr[data-id="${id}"] > :nth-child(1)`).appendChild(message);
		};
	});
};

function saveSettings() {
	const data = {
		'volume_folder_naming': document.getElementById('volume-folder-naming-input').value,
		'file_naming': document.getElementById('file-naming-input').value,
		'file_naming_tpb': document.getElementById('file-naming-tpb-input').value
	};
	fetch(`/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		return response.json();
	})
	.then(json => {
		// catch errors
		if (!json.error === null) {
			return Promise.reject(json);
		};
	})
	.catch(e => {
		console.log(e.error);
	});
};

function toggleAddRootFolder() {
	document.getElementById('folder-error').classList.add('hidden');
	document.getElementById('folder-input').value = '';
	document.getElementById('add-row').classList.toggle('hidden');
};

function addRootFolder() {
	const folder_input = document.getElementById('folder-input');
	const folder = folder_input.value;
	folder_input.value = '';
	fetch(`/api/rootfolder?api_key=${api_key}&folder=${folder}`, {
		'method': 'POST'
	})
	.then(response => {
		// catch errors
		if (!response.ok) {
			return Promise.reject(response.status);
		};
		
		fillRootFolder();
		toggleAddRootFolder();
	})
	.catch(e => {
		if (e === 404) {
			document.getElementById('folder-error').classList.remove('hidden');
		};
	});
};

// code run on load

const api_key = sessionStorage.getItem('api_key');

fillSettings();

document.getElementById('save-button').addEventListener('click', e => saveSettings());
document.getElementById('toggle-root-folder').addEventListener('click', e => toggleAddRootFolder());
document.getElementById('add-folder').addEventListener('click', e => addRootFolder());
document.getElementById('folder-input').addEventListener('keydown', e => {
	if (e.key === 'Enter') {
		addRootFolder();
	};
});
