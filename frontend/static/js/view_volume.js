const ViewEls = {
	views: {
		loading: document.querySelector('#loading-screen'),
		main: document.querySelector('main')
	},
	pre_build: {
		issue_entry: document.querySelector('.pre-build-els .issue-entry')
	},
	vol_data: {
		monitor: document.querySelector('#volume-monitor'),
		title: document.querySelector('.volume-title-monitored > h2'),
		cover: document.querySelector('.volume-info > img'),
		tags: document.querySelector('#volume-tags'),
		path: document.querySelector('#volume-path'),
		description: document.querySelector('#volume-description'),
		mobile_description: document.querySelector('#volume-description-mobile')
	},
	issues_list: document.querySelector('#issues-list')
};

// 
// Filling data
// 
function fillTable(issues, api_key) {
	ViewEls.issues_list.innerHTML = '';

	for (i = issues.length - 1; i >= 0; i--) {
		const obj = issues[i];
		
		const entry = ViewEls.pre_build.issue_entry.cloneNode(deep=true);
		entry.dataset.id = obj.id;

		// Monitored
		const monitored = entry.querySelector('.issue-monitored button');
		monitored.dataset.monitored = obj.monitored;
		monitored.dataset.id = obj.id;
		monitored.onclick = e => toggleMonitoredIssue(obj.id, api_key);
		if (obj.monitored) {
			// Issue is monitored
			monitored.innerHTML = icons.monitored;
			monitored.title = 'Issue is monitored. Click to unmonitor.';
		} else {
			// Issue is unmonitored
			monitored.innerHTML = icons.unmonitored;
			monitored.title = 'Issue is unmonitored. Click to monitor.';
		};

		// Issue number
		entry.querySelector('.issue-number').innerText = obj.issue_number;

		// Title
		const title = entry.querySelector('.issue-title')
		title.innerText = obj.title;
		title.onclick = e => showIssueInfo(obj.id, api_key);

		// Release date
		entry.querySelector('.issue-date').innerText = obj.date;

		// Download status
		const status = entry.querySelector('.issue-status');
		const status_icon = status.querySelector('img');
		if (obj.files.length) {
			// Downloaded
			status_icon.src = `${url_base}/static/img/check.svg`;
			status.title = 'Issue is downloaded';
		} else {
			// Not downloaded
			status_icon.src = `${url_base}/static/img/cancel.svg`;
			status.title = 'Issue is not downloaded';
		};

		entry.querySelector('.action-column :nth-child(1)').onclick =
			e => autosearchIssue(obj.id, api_key);
		entry.querySelector('.action-column :nth-child(2)').onclick =
			e => showManualSearch(api_key, obj.id);
		entry.querySelector('.action-column :nth-child(3)').onclick =
			e => showConvert(api_key, obj.id);

		ViewEls.issues_list.appendChild(entry);
	};
};

function fillPage(data, api_key) {
	// Cover
	ViewEls.vol_data.cover.src = `${url_base}/api/volumes/${data.id}/cover?api_key=${api_key}`;

	// Monitored state
	const monitor = ViewEls.vol_data.monitor;
	monitor.dataset.monitored = data.monitored;
	monitor.onclick = e => toggleMonitored(api_key);
	if (data.monitored) {
		// Volume is monitored
		monitor.innerHTML = icons.monitored;
		monitor.title = 'Volume is monitored. Click to unmonitor.';
	} else {
		// Volume is unmonitored
		monitor.innerHTML = icons.unmonitored;
		monitor.title = 'Volume is unmonitored. Click to monitor.';
	};

	// Title
	ViewEls.vol_data.title.innerText = data.title;

	// Tags
	const tags = ViewEls.vol_data.tags;
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
	const path = ViewEls.vol_data.path;
	path.innerText = data.folder;
	path.dataset.root_folder = data.root_folder;
	path.dataset.volume_folder = data.volume_folder;

	// Descriptions
	ViewEls.vol_data.description.innerHTML = data.description;
	ViewEls.vol_data.mobile_description.innerHTML = data.description;

	// fill issue lists
	fillTable(data.issues, api_key);

	mapButtons(id);

	ViewEls.views.loading.classList.add('hidden');
	ViewEls.views.main.classList.remove('hidden');
};

// 
// Actions
// 
function toggleMonitored(api_key) {
	const button = document.querySelector('#volume-monitor');
	data = {
		'monitored': button.dataset.monitored !== 'true'
	};
	fetch(`${url_base}/api/volumes/${id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		button.dataset.monitored = data.monitored;
		button.innerHTML = data.monitored ? icons.monitored : icons.unmonitored;
	});
};

function toggleMonitoredIssue(issue_id, api_key) {
	const issue = document.querySelector(`button[data-id="${issue_id}"]`);
	data = {
		'monitored': issue.dataset.monitored !== 'true'
	};
	fetch(`${url_base}/api/issues/${issue_id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		issue.dataset.monitored = data.monitored;
		issue.innerHTML = data.monitored ? icons.monitored : icons.unmonitored;
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
				match_icon.src = `${url_base}/static/img/cancel.svg`;
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
		match.src = `${url_base}/static/img/cancel.svg`;
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
		const table = document.querySelector('.rename-preview > tbody');
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
	if ([...document.querySelectorAll('.rename-preview > tbody input[type="checkbox"]')].every(e => !e.checked)) {
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
			...json.result.format_preference,
			'no conversion'
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
		'monitored': document.querySelector('#monitored-input').value == 'true',
		'root_folder': parseInt(document.querySelector('#root-folder-input').value),
		'volume_folder': document.querySelector('#volumefolder-input').value
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
	.catch(e => {
		if (e === 404)
			window.location.href = `${url_base}/`
		else
			console.log(e);
	});

	addEventListener('#refresh-button', 'click', e => refreshVolume(api_key));
	addEventListener('#autosearch-button', 'click', e => autosearchVolume(api_key));
	addEventListener('#manualsearch-button', 'click', e => showManualSearch(api_key));

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
