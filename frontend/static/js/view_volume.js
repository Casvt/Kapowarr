// 
// Filling data
// 
function fillTable(issues, api_key) {
	const table = document.querySelector('#issues-list');
	table.innerHTML = '';

	for (i = issues.length - 1; i >= 0; i--) {
		const obj = issues[i];
		
		const entry = document.createElement('tr');
		entry.setAttribute('data-id', obj.id);
		entry.classList.add('issue-entry');

		// Monitored
		const monitored_container = document.createElement('td');
		monitored_container.classList.add('issue-monitored','monitor-column');
		const monitored = document.createElement('button');
		monitored.dataset.monitored = obj.monitored;
		monitored.dataset.id = obj.id;
		monitored.addEventListener('click', e => toggleMonitoredIssue(obj.id, api_key));
		const monitored_icon = document.createElement('img');
		if (obj.monitored) {
			// Issue is monitored
			monitored_icon.src = `${url_base}/static/img/monitored.svg`;
			monitored.setAttribute('aria-label', 'Issue is monitored. Click to unmonitor.');
			monitored.setAttribute('title', 'Issue is monitored. Click to unmonitor.');
		} else {
			// Issue is unmonitored
			monitored_icon.src = `${url_base}/static/img/unmonitored.svg`;
			monitored.setAttribute('aria-label', 'Issue is unmonitored. Click to monitor.');
			monitored.setAttribute('title', 'Issue is unmonitored. Click to monitor.');
		};
		monitored.appendChild(monitored_icon);
		monitored_container.appendChild(monitored);
		entry.appendChild(monitored_container);

		// Issue number
		const issue_number = document.createElement('td');
		issue_number.classList.add('issue-number','number-column');
		issue_number.innerText = obj.issue_number;
		entry.appendChild(issue_number);

		// Title
		const title = document.createElement('td');
		title.classList.add('issue-title','title-column');
		title.innerText = obj.title;
		title.addEventListener('click', e => showIssueInfo(obj.id, api_key));
		entry.append(title);

		// Release date
		const release_date = document.createElement('td');
		release_date.classList.add('issue-date','date-column');
		release_date.innerText = obj.date;
		entry.append(release_date);

		// Download status
		const status = document.createElement('td');
		status.classList.add('issue-status','download-column');
		const status_icon = document.createElement('img');
		if (obj.files.length) {
			// Downloaded
			status_icon.src = `${url_base}/static/img/check.svg`;
			status.setAttribute('aria-label', 'Issue is downloaded.');
			status.setAttribute('title', 'Issue is downloaded');
		} else {
			// Not downloaded
			status_icon.src = `${url_base}/static/img/cancel_search.svg`;
			status.setAttribute('aria-label', 'Issue is not downloaded.');
			status.setAttribute('title', 'Issue is not downloaded');
		};
		status.appendChild(status_icon);
		entry.appendChild(status);

		// Actions
		const actions = document.createElement('td');
		actions.classList.add('action-column');
		
		// Auto search
		const auto_search = document.createElement('button');
		auto_search.setAttribute('title', 'Auto search for this issue');
		auto_search.setAttribute('aria-label', 'Auto search for this issue');
		auto_search.addEventListener('click', e => autosearchIssue(obj.id, api_key));
		const auto_search_icon = document.createElement('img');
		auto_search_icon.src = `${url_base}/static/img/search.svg`;
		auto_search.appendChild(auto_search_icon);
		actions.appendChild(auto_search);

		// Manual search
		const manual_search = document.createElement('button');
		manual_search.setAttribute('title', 'Manually search for this issue');
		manual_search.setAttribute('aria-label', 'Manually search for this issue');
		manual_search.addEventListener('click', e => showManualSearch(api_key, obj.id));		
		const manual_search_icon = document.createElement('img');
		manual_search_icon.src = `${url_base}/static/img/manual_search.svg`;
		manual_search.appendChild(manual_search_icon);
		actions.appendChild(manual_search);

		// Convert
		const convert = document.createElement('button');
		convert.title = 'Convert files for this issue';
		convert.ariaLabel = 'Convert files for this issue';
		convert.onclick = (e) => showConvert(api_key, obj.id);
		const convert_icon = document.createElement('img');
		convert_icon.src = `${url_base}/static/img/unzip.svg`;
		convert.appendChild(convert_icon);
		actions.appendChild(convert);

		entry.appendChild(actions);
		table.appendChild(entry);
	};
};

