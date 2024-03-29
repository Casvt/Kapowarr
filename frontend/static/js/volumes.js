const library_els = {
	pages: {
		loading: document.querySelector('#loading-library'),
		empty: document.querySelector('#empty-library'),
		view: document.querySelector('#library-container'),
	},
	views: {
		list: document.querySelector('#list-library'),
		table: document.querySelector('#table-library'),
	},
	view_options: {
		sort: document.querySelector('#sort-button'),
		view: document.querySelector('#view-button'),
		filter: document.querySelector('#filter-button')
	},
	task_buttons: {
		update_all: document.querySelector('#updateall-button'),
		search_all: document.querySelector('#searchall-button')
	},
	search: {
		clear: document.querySelector('#clear-search'),
		container: document.querySelector('#search-container'),
		input: document.querySelector('#search-input')
	},
	stats: {
		volume_count: document.querySelector('#volume-count'),
		volume_monitored_count: document.querySelector('#volume-monitored-count'),
		volume_unmonitored_count: document.querySelector('#volume-unmonitored-count'),
		issue_count: document.querySelector('#issue-count'),
		issue_download_count: document.querySelector('#issue-download-count'),
		file_count: document.querySelector('#file-count'),
		total_file_size: document.querySelector('#total-file-size')
	},
	mass_edit: {
		bar: document.querySelector('.action-bar'),
		button: document.querySelector('#massedit-button'),
		toggle: document.querySelector('#massedit-toggle'),
		select_all: document.querySelector('#selectall-input'),
		cancel: document.querySelector('#cancel-massedit')
	}
};

const pre_build_els = {
	list_entry: document.querySelector('.pre-build-els .list-entry'),
	table_entry: document.querySelector('.pre-build-els .table-entry')
};

function showLibraryPage(el) {
	hide(Object.values(library_els.pages), [el]);
};

class LibraryEntry {
	constructor(id, api_key) {
		this.id = id;
		this.api_key = api_key;
		this.list_entry = library_els.views.list.querySelector(`.vol-${id}`);
		this.table_entry = library_els.views.table.querySelector(`.vol-${id}`);
	};

	setMonitored(monitored) {
		sendAPI('PUT', `/volumes/${this.id}`, this.api_key, {}, {
			monitored: monitored
		})
		.then(response => {
			const monitored_button = this.table_entry.querySelector('.table-monitored');
			monitored_button.onclick = e => new LibraryEntry(this.id, this.api_key)
				.setMonitored(!monitored);

			if (monitored) {
				this.list_entry.setAttribute('monitored', '');
				setIcon(monitored_button, icons.monitored, 'Monitored');

			} else {
				this.list_entry.removeAttribute('monitored');
				setIcon(monitored_button, icons.unmonitored, 'Unmonitored');
			};
		});
	};
};

function populateLibrary(volumes, api_key) {
	library_els.views.list.querySelectorAll('.list-entry').forEach(
		e => e.remove()
	);
	library_els.views.table.innerHTML = '';
	const space_taker = document.querySelector('.space-taker');

	volumes.forEach(volume => {
		const list_entry = pre_build_els.list_entry.cloneNode(true),
			table_entry = pre_build_els.table_entry.cloneNode(true);

		// Label
		list_entry.ariaLabel = table_entry.ariaLabel =
			`View the volume ${volume.title} (${volume.year}) Volume ${volume.volume_number}`;

		// ID
		list_entry.classList.add(`vol-${volume.id}`);
		table_entry.classList.add(`vol-${volume.id}`);
		table_entry.dataset.id = volume.id;

		// Link
		list_entry.href =
		table_entry.querySelector('.table-link').href =
			`${url_base}/volumes/${volume.id}`;

		// Cover
		list_entry.querySelector('.list-img').src =
			`${url_base}/api/volumes/${volume.id}/cover?api_key=${api_key}`;

		// Title
		const list_title = list_entry.querySelector('.list-title');
		list_title.innerText =
		list_title.title =
			`${volume.title} (${volume.year})`;
		table_entry.querySelector('.table-link').innerText =
			volume.title;

		// Year
		table_entry.querySelector('.table-year').innerText =
			volume.year;

		// Volume Number
		list_entry.querySelector('.list-volume').innerText =
		table_entry.querySelector('.table-volume').innerText =
			`Volume ${volume.volume_number}`;

		// Progress Bar
		const progress = (volume.issues_downloaded_monitored
						/ volume.issue_count_monitored 			* 100);
		const list_bar = list_entry.querySelector('.list-prog-bar'),
			table_bar = table_entry.querySelector('.table-prog-bar');

		list_entry.querySelector('.list-prog-num').innerText =
		table_entry.querySelector('.table-prog-num').innerText =
			`${volume.issues_downloaded_monitored}/${volume.issue_count_monitored}`;

		list_bar.style.width =
		table_bar.style.width =
			`${progress}%`;

		if (progress === 100)
			list_bar.style.backgroundColor =
			table_bar.style.backgroundColor =
				'var(--success-color)';

		else if (volume.monitored === true)
			list_bar.style.backgroundColor =
			table_bar.style.backgroundColor =
				'var(--accent-color)';

		else
			list_bar.style.backgroundColor =
			table_bar.style.backgroundColor =
				'var(--error-color)';

		// Monitored
		const monitored_button = table_entry.querySelector('.table-monitored');
		monitored_button.onclick = e => new LibraryEntry(volume.id, api_key)
			.setMonitored(!volume.monitored);
		if (volume.monitored) {
			list_entry.setAttribute('monitored', '');
			setIcon(monitored_button, icons.monitored, 'Monitored');
		} else
			setIcon(monitored_button, icons.unmonitored, 'Unmonitored');

		// Add to view
		library_els.views.list.insertBefore(list_entry, space_taker);
		library_els.views.table.appendChild(table_entry);
	});
};

