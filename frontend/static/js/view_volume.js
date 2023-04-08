function fillTable(issues) {
	const table = document.getElementById('issues-list');
	table.innerHTML = '';
	
	const base_entry = document.createElement('tr');
	base_entry.classList.add('issue-entry');

	const monitored_container = document.createElement('td');
	monitored_container.classList.add('issue-monitored','monitor-column');
	const monitored = document.createElement('button');
	const monitored_icon = document.createElement('img');
	monitored.appendChild(monitored_icon);
	monitored_container.appendChild(monitored);
	base_entry.appendChild(monitored_container);

	const issue_number = document.createElement('td');
	issue_number.classList.add('issue-number','number-column');
	base_entry.appendChild(issue_number);

	const title = document.createElement('td');
	title.classList.add('issue-title','title-column');
	base_entry.append(title);

	const release_date = document.createElement('td');
	release_date.classList.add('issue-date','date-column');
	base_entry.append(release_date);

	const status = document.createElement('td');
	status.classList.add('issue-status','download-column');
	const status_icon = document.createElement('img');
	status.appendChild(status_icon);
	base_entry.appendChild(status);

	const auto_search_container = document.createElement('td');
	auto_search_container.classList.add('issue-search','action-column');
	const auto_search = document.createElement('button');
	auto_search.title = 'Auto search for this issue';
	const auto_search_icon = document.createElement('img');
	auto_search_icon.src = '/static/img/search.svg';
	auto_search.appendChild(auto_search_icon);
	auto_search_container.appendChild(auto_search);
	base_entry.appendChild(auto_search_container);
	
	const manual_search_container = document.createElement('td');
	manual_search_container.classList.add('issue-manual-search','action-column');
	const manual_search = document.createElement('button');
	const manual_search_icon = document.createElement('img');
	manual_search_icon.src = '/static/img/manual_search.svg';
	manual_search.appendChild(manual_search_icon);
	manual_search_container.appendChild(manual_search);
	base_entry.appendChild(manual_search_container);

	for (i = issues.length - 1; i >= 0; i--) {
		const obj = issues[i];
		const entry = base_entry.cloneNode(true);
		entry.setAttribute('data-id', obj.id);

		const monitored_button = entry.querySelector('td.issue-monitored button');
		monitored_button.dataset.monitored = obj.monitored;
		monitored_button.id = obj.id;
		monitored_button.addEventListener('click', e => toggleMonitoredIssue(obj.id));
		monitored_button.querySelector('img').src = obj.monitored === true ? '/static/img/monitored.svg' : '/static/img/unmonitored.svg';
		
		entry.querySelector('td.issue-number').innerText = obj.issue_number;
		
		entry.querySelector('td.issue-title').innerText = obj.title;

		entry.querySelector('td.issue-date').innerText = obj.date;

		if (obj.files.length === 0) {
			// Not downloaded
			entry.querySelector('td.issue-status img').src = '/static/img/cancel_search.svg';
		} else {
			// Downloaded
			entry.querySelector('td.issue-status img').src = '/static/img/check.svg';
		};
		
		entry.querySelector('td.issue-search button').addEventListener('click', e => autosearchIssue(obj.id));
		
		entry.querySelector('td.issue-manual-search button').addEventListener('click', e => showManualSearch(obj.id))

		table.appendChild(entry);
	};
	return;
};

function fillPage(data) {
	// set volume data
	const monitor = document.getElementById('volume-monitor');
	const monitor_icon = document.getElementById('volume-monitor-icon');
	const title = document.getElementById('volume-title');
	const cover = document.getElementById('volume-cover');
	const tags = document.getElementById('volume-tags');
	monitor.dataset.monitored = data.monitored;
	monitor.addEventListener('click', e => toggleMonitored());
	monitor_icon.src = data.monitored === true ? '/static/img/monitored_light.svg' : '/static/img/unmonitored_light.svg';
	title.innerText = data.title;
	cover.src = `${data.cover}?api_key=${api_key}`;
	const year = document.createElement('p');
	year.innerText = data.year;
	year.classList.add('volume-tag');
	tags.appendChild(year);
	const volume_number = document.createElement('p');
	if (data.volume_number === null) {
		volume_number.innerText = 'Volume 1';
	} else {
		volume_number.innerText = `Volume ${data.volume_number}`;
	};
	volume_number.classList.add('volume-tag');
	tags.appendChild(volume_number);
	const path = document.getElementById('volume-path');
	path.innerText = data.folder;
	const description = document.getElementById('volume-description');
	description.innerHTML = data.description;
	const mobile_description = document.getElementById('volume-description-mobile');
	mobile_description.innerHTML = data.description;

	// fill issue lists
	fillTable(data.issues);
	return;
};