function fillPage(data, api_key) {
	// Set volume data
	const monitor = document.querySelector('#volume-monitor');
	const monitor_icon = monitor.querySelector('img');
	const title = document.querySelector('.volume-title-monitored > h2');
	const cover = document.querySelector('.volume-info > img');
	const tags = document.querySelector('#volume-tags');
	const path = document.querySelector('#volume-path');
	const description = document.querySelector('#volume-description');
	const mobile_description = document.querySelector('#volume-description-mobile');

	// Cover
	cover.src = `${data.cover}?api_key=${api_key}`;
	
	// Monitored state
	monitor.dataset.monitored = data.monitored;
	monitor.addEventListener('click', e => toggleMonitored(api_key));
	if (data.monitored) {
		// Volume is monitored
		monitor_icon.src = `${url_base}/static/img/monitored_light.svg`;
		monitor.setAttribute('aria-label', 'Volume is monitored. Click to unmonitor.');
		monitor.setAttribute('title', 'Volume is monitored. Click to unmonitor.');
	} else {
		// Volume is unmonitored
		monitor_icon.src = `${url_base}/static/img/unmonitored_light.svg`;
		monitor.setAttribute('aria-label', 'Volume is unmonitored. Click to monitor.');
		monitor.setAttribute('title', 'Volume is unmonitored. Click to monitor.');
	};
	
	// Title
	title.innerText = data.title;
	
	// Tags
	const year = document.createElement('p');
	year.innerText = data.year;
	tags.appendChild(year);
	const volume_number = document.createElement('p');
	volume_number.innerText = `Volume ${data.volume_number || 1}`;
	tags.appendChild(volume_number);
	const special_version = document.createElement('p');
	special_version.innerText = data.special_version?.toUpperCase() || 'Normal volume';
	tags.appendChild(special_version);
	
	// Path
	path.innerText = data.folder;
	path.dataset.root_folder = data.root_folder;
	path.dataset.volume_folder = data.volume_folder;
	
	// Descriptions
	description.innerHTML = data.description;
	mobile_description.innerHTML = data.description;

	// fill issue lists
	fillTable(data.issues, api_key);
	
	mapButtons(id);
};

// 
// Actions
// 
function toggleMonitored(api_key) {
	const button = document.querySelector('#volume-monitor');
	const icon = button.querySelector('img');
	data = {
		'monitor': button.dataset.monitored !== 'true'
	};
	fetch(`${url_base}/api/volumes/${id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		button.dataset.monitored = data.monitor;
		icon.src = data.monitor ? `${url_base}/static/img/monitored_light.svg` : `${url_base}/static/img/unmonitored_light.svg`;
	});
};

function toggleMonitoredIssue(issue_id, api_key) {
	const issue = document.querySelector(`button[data-id="${issue_id}"]`);
	const icon = issue.querySelector('img');
	data = {
		'monitor': issue.dataset.monitored !== 'true'
	};
	fetch(`${url_base}/api/issues/${issue_id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		issue.dataset.monitored = data.monitor;
		icon.src = data.monitor ? `${url_base}/static/img/monitored.svg` : `${url_base}/static/img/unmonitored.svg`;
	});
};

// 
// Tasks
// 
function refreshVolume(api_key) {
	const button_info = task_to_button[`refresh_and_scan#${id}`];
	const icon = button_info.button.querySelector('img');
	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');

	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=refresh_and_scan&volume_id=${id}`, {
		'method': 'POST'
	});
};

function autosearchVolume(api_key) {
	const button_info = task_to_button[`auto_search#${id}`];
	const icon = button_info.button.querySelector('img');
	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');

	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=auto_search&volume_id=${id}`, {
		'method': 'POST'
	});
};

function unzipVolume(api_key) {
	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=unzip&volume_id=${id}`, {
		'method': 'POST'
	});
};

