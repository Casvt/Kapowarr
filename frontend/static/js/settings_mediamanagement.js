//
// Settings
// 
function fillSettings(api_key) {
	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#volume-folder-naming-input').value = json.result.volume_folder_naming;
		document.querySelector('#file-naming-input').value = json.result.file_naming;
		document.querySelector('#file-naming-tpb-input').value = json.result.file_naming_tpb;
		document.querySelector('#unzip-input').checked = json.result.unzip;
	});
};

function saveSettings(api_key) {
	document.querySelector('#file-naming-input').classList.remove('error-input');
	document.querySelector('#file-naming-tpb-input').classList.remove('error-input');
	const data = {
		'volume_folder_naming': document.querySelector('#volume-folder-naming-input').value,
		'file_naming': document.querySelector('#file-naming-input').value,
		'file_naming_tpb': document.querySelector('#file-naming-tpb-input').value,
		'unzip': document.querySelector('#unzip-input').checked
	};
	fetch(`${url_base}/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => response.json())
	.then(json => {
		if (json.error !== null) return Promise.reject(json);
	})
	.catch(e => {
		if (e.error === 'InvalidSettingValue') {
			if (e.result.key === 'file_naming')
				document.querySelector('#file-naming-input').classList.add('error-input');
			else if (e.result.key === 'file_naming_tpb')
				document.querySelector('#file-naming-tpb-input').classList.add('error-input');
		} else {
			console.log(e.error);
		};
	});
};

// 
// Root folders
// 
function fillRootFolder(api_key) {
	fetch(`${url_base}/api/rootfolder?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#root-folder-list');
		table.innerHTML = '';
		json.result.forEach(root_folder => {
			const entry = document.createElement('tr');
			entry.dataset.id = root_folder.id

			const path = document.createElement('td');
			path.innerText = root_folder.folder;
			entry.appendChild(path);

			const delete_root_folder_container = document.createElement('td');
			delete_root_folder_container.classList.add('action-column');
			const delete_root_folder = document.createElement('button');
			delete_root_folder.addEventListener('click', e => deleteRootFolder(root_folder.id, api_key));
			delete_root_folder.setAttribute('type', 'button');
			const delete_root_folder_icon = document.createElement('img');
			delete_root_folder_icon.src = `${url_base}/static/img/delete.svg`;
			delete_root_folder.appendChild(delete_root_folder_icon);
			delete_root_folder_container.appendChild(delete_root_folder);
			entry.appendChild(delete_root_folder_container);

			table.appendChild(entry);
		});
	});
}

function toggleAddRootFolder(e) {
	document.querySelector('#folder-error').classList.add('hidden');
	document.querySelector('#folder-input').value = '';
	document.querySelector('#add-row').classList.toggle('hidden');
};

function addRootFolder(api_key) {
	const folder_input = document.querySelector('#folder-input');
	const folder = folder_input.value;
	folder_input.value = '';

	fetch(`${url_base}/api/rootfolder?api_key=${api_key}&folder=${folder}`, {
		'method': 'POST'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		
		fillRootFolder(api_key);
		toggleAddRootFolder(1);
	})
	.catch(e => {
		if (e === 404) document.querySelector('#folder-error').classList.remove('hidden');
	});
};

function deleteRootFolder(id, api_key) {
	fetch(`${url_base}/api/rootfolder/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		
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

// code run on load

usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	fillRootFolder(api_key);
	addEventListener('#save-button', 'click', e => saveSettings(api_key));
	addEventListener('#add-folder', 'click', e => addRootFolder(api_key));
	addEventListener('#folder-input', 'keydown', e => e.code === 'Enter' ? addRootFolder(api_key) : null);
})

addEventListener('#toggle-root-folder', 'click', toggleAddRootFolder);