function toggleMonitored() {
	const el = document.getElementById('volume-monitor');
	const icon = el.firstChild;
	data = {
		'monitor': el.dataset.monitored === 'true' ? false : true
	};
	fetch(`/api/volumes/${id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		el.dataset.monitored = data.monitor;
		icon.src = el.dataset.monitored === 'true' ? '/static/img/monitored_light.svg' : '/static/img/unmonitored_light.svg';
	})
}

function toggleMonitoredIssue(issue_id) {
	const el = document.getElementById(issue_id);
	const icon = el.firstChild;
	const monitor = el.dataset.monitored === 'true' ? false : true;
	fetch(`/api/issues/${issue_id}?api_key=${api_key}&monitor=${monitor}`, {
		'method': 'PUT',
	})
	.then(response => {
		el.dataset.monitored = el.dataset.monitored === 'true' ? false : true;
		icon.src = el.dataset.monitored === 'true' ? '/static/img/monitored.svg' : '/static/img/unmonitored.svg';
	});
};

function refreshVolume() {
	const el = document.querySelector('#refresh-button > img');
	el.src = '/static/img/loading_white.svg';
	el.classList.add('spinning');
	fetch(`/api/system/tasks?api_key=${api_key}&cmd=refresh_and_scan&volume_id=${id}`, {
		'method': 'POST'
	});
};

function autosearchVolume() {
	const el = document.querySelector('#autosearch-button > img');
	el.src = '/static/img/loading_white.svg';
	el.classList.add('spinning');
	fetch(`/api/system/tasks?api_key=${api_key}&cmd=auto_search&volume_id=${id}`, {
		'method': 'POST'
	});
};

function autosearchIssue(issue_id) {
	const el = document.querySelector(`tr[data-id="${issue_id}"] > td.issue-search > button > img`);
	el.src = '/static/img/loading.svg';
	el.classList.add('spinning');
	fetch(`/api/system/tasks?api_key=${api_key}&cmd=auto_search_issue&volume_id=${id}&issue_id=${issue_id}`, {
		'method': 'POST'
	})
}

function showEdit() {
	document.getElementById('monitored-input').value = document.getElementById('volume-monitor').dataset.monitored;
	fetch(`/api/volumes/${id}?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const volume_root_folder = json.result.root_folder;

		fetch(`/api/rootfolder?api_key=${api_key}`)
		.then(response => response.json())
		.then(json => {
			const table = document.getElementById('root-folder-input');
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
			showWindow('editing-window');
		});
	});
};

function editVolume() {
	showWindow("edit-loading-window");

	const data = {
		'monitor': document.getElementById('monitored-input').value == 'true',
		'root_folder_id': parseInt(document.getElementById('root-folder-input').value)
	}
	document.getElementById('submit-edit').innerText = 'Updating...';
	fetch(`/api/volumes/${id}?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		window.location.reload();
	});
	
	return;
};

function deleteVolume() {
	const delete_folder = document.getElementById('delete-folder-input').value;
	fetch(`/api/volumes/${id}?api_key=${api_key}&delete_folder=${delete_folder}`, {
		'method': 'DELETE'
	})
	.then(response => {
		window.location.href = '/';
	});
};

function showRename() {
	fetch(`/api/volumes/${id}/rename?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const minus = document.createElement('span');
		minus.classList.add('rename-minus');
		minus.innerText = '-';
		const plus = document.createElement('span');
		plus.classList.add('rename-plus');
		plus.innerText = '+';

		const table = document.querySelector('#rename-preview > tbody');
		table.innerHTML = '';
		const rename_button = document.getElementById('submit-rename');
		
		if (json.result.length === 0) {
			const message = document.createElement('p');
			message.classList.add('empty-rename-message');
			message.innerText = 'Nothing to rename';
			table.appendChild(message);
			rename_button.classList.add('hidden');
		} else {
			rename_button.classList.remove('hidden');
			json.result.forEach(rename_entry => {
				const entry = document.createElement('tr');
				const entry_data = document.createElement('td');
				const before = document.createElement('p');
				const before_text = document.createElement('span');
				before_text.innerText = rename_entry.before;
				before.appendChild(minus.cloneNode(true));
				before.appendChild(before_text);
				const after = document.createElement('p');
				const after_text = document.createElement('span');
				after_text.innerText = rename_entry.after;
				after.appendChild(plus.cloneNode(true));
				after.appendChild(after_text);
				entry_data.appendChild(before);
				entry_data.appendChild(after);
				entry.appendChild(entry_data);
				table.appendChild(entry);
			});
		};
		showWindow('renaming-window');
	});
};