function autosearchIssue(issue_id, api_key) {
	const button_info = task_to_button[`auto_search_issue#${id}#${issue_id}`];
	const icon = button_info.button.querySelector('img');
	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');
	
	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=auto_search_issue&volume_id=${id}&issue_id=${issue_id}`, {
		'method': 'POST'
	});
};

// 
// Manual search
// 
function showManualSearch(api_key, issue_id=null) {
	// Display searching message
	const message = document.querySelector('#searching-message');
	message.classList.remove('hidden');
	const table = document.querySelector('#search-result-table');
	table.classList.add('hidden');
	const tbody = table.querySelector('tbody');

	// Show window
	showWindow('manual-search-window');

	// Start search
	tbody.innerHTML = '';
	const url = issue_id ? `${url_base}/api/issues/${issue_id}/manualsearch` : `${url_base}/api/volumes/${id}/manualsearch`;
	fetch(`${url}?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		json.result.forEach(result => {
			const entry = document.createElement('tr');
			entry.classList.add('search-entry');

			const match = document.createElement('td');
			match.classList.add('match-column');
			const match_icon = document.createElement('img');
			if (result.match) {
				match_icon.src = `${url_base}/static/img/check.svg`;
			} else {
				match_icon.src = `${url_base}/static/img/cancel_search.svg`;
				match.title = result.match_issue;
			};
			match.appendChild(match_icon);
			entry.appendChild(match);
			
			const title = document.createElement('td');
			const title_link = document.createElement('a');
			title_link.href = result.link;
			title_link.innerText = result.display_title;
			title_link.setAttribute('target', '_blank');
			title.appendChild(title_link);
			entry.appendChild(title);

			const source = document.createElement('td');
			source.classList.add('source-column');
			source.innerText = result.source;
			entry.appendChild(source);

			const action = document.createElement('td');
			action.classList.add('search-action-column', 'action-list');
			const add_entry = document.createElement('button');
			add_entry.title = 'Download';
			add_entry.addEventListener('click', e => addManualSearch(result.link, add_entry, api_key, issue_id));
			const add_entry_icon = document.createElement('img');
			add_entry_icon.src = `${url_base}/static/img/download.svg`;
			add_entry.appendChild(add_entry_icon);
			action.appendChild(add_entry);
			if (result.match_issue === null || !result.match_issue.includes('blocklist')) {
				const blocklist_entry = document.createElement('button');
				blocklist_entry.title = 'Add to blocklist';
				blocklist_entry.addEventListener('click', e => blockManualSearch(result.link, blocklist_entry, match, api_key));
				const blocklist_entry_icon = document.createElement('img');
				blocklist_entry_icon.src = `${url_base}/static/img/blocklist.svg`;
				blocklist_entry.appendChild(blocklist_entry_icon);
				action.appendChild(blocklist_entry);
			};
			entry.appendChild(action);

			tbody.appendChild(entry);
		});

		message.classList.add('hidden');
		table.classList.remove('hidden');
	});
};

function addManualSearch(link, button, api_key, issue_id=null) {
	const img = button.querySelector('img');
	img.src = `${url_base}/static/img/loading.svg`;
	img.classList.add('spinning');

	const url = issue_id ? `${url_base}/api/issues/${issue_id}/download` : `${url_base}/api/volumes/${id}/download`;
	fetch(`${url}?api_key=${api_key}&link=${link}`, {
		'method': 'POST'
	})
	.then(response => response.json())
	.then(json => {
		img.classList.remove('spinning');
		if (json.result.length) img.src = `${url_base}/static/img/check.svg`;
		else img.src = `${url_base}/static/img/download_failed.svg`;
	});
};

function blockManualSearch(link, button, match, api_key) {
	fetch(`${url_base}/api/blocklist?api_key=${api_key}&link=${link}&reason_id=4`, {
		'method': 'POST'
	})
	.then(response => {
		button.querySelector('img').src = `${url_base}/static/img/check.svg`;
		match.src = '/static/img/cancel_search.svg';
		match.title = 'Link is blocklisted';
	});
};

