//
// Library
//
function populateLibrary(volumes, api_key) {
	const table = document.querySelector('#library');
	const space_taker = document.querySelector('.space-taker');
	table.querySelectorAll('a').forEach(e => e.remove())
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
		const calc = volume.issues_downloaded / volume.issue_count * 100;
		if (calc === 100) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--success-color);`);
		} else if (volume.monitored === true) {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--accent-color);`);
		} else {
			progress_bar.setAttribute('style', `width: ${calc}%; background-color: var(--error-color);`);
		};
		progress.appendChild(progress_bar);
		const progress_text = document.createElement('div');
		progress_text.innerText = `${volume.issues_downloaded}/${volume.issue_count}`;
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

function fetchLibrary(api_key) {
	const sort = document.querySelector('#sort-button').value;
	const query = document.querySelector('#search-input').value;
	let url;
	if (query === '')
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}`;
	else
		url = `${url_base}/api/volumes?api_key=${api_key}&sort=${sort}&query=${query}`;
	fetch(url)
	.then(response => response.json())
	.then(json => populateLibrary(json.result, api_key));
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
usingApiKey()
.then(api_key => {
	fetchLibrary(api_key);
	fetchStats(api_key);

	addEventListener('#clear-search', 'click', e => clearSearch(api_key));
	addEventListener('#start-search', 'click', e => fetchLibrary(api_key));
	addEventListener('#search-input', 'keydown', e => e.code === 'Enter' ? fetchLibrary(api_key) : null);
	addEventListener('#updateall-button', 'click', e => updateAll(api_key));
	addEventListener('#searchall-button', 'click', e => searchAll(api_key));
	addEventListener('#sort-button', 'change', e => {
		setLocalStorage({'lib_sorting': document.querySelector('#sort-button').value});
		fetchLibrary(api_key);
	});
});
