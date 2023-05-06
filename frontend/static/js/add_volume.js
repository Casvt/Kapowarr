// 
// Searching
// 
function buildResults(results) {
	const table = document.querySelector('#search-results');
	table.innerHTML = '';
	results.forEach(result => {
		const entry = document.createElement('button');
		entry.classList.add('search-entry');
		entry.dataset.title = result.year !== null ? `${result.title} (${result.year})` : result.title;
		entry.dataset.cover = result.cover;
		entry.dataset.comicvine_id = result.comicvine_id;

		// Only allow adding volume if it isn't already added
		if (!result.already_added)
			entry.addEventListener('click', e => showAddWindow(result.comicvine_id));

		const cover_info_container = document.createElement('div');
		cover_info_container.classList.add('cover-info-container');
		entry.appendChild(cover_info_container);

		const cover_container = document.createElement('div');
		cover_info_container.appendChild(cover_container);
		
		const cover = document.createElement('img');
		cover.src = result.cover;
		cover.alt = "";
		cover.loading = "lazy";
		cover_container.appendChild(cover);

		const info_container = document.createElement('div');
		info_container.classList.add('entry-info-container');
		cover_info_container.appendChild(info_container);

		const title = document.createElement("h2");
		title.innerText = result.title;
		info_container.appendChild(title);
		
		if (result.year !== null) {
			const year = document.createElement("span");
			year.innerText = ` (${result.year})`;
			title.appendChild(year);
		};
		
		if (result.already_added) {
			const aa_icon = document.createElement('img');
			aa_icon.alt = 'Volume is already added';
			aa_icon.src = '/static/img/check_circle.svg';
			title.appendChild(aa_icon);
		};
		
		const tags = document.createElement('div');
		tags.classList.add('entry-tags');
		info_container.appendChild(tags);

		if (result.volume_number !== null) {
			const volume_number = document.createElement('p');
			volume_number.innerText = `Volume ${result.volume_number}`;
			tags.appendChild(volume_number);
		};

		const publisher = document.createElement('p');
		publisher.innerText = result.publisher || 'Publisher Unknown';
		tags.appendChild(publisher);

		const issue_count = document.createElement('p');
		issue_count.innerText = `${result.issue_count} issues`;
		tags.appendChild(issue_count);

		const info_link = document.createElement('a');
		info_link.href = result.comicvine_info;
		info_link.innerText = 'Link';
		tags.appendChild(info_link);

		if (result.aliases.length) {
			const aliases = document.createElement('div');
			aliases.classList.add('entry-aliases');
			info_container.appendChild(aliases);
			
			result.aliases.forEach(alias_text => {
				const alias = document.createElement('p');
				alias.innerText = alias_text;
				aliases.appendChild(alias);
			});
		};
		
		const description = document.createElement('div');
		description.classList.add('entry-description', 'description');
		description.innerHTML = result.description;
		info_container.appendChild(description);

		const spare_description = document.createElement('div');
		spare_description.classList.add('entry-spare-description', 'description');
		spare_description.innerHTML = result.description;
		entry.appendChild(spare_description);

		table.appendChild(entry);
	})
	if (table.innerHTML === '') {
		document.querySelector('#search-empty').classList.remove('hidden');
	};
};

function search(api_key) {
	if (!document.querySelector('#search-blocked').classList.contains('hidden'))
		return;
	document.querySelector('#search-explain').classList.add('hidden');
	document.querySelector('#search-empty').classList.add('hidden');
	document.querySelector('#search-failed').classList.add('hidden');
	document.querySelector('#search-input').blur();

	const query = document.querySelector('#search-input').value;
	fetch(`/api/volumes/search?api_key=${api_key}&query=${query}`)
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		return response.json();
	})
	.then(json => buildResults(json.result))
	.catch(e => {
		if (e === 400) document.querySelector('#search-failed').classList.remove('hidden');
	});
};

function clearSearch(e) {
	document.querySelector('#search-results').innerHTML = '';
	document.querySelector('#search-empty').classList.add('hidden');
	document.querySelector('#search-failed').classList.add('hidden');
	if (document.querySelector('#search-blocked').classList.contains('hidden'))
		document.querySelector('#search-explain').classList.remove('hidden');
	else
		document.querySelector('#search-explain').classList.add('hidden');
	document.querySelector('#search-input').value = '';
};

// 
// Adding
//
function fillRootFolderInput(api_key) {
	const root_folder_list = document.querySelector('#rootfolder-input');
	fetch(`/api/rootfolder?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		if (json.result.length) {
			json.result.forEach(folder => {
				const option = document.createElement('option');
				option.value = folder.id;
				option.innerText = folder.folder;
				root_folder_list.appendChild(option);
			});
		} else {
			document.querySelector('#search-blocked').classList.remove('hidden');
		};
	});
};

function showAddWindow(comicvine_id) {
	var volume_data = document.querySelector(`button[data-comicvine_id="${comicvine_id}"]`).dataset;

	document.querySelector('#add-title').innerText = volume_data.title;
	document.querySelector('#add-cover').src = volume_data.cover;
	document.querySelector('#comicvine-input').value = comicvine_id;
	
	showWindow("add-window");
};

function addVolume() {
	showLoadWindow("add-window");
	const comicvine_id = document.querySelector('#comicvine-input').value;
	const root_folder_id = document.querySelector('#rootfolder-input').value;
	const monitor_value = document.querySelector('#monitor-input').value;
	usingApiKey()
	.then(api_key => {
		fetch(`/api/volumes?api_key=${api_key}&comicvine_id=${comicvine_id}&monitor=${monitor_value}&root_folder_id=${root_folder_id}`, {
			'method': 'POST'
		})
		.then(response => {
			if (!response.ok) return Promise.reject(response.status);
			else return response.json();
		})
		.then(json => window.location.href = `/volumes/${json.result.id}`)
		.catch(e => {
			if (e === 401) window.location.href = `/login?redirect=${window.location.pathname}`;
			else if (e === 509) document.querySelector('#add-volume').innerText = 'ComicVine API rate limit reached';
			else {
				console.log(e);
			};
		});
	});
};

// code run on load
addEventListener('#search-cancel-button', 'click', clearSearch);
setAttribute('#add-form', 'action', 'javascript:addVolume()');

usingApiKey()
.then(api_key => {
	fillRootFolderInput(api_key);
	addEventListener('#search-button', 'click', e => search(api_key));
	addEventListener('#search-input', 'keydown', e => e.code === 'Enter' ? search(api_key) : null);
});