// 
// Renaming
// 
function showRename(api_key, issue_id=null) {
	document.querySelector('#selectall-input').checked = true;
	
	const rename_button = document.querySelector('#submit-rename');
	let url;
	if (issue_id === null) {
		// Preview volume rename
		url = `${url_base}/api/volumes/${id}/rename?api_key=${api_key}`;
		rename_button.dataset.issue_id = '';
	} else {
		// Preview issue rename
		url = `${url_base}/api/issues/${issue_id}/rename?api_key=${api_key}`;
		rename_button.dataset.issue_id = issue_id;
	};
	fetch(url)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#rename-preview > tbody');
		table.innerHTML = '';
		

		if (!json.result.length) {
			const message = document.createElement('p');
			message.classList.add('empty-rename-message');
			message.innerText = 'Nothing to rename';
			table.appendChild(message);
			rename_button.classList.add('hidden');
			table.parentNode.querySelector('thead').classList.add('hidden');
		} else {
			rename_button.classList.remove('hidden');
			table.parentNode.querySelector('thead').classList.remove('hidden');
			json.result.forEach(rename_entry => {
				const before = document.createElement('tr');
				
				const checkbox = document.createElement('td');
				checkbox.setAttribute('rowspan', '2');
				const checkbox_input = document.createElement('input');
				checkbox_input.type = 'checkbox';
				checkbox_input.checked = true;
				checkbox.appendChild(checkbox_input);
				before.appendChild(checkbox);
				
				const before_icon = document.createElement('td');
				before_icon.innerText = '-';
				before.appendChild(before_icon);
				
				const before_path = document.createElement('td');
				before_path.innerText = rename_entry.before;
				before.appendChild(before_path);
				
				table.appendChild(before);
				
				const after = document.createElement('tr');
				
				const after_icon = document.createElement('td');
				after_icon.innerText = '+';
				after.appendChild(after_icon);
				
				const after_path = document.createElement('td');
				after_path.innerText = rename_entry.after;
				after.appendChild(after_path);
				
				table.appendChild(after);
			});
		};
		showWindow('rename-window');
	});
};

function toggleAllRenames() {
	const checked = document.querySelector('#selectall-input').checked;
	document.querySelectorAll('#rename-window > tbody input[type="checkbox"]').forEach(e => e.checked = checked);
};

function renameVolume(api_key, issue_id=null) {
	if ([...document.querySelectorAll('#rename-preview > tbody input[type="checkbox"]')].every(e => !e.checked)) {
		closeWindow();
		return;
	};

	showLoadWindow('rename-window');
	let url;
	if (issue_id === null) url = `${url_base}/api/volumes/${id}/rename?api_key=${api_key}`;
	else url = `${url_base}/api/issues/${issue_id}/rename?api_key=${api_key}`;

	let args;
	if ([...document.querySelectorAll('#rename-preview > tbody input[type="checkbox"]')].every(e => e.checked))
		args = { 'method': 'POST' };
	else
		args = {
			'method': 'POST',
			'headers': {'Content-Type': 'application/json'},
			'body': JSON.stringify(
				[...document.querySelectorAll('#rename-preview > tbody > tr > td > input[type="checkbox"]:checked')]
					.map(e => e.parentNode.nextSibling.nextSibling.innerText)
			)
		}

	fetch(url, args)
	.then(response => window.location.reload());
};

// 
// Converting
// 
function loadConvertPreference(api_key) {
	const el = document.querySelector('#convert-preference');
	if (el.innerHTML !== '')
		return;

	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		el.innerHTML = [
			'source',
			...json.result.format_preference
		].join(' - ');
	});
};

