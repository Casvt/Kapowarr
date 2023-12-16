const inputs = {
	'renaming_input': document.querySelector('#renaming-input'),
	'volume_folder_naming_input': document.querySelector('#volume-folder-naming-input'),
	'file_naming_input': document.querySelector('#file-naming-input'),
	'file_naming_tpb_input': document.querySelector('#file-naming-tpb-input'),
	'file_naming_empty_input': document.querySelector('#file-naming-empty-input'),
	'volume_as_empty_input': document.querySelector('#volume-as-empty-input'),
	'convert_input': document.querySelector('#convert-input'),
	'extract_input': document.querySelector('#extract-input'),
	'issue_padding_input': document.querySelector('#issue-padding-input'),
	'volume_padding_input': document.querySelector('#volume-padding-input')
};

//
// Settings
// 
function fillSettings(api_key) {
	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		inputs.renaming_input.checked = json.result.rename_downloaded_files;
		inputs.volume_folder_naming_input.value = json.result.volume_folder_naming;
		inputs.file_naming_input.value = json.result.file_naming;
		inputs.file_naming_tpb_input.value = json.result.file_naming_tpb;
		inputs.file_naming_empty_input.value = json.result.file_naming_empty;
		inputs.volume_as_empty_input.checked = json.result.volume_as_empty;
		inputs.convert_input.checked = json.result.convert;
		inputs.extract_input.checked = json.result.extract_issue_ranges;
		inputs.issue_padding_input.value = json.result.issue_padding;
		inputs.volume_padding_input.value = json.result.volume_padding;
		
		fillConvert(api_key, json.result.format_preference);
	});
};

function saveSettings(api_key) {
	inputs.file_naming_input.classList.remove('error-input');
	inputs.file_naming_tpb_input.classList.remove('error-input');
	inputs.file_naming_empty_input.classList.remove('error-input');
	const data = {
		'rename_downloaded_files': document.querySelector('#renaming-input').checked,
		'volume_folder_naming': document.querySelector('#volume-folder-naming-input').value,
		'file_naming': inputs.file_naming_input.value,
		'file_naming_tpb': inputs.file_naming_tpb_input.value,
		'file_naming_empty': inputs.file_naming_empty_input.value,
		'volume_as_empty': inputs.volume_as_empty_input.checked,
		'convert': inputs.convert_input.checked,
		'extract_issue_ranges': inputs.extract_input.checked,
		'format_preference': convert_preference,
		'issue_padding': parseInt(inputs.issue_padding_input.value),
		'volume_padding': parseInt(inputs.volume_padding_input.value)
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
				inputs.file_naming_input.classList.add('error-input');
			else if (e.result.key === 'file_naming_tpb')
				inputs.file_naming_tpb_input.classList.add('error-input');
			else if (e.result.key === 'file_naming_empty')
				inputs.file_naming_empty_input.classList.add('error-input');
		} else
			console.log(e.error);
	});
};

//
// Convert
//
let convert_options = [];
let convert_preference = [];
function fillConvert(api_key, convert_pref) {
	fetch(`${url_base}/api/settings/availableformats?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		convert_options = json.result;

		convert_preference = convert_pref;
		updateConvertList();
	});
};

function getConvertList() {
	return [
		...document.querySelectorAll(
			'#convert-table tr[data-place] select'
		)
	].map(el => el.value);
};

function updateConvertList() {
	const table = document.querySelector('#convert-table tbody');
	table.querySelectorAll('tr:not(:nth-last-child(-n+2))').forEach(
		e => e.remove()
		);
	const no_conversion = table.querySelector('tr:nth-last-child(2)');

	let last_index = -1
	convert_preference.forEach((format, index) => {
		last_index = index;
		const entry = document.createElement('tr');
		entry.dataset.place = index + 1;

		const place = document.createElement('th');
		place.innerText = index + 1;
		entry.appendChild(place);

		const select_container = document.createElement('td');
		const select = document.createElement('select');
		convert_preference.forEach(o => {
			const option = document.createElement('option');
			option.value = option.innerText = o;
			option.selected = format === o;
			select.appendChild(option);
		});
		select.onchange = (e) => {
			const other_el = [
				...table.querySelectorAll(
					`tr:not([data-place="${index + 1}"]) select`
				)
			].filter(
				el => el.value === select.value
			)[0];
			const used_values = new Set([
				...table.querySelectorAll('select')
			].map(el => el.value));
			const missing_value = convert_preference
				.filter(f => !used_values.has(f))[0];
			other_el.value = missing_value;
			
			convert_preference = getConvertList();
		};
		select_container.appendChild(select);
		entry.appendChild(select_container);
		
		const delete_container = document.createElement('td');
		const delete_button = document.createElement('button');
		delete_button.title = 'Delete format from list';
		delete_button.type = 'button';
		delete_button.onclick = (e) => {
			entry.remove();
			convert_preference = getConvertList();
			updateConvertList();
		};
		const delete_button_icon = document.createElement('img');
		delete_button_icon.src = `${url_base}/static/img/delete.svg`;
		delete_button_icon.alt = '';

		delete_button.appendChild(delete_button_icon);
		delete_container.appendChild(delete_button);
		entry.appendChild(delete_container);

		no_conversion.insertAdjacentElement("beforebegin", entry);
	});

	no_conversion.querySelector('th').innerText = last_index + 2;

	const add_select = table.querySelector('#add-convert-input');
	add_select.innerHTML = '';
	const not_added_formats = convert_options
		.filter(el => !convert_preference.includes(el));
	if (not_added_formats.length > 0) {
		not_added_formats.forEach(format => {
			const option = document.createElement('option');
			option.value = option.innerText = format;
			add_select.appendChild(option);
		});
		table.querySelector('tr:last-child').classList.remove('hidden');
	} else {
		table.querySelector('tr:last-child').classList.add('hidden');
	};
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

	fetch(`${url_base}/api/rootfolder?api_key=${api_key}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify({'folder': folder})
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
});

addEventListener('#toggle-root-folder', 'click', toggleAddRootFolder);
addEventListener('#add-convert-button', 'click', e => {
	convert_preference.push(
		document.querySelector('#add-convert-input').value
	);
	updateConvertList();
});