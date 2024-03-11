const ViewEls = {
	views: {
		loading: document.querySelector('#loading-screen'),
		main: document.querySelector('main')
	},
	pre_build: {
		issue_entry: document.querySelector('.pre-build-els .issue-entry'),
		manual_search: document.querySelector('.pre-build-els .search-entry'),
		rename_before: document.querySelector('.pre-build-els .rename-before'),
		rename_after: document.querySelector('.pre-build-els .rename-after')
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
class IssueEntry {
	constructor(id, api_key) {
		this.id = id;
		this.api_key = api_key;
		this.entry = ViewEls.issues_list.querySelector(`tr[data-id="${id}"]`);

		this.monitored = this.entry.querySelector('.issue-monitored button');
		this.issue_number = this.entry.querySelector('.issue-number');
		this.title = this.entry.querySelector('.issue-title');
		this.date = this.entry.querySelector('.issue-date');
		this.status = this.entry.querySelector('.issue-status');
		this.auto_search = this.entry.querySelector('.action-column :nth-child(1)');
		this.manual_search = this.entry.querySelector('.action-column :nth-child(2)');
		this.convert = this.entry.querySelector('.action-column :nth-child(3)');
	};

	setMonitorIcon() {
		if (this.monitored.dataset.monitored === 'true') {
			setIcon(
				this.monitored,
				icons.monitored,
				'Issue is monitored. Click to unmonitor.'
			);
		} else {
			setIcon(
				this.monitored,
				icons.unmonitored,
				'Issue is umonitored. Click to monitor.'
			);
		};
	};

	toggleMonitored() {
		const monitored = this.monitored.dataset.monitored !== 'true';
		sendAPI('PUT', `/issues/${this.id}`, this.api_key, {}, {
			'monitored': monitored
		})
		.then(response => {
			this.monitored.dataset.monitored = monitored;
			this.setMonitorIcon();
		});
	};

	setDownloaded(downloaded) {
		if (downloaded) {
			// Downloaded
			setImage(this.status, images.check, 'Issue is downloaded');
		} else {
			// Not downloaded
			setImage(this.status, images.cancel, 'Issue is not downloaded');
		};
	};
};

function fillTable(issues, api_key) {
	ViewEls.issues_list.innerHTML = '';

	for (i = issues.length - 1; i >= 0; i--) {
		const obj = issues[i];

		const entry = ViewEls.pre_build.issue_entry.cloneNode(deep=true);
		entry.dataset.id = obj.id;
		ViewEls.issues_list.appendChild(entry);

		const inst = new IssueEntry(obj.id, api_key);

		// Monitored
		inst.monitored.dataset.monitored = obj.monitored;
		inst.monitored.dataset.id = obj.id;
		inst.monitored.onclick = e => inst.toggleMonitored();
		inst.setMonitorIcon();

		// Issue number
		inst.issue_number.innerText = obj.issue_number;

		// Title
		inst.title.innerText = obj.title;
		inst.title.onclick = e => showIssueInfo(obj.id, api_key);

		// Release date
		inst.date.innerText = obj.date;

		// Download status
		inst.setDownloaded(obj.files.length);

		// Actions
		inst.auto_search.onclick = e => autosearchIssue(obj.id, api_key);
		inst.manual_search.onclick = e => showManualSearch(api_key, obj.id);
		inst.convert.onclick = e => showConvert(api_key, obj.id);
	};
};

function fillPage(data, api_key) {
	// Cover
	ViewEls.vol_data.cover.src = `${url_base}/api/volumes/${data.id}/cover?api_key=${api_key}`;

	// Monitored state
	const monitor = ViewEls.vol_data.monitor;
	monitor.dataset.monitored = data.monitored;
	monitor.onclick = e => toggleMonitored(api_key);
	if (data.monitored)
		// Volume is monitored
		setIcon(monitor, icons.monitored, 'Volume is monitored. Click to unmonitor.');
	else
		// Volume is unmonitored
		setIcon(monitor, icons.unmonitored, 'Volume is unmonitored. Click to monitor.');

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
	const total_size = document.createElement('p');
	total_size.innerText = data.total_size > 0 ? convertSize(data.total_size) : '0MB';
	tags.appendChild(total_size);

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
	const monitored = button.dataset.monitored !== 'true';
	sendAPI('PUT', `/volumes/${id}`, api_key, {}, {
		monitored: monitored
	})
	.then(response => {
		button.dataset.monitored = monitored;
		if (monitored)
			setIcon(
				button,
				icons.monitored,
				'Volume is monitored. Click to unmonitor.'
			);
		else
			setIcon(
				button,
				icons.unmonitored,
				'Volume is unmonitored. Click to monitor.'
			);
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

	sendAPI('POST', '/system/tasks', api_key, {
		cmd: 'refresh_and_scan',
		volume_id: id
	}, {})
};

function autosearchVolume(api_key) {
	const button_info = task_to_button[`auto_search#${id}`];
	const icon = button_info.button.querySelector('img');
	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');

	sendAPI('POST', '/system/tasks', api_key, {
		cmd: 'auto_search',
		volume_id: id
	}, {})
};

function autosearchIssue(issue_id, api_key) {
	const button_info = task_to_button[`auto_search_issue#${id}#${issue_id}`];
	const icon = button_info.button.querySelector('img');
	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');

	sendAPI('POST', '/system/tasks', api_key, {
		cmd: 'auto_search_issue',
		volume_id: id,
		issue_id: issue_id
	}, {})
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
	const url = issue_id
			? `/issues/${issue_id}/manualsearch`
			: `/volumes/${id}/manualsearch`;

	fetchAPI(url, api_key)
	.then(json => {
		json.result.forEach(result => {
			const entry = ViewEls.pre_build.manual_search.cloneNode(true);
			tbody.appendChild(entry);

			const match = entry.querySelector('.match-column');
			if (result.match)
				setImage(
					match,
					images.check,
					''
				);
			else
				setImage(
					match,
					images.cancel,
					result.match_issue
				);

			const title = entry.querySelector('a');
			title.href = result.link;
			title.innerText = result.display_title;

			entry.querySelector('.source-column').innerText = result.source;

			const download_button = entry.querySelector('.search-action-column :nth-child(1)')
			download_button.onclick =
				e => addManualSearch(result.link, download_button, api_key, issue_id);

			const blocklist_button = entry.querySelector('.search-action-column :nth-child(2)')
			if (result.match_issue === null || !result.match_issue.includes('blocklist'))
				// Show blocklist button
				blocklist_button.onclick =
					e => blockManualSearch(
						result.link,
						blocklist_button,
						match,
						api_key
					);
			else
				// No blocklist button
				blocklist_button.remove()
		});

		message.classList.add('hidden');
		table.classList.remove('hidden');
	});
};

function addManualSearch(link, button, api_key, issue_id=null) {
	const img = button.querySelector('img');
	img.src = `${url_base}/static/img/loading.svg`;
	img.classList.add('spinning');

	const url = issue_id
		? `/issues/${issue_id}/download`
		: `/volumes/${id}/download`;

	sendAPI('POST', url, api_key, {link: link})
	.then(response => response.json())
	.then(json => {
		img.classList.remove('spinning');
		if (json.result.length) img.src = `${url_base}/static/img/check.svg`;
		else img.src = `${url_base}/static/img/download_failed.svg`;
	});
};

function blockManualSearch(link, button, match, api_key) {
	sendAPI('POST', '/blocklist', api_key, {
		link: link,
		reason_id: 4
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
		url = `/volumes/${id}/rename`;
		rename_button.dataset.issue_id = '';
	} else {
		// Preview issue rename
		url = `/issues/${issue_id}/rename`;
		rename_button.dataset.issue_id = issue_id;
	};
	fetchAPI(url, api_key)
	.then(json => {
		const empty_message = document.querySelector('#rename-window .empty-rename-message');
		const table_container = document.querySelector('.rename-preview');
		const table = table_container.querySelector('tbody');
		table.innerHTML = '';

		if (!json.result.length) {
			empty_message.classList.remove('hidden');
			table_container.classList.add('hidden');
		} else {
			empty_message.classList.add('hidden');
			table_container.classList.remove('hidden');
			rename_button.classList.remove('hidden');
			json.result.forEach(rename_entry => {
				const before = ViewEls.pre_build.rename_before.cloneNode(true);
				table.appendChild(before);
				const after = ViewEls.pre_build.rename_after.cloneNode(true);
				table.appendChild(after);

				before.querySelector('td:last-child').innerText = rename_entry.before;
				after.querySelector('td:last-child').innerText = rename_entry.after;
			});
		};
		showWindow('rename-window');
	});
};

function toggleAllRenames() {
	const checked = document.querySelector('#selectall-input').checked;
	document.querySelectorAll(
		'#rename-window tbody input[type="checkbox"]'
	).forEach(e => e.checked = checked);
};

function renameVolume(api_key, issue_id=null) {
	const checkboxes = [...document.querySelectorAll('#rename-window tbody input[type="checkbox"]')];
	
	if (checkboxes.every(e => !e.checked)) {
		closeWindow();
		return;
	};

	showLoadWindow('rename-window');
	let url;
	if (issue_id === null)
		url = `/volumes/${id}/rename`;
	else
		url = `/issues/${issue_id}/rename`;

	sendAPI(
		'POST',
		url,
		api_key,
		{}, 
		checkboxes
			.filter(e => e.checked)
			.map(e => e.parentNode.parentNode.querySelector('td:last-child').innerText)
	)
	.then(response => 
		window.location.reload()
	);
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