function showConvert(api_key, issue_id=null) {
	document.querySelector('#selectall-convert-input').checked = true;
	loadConvertPreference(api_key);

	const convert_button = document.querySelector('#submit-convert');
	let url;
	if (issue_id === null) {
		// Preview issue conversion
		url = `${url_base}/api/volumes/${id}/convert?api_key=${api_key}`;
		convert_button.dataset.issue_id = '';
	} else {
		// Preview issue conversion
		url = `${url_base}/api/issues/${issue_id}/convert?api_key=${api_key}`;
		convert_button.dataset.issue_id = issue_id;
	};
	fetch(url)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#convert-window tbody');
		table.innerHTML = '';

		if (!json.result.length) {
			const message = document.createElement('p');
			message.classList.add('empty-rename-message');
			message.innerText = 'Nothing to convert';
			table.appendChild(message);
			convert_button.classList.add('hidden');
			table.parentNode.querySelector('thead').classList.add('hidden');

		} else {
			convert_button.classList.remove('hidden');
			table.parentNode.querySelector('thead').classList.remove('hidden');
			json.result.forEach(convert_entry => {
				const before = document.createElement('tr');
				
				const checkbox = document.createElement('td');
				checkbox.setAttribute('rowspan', '2');
				const checkbox_input = document.createElement('input');
				checkbox_input.type = 'checkbox';
				checkbox_input.checked = true;
				checkbox.appendChild(checkbox_input);
				before.appendChild(checkbox);
				
				const before_icon = document.createElement('td');
				before_icon.innerText = '-';
				before.appendChild(before_icon);
				
				const before_path = document.createElement('td');
				before_path.innerText = convert_entry.before;
				before.appendChild(before_path);
				
				table.appendChild(before);
				
				const after = document.createElement('tr');
				
				const after_icon = document.createElement('td');
				after_icon.innerText = '+';
				after.appendChild(after_icon);
				
				const after_path = document.createElement('td');
				after_path.innerText = convert_entry.after;
				after.appendChild(after_path);
				
				table.appendChild(after);
			});
		};
		showWindow('convert-window');
	});
};

function toggleAllConverts() {
	const checked = document.querySelector('#selectall-convert-input').checked;
	document.querySelectorAll('#convert-window tbody input[type="checkbox"]').forEach(e => e.checked = checked);
};

function convertVolume(api_key, issue_id=null) {
	if ([...document.querySelectorAll('#convert-window tbody input[type="checkbox"]')].every(e => !e.checked)) {
		closeWindow();
		return;
	};

	showLoadWindow('convert-window');
	let url;
	if (issue_id === null) url = `${url_base}/api/volumes/${id}/convert?api_key=${api_key}`;
	else url = `${url_base}/api/issues/${issue_id}/convert?api_key=${api_key}`;

	let args;
	if ([...document.querySelectorAll('#convert-window tbody input[type="checkbox"]')].every(e => e.checked))
		args = { 'method': 'POST' };
	else
		args = {
			'method': 'POST',
			'headers': {'Content-Type': 'application/json'},
			'body': JSON.stringify(
				[...document.querySelectorAll('#convert-window tbody > tr > td > input[type="checkbox"]:checked')]
					.map(e => e.parentNode.nextSibling.nextSibling.innerText)
			)
		}

	fetch(url, args)
	.then(response => window.location.reload());
};