function renameVolume() {
	document.getElementById('submit-rename').innerText = 'Renaming...';
	fetch(`/api/volumes/${id}/rename?api_key=${api_key}`, {
		'method': 'POST'
	})
	.then(response => {
		window.location.reload();
	});
};

function showManualSearch(issue_id=null) {
	// Display searching message
	const message = document.getElementById('searching-message');
	message.classList.remove('hidden');
	const table = document.getElementById('search-result-table');
	table.classList.add('hidden');
	const tbody = document.getElementById('search-results');

	// Show window
	showWindow('manual-search-window');

	// Start search
	tbody.innerHTML = '';
	const url = issue_id !== null ? `/api/issues/${issue_id}/manualsearch` : `/api/volumes/${id}/manualsearch`;
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
				match_icon.src = '/static/img/check.svg';
			} else {
				match_icon.src = '/static/img/cancel_search.svg';
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
			add_entry.addEventListener('click', e => addManualSearch(result.link, add_entry, issue_id));
			const add_entry_icon = document.createElement('img');
			add_entry_icon.src = '/static/img/download.svg';
			add_entry.appendChild(add_entry_icon);
			action.appendChild(add_entry);
			if (result.match_issue !== 'Link is blocklisted') {
				const blocklist_entry = document.createElement('button');
				blocklist_entry.title = 'Add to blocklist';
				blocklist_entry.addEventListener('click', e => blockManualSearch(result.link, blocklist_entry, match));
				const blocklist_entry_icon = document.createElement('img');
				blocklist_entry_icon.src = '/static/img/blocklist.svg';
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

function addManualSearch(link, button, issue_id=null) {
	const img = button.querySelector('img');
	img.src = '/static/img/loading.svg';
	img.classList.add('spinning');
	const url = issue_id !== null ? `/api/issues/${issue_id}/download` : `/api/volumes/${id}/download`;
	fetch(`${url}?api_key=${api_key}&link=${link}`, {
		'method': 'POST'
	})
	.then(response => response.json())
	.then(json => {
		img.classList.remove('spinning');
		if (json.result.length > 0) {
			img.src = '/static/img/check.svg';
		} else {
			img.src = '/static/img/download_failed.svg';
		};
	});
};

function blockManualSearch(link, button, match) {
	fetch(`/api/blocklist?api_key=${api_key}&link=${link}&reason_id=4`, {
		'method': 'POST'
	})
	.then(response => {
		button.querySelector('img').src = '/static/img/check.svg';
		match.innerText = 'No';
		match.title = 'Link is blocklisted';
	});
};

// code run on load
const api_key = sessionStorage.getItem('api_key');
const id = window.location.pathname.split('/').at(-1);

fetch(`/api/volumes/${id}?api_key=${api_key}`)
.then(response => {
	// catch errors
	if (!response.ok) return Promise.reject(response.status);
	return response.json();
})
.then(json => fillPage(json.result))
.catch(e => {
	if (e === 404) {
		window.location.href = '/';
	};
});

document.getElementById('refresh-button').addEventListener('click', e => refreshVolume());
document.getElementById('autosearch-button').addEventListener('click', e => autosearchVolume());

document.getElementById('manualsearch-button').addEventListener('click', e => showManualSearch());
document.getElementById('cancel-search').addEventListener('click', e => closeWindow());

document.getElementById('rename-button').addEventListener('click', e => showRename());
document.getElementById('cancel-rename').addEventListener('click', e => closeWindow());
document.getElementById('submit-rename').addEventListener('click', e => renameVolume());

document.getElementById('edit-button').addEventListener('click', e => showEdit());
document.getElementById('edit-form').setAttribute('action', 'javascript:editVolume();');
document.getElementById('cancel-edit').addEventListener('click', e => closeWindow());

document.getElementById('delete-button').addEventListener('click', e => showWindow('deleting-window'));
document.getElementById('delete-form').setAttribute('action', 'javascript:deleteVolume();');
document.getElementById('cancel-delete').addEventListener('click', e => closeWindow());

