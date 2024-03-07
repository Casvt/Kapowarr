//
// Library
//
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
	stats: {
		volume_count: document.querySelector('#volume-count'),
		volume_monitored_count: document.querySelector('#volume-monitored-count'),
		volume_unmonitored_count: document.querySelector('#volume-unmonitored-count'),
		issue_count: document.querySelector('#issue-count'),
		issue_download_count: document.querySelector('#issue-download-count'),
		file_count: document.querySelector('#file-count'),
		total_file_size: document.querySelector('#total-file-size')
	}
};

const pre_build_els = {
	list_entry: document.querySelector('.pre-build-els .list-entry'),
	table_entry: document.querySelector('.pre-build-els .table-entry')
};

function showLibraryPage(el) {
	Object.values(library_els.pages).forEach(v => v.classList.add('hidden'));
	el.classList.remove('hidden');
};

class LibraryEntry {
	constructor(id, api_key) {
		this.id = id;
		this.api_key = api_key;
		this.list_entry = library_els.views.list.querySelector(`.vol-${id}`);
		this.table_entry = library_els.views.table.querySelector(`.vol-${id}`);
	};
	
	setMonitored(monitored) {
		fetch(`${url_base}/api/volumes/${this.id}?api_key=${this.api_key}`, {
			'method': 'PUT',
			'headers': {'Content-Type': 'application/json'},
			'body': JSON.stringify({'monitored': monitored})
		})
		.then(response => {
			const monitored_button = this.table_entry.querySelector('.table-monitored');
			monitored_button.onclick = e => new LibraryEntry(this.id, this.api_key)
				.setMonitored(!monitored);
	
			if (monitored) {
				this.list_entry.setAttribute('monitored', '');
				monitored_button.title = 'Monitored'
				monitored_button.innerHTML =
					icons.monitored;
	
			} else {
				this.list_entry.removeAttribute('monitored');
				monitored_button.title = 'Unmonitored'
				monitored_button.innerHTML =
					icons.unmonitored;
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
		
		// ID
		list_entry.classList.add(`vol-${volume.id}`);
		table_entry.classList.add(`vol-${volume.id}`);

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

			monitored_button.title = 'Monitored'
			monitored_button.innerHTML =
				icons.monitored;

		} else {
			monitored_button.title = 'Unmonitored'
			monitored_button.innerHTML =
				icons.unmonitored;
		};
		
		// Add to view
		library_els.views.list.insertBefore(list_entry, space_taker);
		library_els.views.table.appendChild(table_entry);
	});
};

function fetchLibrary(api_key) {
	showLibraryPage(library_els.pages.loading);

	const sort = document.querySelector('#sort-button').value;
	const filter = document.querySelector('#filter-button').value;
	const query = document.querySelector('#search-input').value;
	let url;
	if (query === '')
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}&filter=${filter}`;
	else
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}&query=${query}&filter=${filter}`;

	fetch(url)
	.then(response => response.json())
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
	document.querySelector('#search-input').value = '';
	fetchLibrary(api_key);
};

function fetchStats(api_key) {
	fetch(`${url_base}/api/volumes/stats?api_key=${api_key}`)
	.then(response => response.json())
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
// Actions
//
function updateAll(api_key) {
	fetch(
		`${url_base}/api/system/tasks?api_key=${api_key}&cmd=update_all`,
		{'method': 'POST'}
	);
};

function searchAll(api_key) {
	fetch(
		`${url_base}/api/system/tasks?api_key=${api_key}&cmd=search_all`,
		{'method': 'POST'}
	);
};

// code run on load

document.querySelector('#sort-button').value = getLocalStorage('lib_sorting')['lib_sorting'];
document.querySelector('#view-button').value = getLocalStorage('lib_view')['lib_view'];
document.querySelector('#filter-button').value = getLocalStorage('lib_filter')['lib_filter'];
usingApiKey()
.then(api_key => {
	fetchLibrary(api_key);
	fetchStats(api_key);

	addEventListener('#clear-search', 'click', e => clearSearch(api_key));
	addEventListener('#updateall-button', 'click', e => updateAll(api_key));
	addEventListener('#searchall-button', 'click', e => searchAll(api_key));
	addEventListener('#sort-button', 'change', e => {
		setLocalStorage({'lib_sorting': document.querySelector('#sort-button').value});
		fetchLibrary(api_key);
	});
	addEventListener('#view-button', 'change', e => {
		setLocalStorage({'lib_view': document.querySelector('#view-button').value});
	});
	addEventListener('#filter-button', 'change', e => {
		setLocalStorage({'lib_filter': document.querySelector('#filter-button').value});
		fetchLibrary(api_key);
	});
});
setAttribute('#search-container', 'action', 'javascript:searchLibrary();');