// 
// Editing
// 
function showEdit(api_key) {
	document.querySelector('#monitored-input').value = document.querySelector('#volume-monitor').dataset.monitored;
	const volume_root_folder = parseInt(document.querySelector('#volume-path').dataset.root_folder),
		volume_folder = document.querySelector('#volume-path').dataset.volume_folder;
	fetch(`${url_base}/api/rootfolder?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#root-folder-input');
		table.innerHTML = '';
		json.result.forEach(root_folder => {
			const entry = document.createElement('option');
			entry.value = root_folder.id;
			entry.innerText = root_folder.folder;
			if (root_folder.id === volume_root_folder) {
				entry.setAttribute('selected', 'true');
			};
			table.appendChild(entry);
		});
		showWindow('edit-window');
	});
	document.querySelector('#volumefolder-input').value = volume_folder;
};

function editVolume() {
	showLoadWindow('edit-window');

	const data = {
		'monitor': document.querySelector('#monitored-input').value == 'true',
		'new_root_folder': parseInt(document.querySelector('#root-folder-input').value),
		'new_volume_folder': document.querySelector('#volumefolder-input').value
	};
	usingApiKey()
	.then(api_key => {
		fetch(`${url_base}/api/volumes/${id}?api_key=${api_key}`, {
			'method': 'PUT',
			'body': JSON.stringify(data),
			'headers': {'Content-Type': 'application/json'}
		})
		.then(response => window.location.reload());
	});
};

//
// Deleting
// 
function deleteVolume() {
	const delete_error = document.querySelector('#volume-downloading-error');
	delete_error.classList.add('hidden');
	const delete_folder = document.querySelector('#delete-folder-input').value;
	usingApiKey()
	.then(api_key => {
		fetch(`${url_base}/api/volumes/${id}?api_key=${api_key}&delete_folder=${delete_folder}`, {
			'method': 'DELETE'
		})
		.then(response => {
			if (!response.ok) return Promise.reject(response.status);
			window.location.href = `${url_base}/`;
		})
		.catch(e => {
			if (e === 400) delete_error.classList.remove('hidden');
			else console.log(e);
		});
	});
};

// 
// Issue info
// 
function showIssueInfo(id, api_key) {
	document.querySelector('#issue-rename-selector').dataset.issue_id = id;
	fetch(`${url_base}/api/issues/${id}?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#issue-info-title').innerText = `${json.result.title} - #${json.result.issue_number} - ${json.result.date}`;
		document.querySelector('#issue-info-desc').innerHTML = json.result.description;
		const files_table = document.querySelector('#issue-files');
		files_table.innerHTML = '';
		json.result.files.forEach(f => {
			const entry = document.createElement('div');
			entry.innerText = f;
			files_table.appendChild(entry);
		});
		showWindow('issue-info-window');
	});
};

function showInfoWindow(window) {
	document.querySelectorAll(
		`#issue-info-window > div:nth-child(2) > div:not(#issue-info-selectors)`
	).forEach(w => w.classList.add('hidden'));
	document.querySelector(`#${window}`).classList.remove('hidden');
};

// code run on load
const id = window.location.pathname.split('/').at(-1);

usingApiKey()
.then(api_key => {
	fetch(`${url_base}/api/volumes/${id}?api_key=${api_key}`)
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		return response.json();
	})
	.then(json => fillPage(json.result, api_key))
	.catch(e => { window.location.href = `${url_base}/` });

	addEventListener('#refresh-button', 'click', e => refreshVolume(api_key));
	addEventListener('#autosearch-button', 'click', e => autosearchVolume(api_key));
	addEventListener('#manualsearch-button', 'click', e => showManualSearch(api_key));
	addEventListener('#unzip-button', 'click', e => unzipVolume(api_key));

	addEventListener('#rename-button', 'click', e => showRename(api_key));
	addEventListener('#submit-rename', 'click', e => renameVolume(api_key, e.target.dataset.issue_id || null));

	addEventListener('#convert-button', 'click', e => showConvert(api_key));
	addEventListener('#submit-convert', 'click', e => convertVolume(api_key, e.target.dataset.issue_id || null));

	addEventListener('#edit-button', 'click', e => showEdit(api_key));
	
	addEventListener('#issue-rename-selector', 'click', e => showRename(api_key, e.target.dataset.issue_id));
});

addEventListener('#cancel-search', 'click', e => closeWindow());
addEventListener('#cancel-rename', 'click', e => closeWindow());
addEventListener('#cancel-edit', 'click', e => closeWindow());
addEventListener('#delete-button', 'click', e => showWindow('delete-window'));
addEventListener('#cancel-delete', 'click', e => closeWindow());
addEventListener('#cancel-info', 'click', e => closeWindow());
addEventListener('#issue-info-selector', 'click', e => showInfoWindow('issue-info'));
addEventListener('#issue-files-selector', 'click', e => showInfoWindow('issue-files'));
addEventListener('#cancel-convert', 'click', e => closeWindow());
addEventListener('#selectall-input', 'change', e => toggleAllRenames());
addEventListener('#selectall-convert-input', 'change', e => toggleAllConverts());

document.querySelector('#edit-form').setAttribute('action', 'javascript:editVolume();');
document.querySelector('#delete-form').setAttribute('action', 'javascript:deleteVolume();');
