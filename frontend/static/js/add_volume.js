function buildResults(results) {
	const table = document.getElementById('search-results');
	table.innerHTML = '';
	for (i=0; i<results.length; i++) {
		const obj = results[i];
		
		const entry = document.createElement('button');
		entry.classList.add('search-entry');
		entry.dataset.title = `${obj.title} (${obj.year})`;
		entry.dataset.cover = obj.cover;

		entry.id = obj.comicvine_id;
		entry.addEventListener('click', e => {
			fillAddWindow(obj.comicvine_id);
			showWindow("add-window");
		});

		const cover_info_container = document.createElement('div');
		cover_info_container.classList.add('cover-info-container');
		entry.appendChild(cover_info_container);

		const cover = document.createElement('img');
		cover.classList.add('entry-cover');
		cover.src = obj.cover;
		cover_info_container.appendChild(cover);

		const info_container = document.createElement('div');
		info_container.classList.add('entry-info-container');
		cover_info_container.appendChild(info_container);
		
		const title = document.createElement("h2");
		title.classList.add('entry-title');
		title.innerText = entry.dataset.title;
		info_container.appendChild(title);
		
		const tags = document.createElement('div');
		tags.classList.add('entry-tags');
		info_container.appendChild(tags);

		if (obj.volume_number !== null) {
			const volume_number = document.createElement('p');
			volume_number.classList.add('entry-tag');
			volume_number.innerText = `Volume ${obj.volume_number}`;
			tags.appendChild(volume_number);
		}

		const publisher = document.createElement('p');
		publisher.classList.add('entry-tag');
		publisher.innerText = obj.publisher;
		tags.appendChild(publisher);

		const issue_count = document.createElement('p');
		issue_count.classList.add('entry-tag');
		issue_count.innerText = `${obj.issue_count} issues`;
		tags.appendChild(issue_count);

		const info_link = document.createElement('a');
		info_link.classList.add('entry-tag');
		info_link.href = obj.comicvine_info;
		info_link.innerText = 'Link';
		tags.appendChild(info_link);

		if (obj.aliases.length > 0) {
			const aliases = document.createElement('div');
			aliases.classList.add('entry-aliases');
			info_container.appendChild(aliases);
			
			for (j=0; j<obj.aliases.length; j++) {
				const alias = document.createElement('p');
				alias.innerText = obj.aliases[j];
				alias.classList.add('entry-alias');
				aliases.appendChild(alias);
			}
		}
		
		const description = document.createElement('div');
		description.classList.add('entry-description', 'description');
		description.innerHTML = obj.description;
		info_container.appendChild(description);

		const spare_description = document.createElement('div');
		spare_description.classList.add('entry-spare-description', 'description');
		spare_description.innerHTML = obj.description;
		entry.appendChild(spare_description);

		table.appendChild(entry);
	};
	if (table.innerHTML === '') {
		document.getElementById('search-empty').classList.remove('hidden');
	};
};

function search() {
	document.getElementById('search-explain').classList.add('hidden');
	document.getElementById('search-empty').classList.add('hidden');
	document.getElementById('search-failed').classList.add('hidden');
	document.getElementById('search-input').blur();

	const query = document.getElementById('search-input').value;
	fetch(`/api/volumes/search?api_key=${api_key}&query=${query}`)
	.then(response => {
		// catch errors
		if (!response.ok) {
			return Promise.reject(response.status);
		};

		return response.json();
	})
	.then(json => {
		const results = json.result;
		buildResults(results);
	})
	.catch(e => {
		if (e === 400) {
			document.getElementById('search-failed').classList.remove('hidden');
		};
	});
};

function clearSearch() {
	document.getElementById('search-results').innerHTML = '';
	document.getElementById('search-empty').classList.add('hidden');
	document.getElementById('search-failed').classList.add('hidden');
	document.getElementById('search-explain').classList.remove('hidden');
	document.getElementById('search-input').value = '';
};

function searchShortcut(e) {
	if (e.key === 'Enter') {
		search();
	};
};

function fillAddWindow(comicvine_id) {
	var el = document.getElementById(comicvine_id).dataset;

	document.getElementById('add-title').innerText = el.title;
	document.getElementById('add-cover').src = el.cover;
	document.getElementById('comicvine-input').value = comicvine_id;
	return;
}

function addVolume() {
	showWindow("adding-window");
	const comicvine_id = document.getElementById('comicvine-input').value;
	const root_folder_id = document.getElementById('rootfolder-input').value;
	const monitor_value = document.getElementById('monitor-input').value;
	fetch(`/api/volumes?api_key=${api_key}&comicvine_id=${comicvine_id}&monitor=${monitor_value}&root_folder_id=${root_folder_id}`, {
		'method': 'POST'
	})
	.then(response => {
		return response.json();
	})
	.then(json => {
		window.location.href = `/volumes/${json.result.id}`;
	})
}

// code run on load
const api_key = sessionStorage.getItem('api_key');

document.getElementById('search-button').addEventListener('click', e => search());
document.getElementById('search-input').addEventListener('keydown', e => searchShortcut(e));
document.getElementById('search-cancel-button').addEventListener('click', e => clearSearch());
document.getElementById('add-form').setAttribute('action', 'javascript:addVolume()');

const root_folder_list = document.getElementById('rootfolder-input');
fetch(`/api/rootfolder?api_key=${api_key}`)
.then(response => {
	return response.json();
})
.then(json => {
	for (i=0; i<json.result.length; i++) {
		const folder = json.result[i];
		const option = document.createElement('option');
		option.value = folder.id;
		option.innerText = folder.folder;
		root_folder_list.appendChild(option);
	}
})