//
// Library
//
function populatePosters(volumes, api_key) {
	const table = document.querySelector('#library');
	const space_taker = document.querySelector('.space-taker');
	space_taker.classList.remove('hidden');
	table.querySelectorAll('#library > a, #library > .table-container').forEach(e => e.remove());
	volumes.forEach(volume => {
		const entry = document.createElement("a");
		entry.href = `${url_base}/volumes/${volume.id}`;

		const cover = document.createElement("img");
		cover.src = `${volume.cover}?api_key=${api_key}`;
		cover.alt = "";
		cover.loading = "lazy";
		entry.appendChild(cover);
		
		const progress = document.createElement('div');
		const progress_bar = document.createElement('div');
		const calc = volume.issues_downloaded_monitored / volume.issue_count_monitored * 100;
		if (calc === 100) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--success-color);`);
		} else if (volume.monitored === true) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--accent-color);`);
		} else {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--error-color);`);
		};
		progress.appendChild(progress_bar);
		const progress_text = document.createElement('div');
		progress_text.innerText = `${volume.issues_downloaded_monitored}/${volume.issue_count_monitored}`;
		progress.appendChild(progress_text);
		entry.appendChild(progress);

		const title = document.createElement("h2");
		title.innerText = `${volume.title} (${volume.year})`;
		title.title = `${volume.title} (${volume.year})`;
		entry.appendChild(title);

		const volume_number = document.createElement("p");
		volume_number.innerText = `Volume ${volume.volume_number}`;
		entry.append(volume_number);

		const monitored = document.createElement("p");
		monitored.innerText = volume.monitored ? 'Monitored' : 'Unmonitored';
		entry.appendChild(monitored);

		table.insertBefore(entry, space_taker);
	});
};

function populateTable(volumes) {
	const space_taker = document.querySelector('.space-taker');
	space_taker.classList.add('hidden');

	const library = document.querySelector('#library');
	library.querySelectorAll('#library > a, #library > .table-container').forEach(e => e.remove());

	const table_container = document.createElement('div');
	table_container.classList.add('table-container');
	const table = document.createElement('table');
	table_container.appendChild(table);
	const thead = document.createElement('thead');
	table.appendChild(thead);
	const head_row = document.createElement('tr');
	thead.appendChild(head_row);
	['Volume Title', 'Year', 'Progress', 'Monitored'].forEach(h => {
		const entry = document.createElement('th');
		entry.innerText = h;
		head_row.appendChild(entry);
	});
	const list = document.createElement('tbody');
	table.appendChild(list);
	library.insertBefore(table_container, space_taker);

	volumes.forEach(volume => {
		const entry = document.createElement('tr');

		const title_container = document.createElement('td');
		const title = document.createElement('a');
		title.innerText = volume.title;
		title.title = volume.title;
		title.href = `${url_base}/volumes/${volume.id}`;
		title_container.appendChild(title);
		entry.appendChild(title_container);

		const year = document.createElement('td');
		year.innerText = volume.year;
		entry.appendChild(year);
		
		const progress_container = document.createElement('td');
		const progress = document.createElement('div');
		const progress_bar = document.createElement('div');
		const calc = volume.issues_downloaded_monitored / volume.issue_count_monitored * 100;
		if (calc === 100) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--success-color);`);
		} else if (volume.monitored === true) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--accent-color);`);
		} else {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--error-color);`);
		};
		progress.appendChild(progress_bar);
		const progress_text = document.createElement('div');
		progress_text.innerText = `${volume.issues_downloaded_monitored}/${volume.issue_count_monitored}`;
		progress.appendChild(progress_text);
		progress_container.appendChild(progress);
		entry.appendChild(progress_container);
		
		const monitored_container = document.createElement('td');
		const monitored = document.createElement('img');
		monitored.src = volume.monitored ? `${url_base}/static/img/monitored.svg` : `${url_base}/static/img/unmonitored.svg`;
		monitored.title = volume.monitored ? 'Monitored' : 'Unmonitored';
		monitored_container.appendChild(monitored);
		entry.appendChild(monitored_container);
		
		list.appendChild(entry);
	});
};

function populateLibrary(volumes, api_key, view) {
	if (view === 'posters')
		populatePosters(volumes, api_key);
	else if (view === 'table')
		populateTable(volumes);
};

function fetchLibrary(api_key) {
	const sort = document.querySelector('#sort-button').value;
	const view = document.querySelector('#view-button').value;
	const query = document.querySelector('#search-input').value;
	let url;
	if (query === '')
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}`;
	else
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}&query=${query}`;
	fetch(url)
	.then(response => response.json())
	.then(json => populateLibrary(json.result, api_key, view));
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
		document.querySelector('#volume-count').innerText = json.result.volumes;
		document.querySelector('#volume-monitored-count').innerText = json.result.monitored;
		document.querySelector('#volume-unmonitored-count').innerText = json.result.unmonitored;
		document.querySelector('#issue-count').innerText = json.result.issues;
		document.querySelector('#issue-download-count').innerText = json.result.downloaded_issues;
		document.querySelector('#file-count').innerText = json.result.files;
		document.querySelector('#total-file-size').innerText = convertSize(json.result.total_file_size);
	});
};

//
// Actions
//
function updateAll(api_key) {
	const icon = document.querySelector('#updateall-button > img');
	icon.src = task_to_button['update_all'].loading_icon;
	icon.classList.add('spinning');
	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=update_all`, {'method': 'POST'});
};

function searchAll(api_key) {
	const icon = document.querySelector('#searchall-button > img');
	icon.src = task_to_button['search_all'].loading_icon;
	icon.classList.add('spinning');
	fetch(`${url_base}/api/system/tasks?api_key=${api_key}&cmd=search_all`, {'method': 'POST'});
};

// code run on load

document.querySelector('#sort-button').value = getLocalStorage('lib_sorting')['lib_sorting'];
document.querySelector('#view-button').value = getLocalStorage('lib_view')['lib_view'];
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
		fetchLibrary(api_key);
	});
});
document.querySelector('#search-container').setAttribute('action', 'javascript:searchLibrary();');