function fetchLibrary(api_key) {
	showLibraryPage(library_els.pages.loading);

	const params = {
		sort: library_els.view_options.sort.value,
		filter: library_els.view_options.filter.value
	};
	const query = library_els.search.input.value;
	if (query !== '')
		params.query = query;

	fetchAPI('/volumes', api_key, params)
	.then(json => {
		if (json.result.length === 0) {
			showLibraryPage(library_els.pages.empty);
		} else {
			populateLibrary(json.result, api_key);
			showLibraryPage(library_els.pages.view);
		};
	});
};

function searchLibrary() {
	usingApiKey().then(api_key => fetchLibrary(api_key));
};

function clearSearch(api_key) {
	library_els.search.input.value = '';
	fetchLibrary(api_key);
};

function fetchStats(api_key) {
	fetchAPI('/volumes/stats', api_key)
	.then(json => {
		library_els.stats.volume_count.innerText = json.result.volumes;
		library_els.stats.volume_monitored_count.innerText = json.result.monitored;
		library_els.stats.volume_unmonitored_count.innerText = json.result.unmonitored;
		library_els.stats.issue_count.innerText = json.result.issues;
		library_els.stats.issue_download_count.innerText = json.result.downloaded_issues;
		library_els.stats.file_count.innerText = json.result.files;
		library_els.stats.total_file_size.innerText = convertSize(json.result.total_file_size);
	});
};

//
// Mass Edit
//
function runAction(api_key, action, args={}) {
	showLibraryPage(library_els.pages.loading);

	const volume_ids = [...library_els.views.table.querySelectorAll(
		'input[type="checkbox"]:checked'
	)].map(v => parseInt(v.parentNode.parentNode.dataset.id))

	sendAPI('POST', '/masseditor', api_key, {}, {
		'volume_ids': volume_ids,
		'action': action,
		'args': args
	})
	.then(response => {
		library_els.mass_edit.select_all.checked = false;
		fetchLibrary(api_key);
	});
};

// code run on load

library_els.view_options.sort.value = getLocalStorage('lib_sorting')['lib_sorting'];
library_els.view_options.view.value = getLocalStorage('lib_view')['lib_view'];
library_els.view_options.filter.value = getLocalStorage('lib_filter')['lib_filter'];
usingApiKey()
.then(api_key => {
	fetchLibrary(api_key);
	fetchStats(api_key);

	library_els.search.clear.onclick =
		e => clearSearch(api_key);

	library_els.task_buttons.update_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {'cmd': 'update_all'});
	library_els.task_buttons.search_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {'cmd': 'search_all'});

	library_els.view_options.sort.onchange = e => {
		setLocalStorage({'lib_sorting': library_els.view_options.sort.value});
		fetchLibrary(api_key);
	};
	library_els.view_options.view.onchange =
		e => setLocalStorage({'lib_view': library_els.view_options.view.value});
	library_els.view_options.filter.onchange = e => {
		setLocalStorage({'lib_filter': library_els.view_options.filter.value});
		fetchLibrary(api_key);
	};

	library_els.mass_edit.bar.querySelectorAll('.action-divider > button[data-action]').forEach(
		b => b.onclick = e => runAction(api_key, e.target.dataset.action)
	);
	library_els.mass_edit.bar.querySelector('button[data-action="delete"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'delete_folder': document.querySelector(
					'select[name="delete_folder"]'
				).value === "true"
			}
		);
});
library_els.search.container.action = 'javascript:searchLibrary();';
library_els.mass_edit.button.onclick =
library_els.mass_edit.cancel.onclick =
	e => library_els.mass_edit.toggle.toggleAttribute('checked');
library_els.mass_edit.select_all.onchange =
	e => library_els.views.table.querySelectorAll('input[type="checkbox"]')
			.forEach(c => c.checked = library_els.mass_edit.select_all.checked);
