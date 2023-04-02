function buildVault(volumes) {
	const table = document.getElementById('vault');
	table.innerHTML = '';
	for (i=0; i<volumes.length; i++) {
		const obj = volumes[i];
		
		const entry = document.createElement("a");
		entry.classList.add('vault-entry');
		entry.href = `/volumes/${obj.id}`;

		const cover = document.createElement("img");
		cover.src = `${obj.cover}?api_key=${api_key}`;
		cover.alt = "";
		cover.loading = "lazy";
		cover.classList.add('entry-cover');
		entry.appendChild(cover);
		
		const title = document.createElement("h2");
		title.innerText = obj.title;
		title.classList.add('entry-title');
		entry.appendChild(title);

		if (obj.volume_number !== null) {
			const volume_number = document.createElement("p");
			volume_number.innerText = `Volume ${obj.volume_number}`;
			volume_number.classList.add('entry-volume-number');
			entry.append(volume_number);
		};

		const monitored = document.createElement("p");
		monitored.innerText = obj.monitored ? 'Monitored' : 'Unmonitored';
		monitored.classList.add('entry-monitored');
		entry.appendChild(monitored);
		
		table.appendChild(entry);
	};
};

function searchVault() {
	const query = document.getElementById('search-input').value;
	fetch(`/api/volumes?api_key=${api_key}&query=${query}`)
	.then(response => {
		return response.json();
	})
	.then(json => {
		buildVault(json.result);
	});
};

function searchVaultShortcut(e) {
	if (e.key === 'Enter') {
		searchVault();
	};
};

function updateAll() {
	const el = document.querySelector('#update-button > img');
	el.src = '/static/img/loading_white.svg';
	el.classList.add('spinning');
	fetch(`/api/system/tasks?api_key=${api_key}&cmd=update_all`, {
		'method': 'POST'
	});
};

function searchAll() {
	const el = document.querySelector('#searchall-button > img');
	el.src = '/static/img/loading_white.svg';
	el.classList.add('spinning');
	fetch(`/api/system/tasks?api_key=${api_key}&cmd=search_all`, {
		'method': 'POST'
	});
}

function fillVault(sort="title") {
	fetch(`/api/volumes?api_key=${api_key}&sort=${sort}`)
	.then(response => {
		return response.json();
	})
	.then(json => {
		const volumes = json.result;
		buildVault(volumes);
	});
}

function clearSearch() {
	document.getElementById('search-input').value = '';
	fillVault();
};

function sortVault() {
	const order = document.getElementById('sort-button').value;
	fillVault(order);
}

function toggleSearch() {
	document.getElementById('search-bar').classList.toggle('show-search-bar');
}

// code run on load
const api_key = sessionStorage.getItem('api_key');

fillVault();

document.getElementById('clear-search-button').addEventListener('click', e => clearSearch());
document.getElementById('search-button').addEventListener('click', e => searchVault());
document.getElementById('search-input').addEventListener('keydown', e => searchVaultShortcut(e));
document.getElementById('update-button').addEventListener('click', e => updateAll());
document.getElementById('searchall-button').addEventListener('click', e => searchAll());
document.getElementById('sort-button').addEventListener('change', e => sortVault());
document.getElementById('search-toggle-button').addEventListener('click', e => toggleSearch());
