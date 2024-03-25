const SearchEls = {
	pre_build: {
		search_entry: document.querySelector('.pre-build-els .search-entry')
	},
	search_bar: {
		bar: document.querySelector('.search-bar'),
		cancel: document.querySelector('#search-cancel-button'),
		input: document.querySelector('#search-input')
	},
	search_results: document.querySelector('#search-results'),
	msgs: {
		blocked: document.querySelector('#search-blocked'),
		failed: document.querySelector('#search-failed'),
		empty: document.querySelector('#search-empty'),
		explain: document.querySelector('#search-explain')
	},
	filters: {
		translations: document.querySelector('#filter-translations')
	},
	window: {
		form: document.querySelector('#add-form'),
		title: document.querySelector('#add-window h2'),
		cover: document.querySelector('#add-cover'),
		cv_input: document.querySelector('#comicvine-input'),
		monitor_input: document.querySelector('#monitor-input'),
		root_folder_input: document.querySelector('#rootfolder-input'),
		volume_folder_input: document.querySelector('#volumefolder-input'),
		submit: document.querySelector('#add-volume')
	}
};

//
// Searching
//
function addAlreadyAdded(title) {
	const aa_icon = document.createElement('img');
	aa_icon.src = `${url_base}/static/img/check_circle.svg`;
	aa_icon.alt = 'Volume is already added';
	title.appendChild(aa_icon);
}

function buildResults(results, api_key) {
	SearchEls.search_results.querySelectorAll('button:not(.filter-bar)').forEach(e => e.remove());
	results.forEach(result => {
		const entry = SearchEls.pre_build.search_entry.cloneNode(true);
		entry.dataset.title = result.year !== null ? `${result.title} (${result.year})` : result.title;
		entry.dataset.cover = result.cover;
		entry.dataset.comicvine_id = result.comicvine_id;
		entry.dataset._translated = result.translated;
		entry.dataset._title = result.title;
		entry.dataset._year = result.year;
		entry.dataset._volume_number = result.volume_number;
		entry.dataset._publisher = result.publisher;

		// Only allow adding volume if it isn't already added
		if (!result.already_added)
			entry.onclick = e => showAddWindow(result.comicvine_id, api_key);

		entry.querySelector('img').src = result.cover;

		const title = entry.querySelector('h2');
		title.innerText = result.title;

		if (result.year !== null) {
			const year = document.createElement("span");
			year.innerText = ` (${result.year})`;
			title.appendChild(year);
		};

		if (result.already_added)
			addAlreadyAdded(title);

		const tags = entry.querySelector('.entry-tags');

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
		info_link.onclick = e => e.stopImmediatePropagation();
		tags.appendChild(info_link);

		if (result.aliases.length) {
			const aliases = entry.querySelector('.entry-aliases');
			result.aliases.forEach(alias_text => {
				const alias = document.createElement('p');
				alias.innerText = alias_text;
				aliases.appendChild(alias);
			});
		};

		entry.querySelectorAll('.entry-description, .entry-spare-description').forEach(
			d => d.innerHTML = result.description
		);

		SearchEls.search_results.appendChild(entry);
	});

	applyTranslationFilter();
};

function search() {
	if (!SearchEls.msgs.blocked.classList.contains('hidden'))
	return;

	SearchEls.search_bar.input.blur();

	hide([
		SearchEls.msgs.empty,
		SearchEls.msgs.explain,
		SearchEls.msgs.failed,
		SearchEls.search_results
	]);
	usingApiKey().then(api_key => {
		const query = SearchEls.search_bar.input.value;
		fetchAPI('/volumes/search', api_key, {query: query})
		.then(json => {

			buildResults(json.result, api_key);

			if (!SearchEls.search_results.querySelector('button:not(.filter-bar)'))
				hide([], [SearchEls.msgs.empty]);
			else
				hide([], [SearchEls.search_results]);
		})
		.catch(e => {
			if (e.status === 400)
				hide([], [SearchEls.msgs.failed]);
			else
				console.log(e);
		});
	});
};

function clearSearch(e) {
	hide([
		SearchEls.search_results,
		SearchEls.msgs.empty,
		SearchEls.msgs.failed
	], [
		SearchEls.msgs.explain
	])
	SearchEls.search_results.querySelectorAll('button:not(.filter-bar)').forEach(e => e.remove());
	SearchEls.search_bar.input.value = '';
};

function applyTranslationFilter() {
	const value = SearchEls.filters.translations.value;
	setLocalStorage({'translated_filter': value});
	const els = [...SearchEls.search_results.querySelectorAll(
		'button[data-_translated="true"]'
	)]
	if (value === 'all')
		hide([], els);
	else if (value == 'only-english')
		hide(els);
};

//
// Adding
//
function fillRootFolderInput(api_key) {
	fetchAPI('/rootfolder', api_key)
	.then(json => {
		if (json.result.length)
			json.result.forEach(folder => {
				const option = document.createElement('option');
				option.value = folder.id;
				option.innerText = folder.folder;
				SearchEls.window.root_folder_input.appendChild(option);
			});
		else
			hide([], [SearchEls.msgs.blocked]);
	});
};

function showAddWindow(comicvine_id, api_key) {
	const volume_data = document.querySelector(
		`button[data-comicvine_id="${comicvine_id}"]`
	).dataset;
	const body = {
		'comicvine_id': volume_data.comicvine_id,
		'title': volume_data._title,
		'year': volume_data._year,
		'volume_number': volume_data._volume_number,
		'publisher': volume_data._publisher
	};

	sendAPI('POST', '/volumes/search', api_key, {}, body)
	.then(response => response.json())
	.then(json => {
		volume_data._volume_folder = json.result.folder;
		SearchEls.window.volume_folder_input.value = json.result.folder;
		showWindow("add-window");
	});

	SearchEls.window.title.innerText = volume_data.title;
	SearchEls.window.cover.src = volume_data.cover;
	SearchEls.window.cv_input.value = comicvine_id;
};

function addVolume() {
	showLoadWindow("add-window");
	const volume_folder = SearchEls.window.volume_folder_input.value;

	const data = {
		'comicvine_id': SearchEls.window.cv_input.value,
		'root_folder_id': parseInt(SearchEls.window.root_folder_input.value),
		'monitor': SearchEls.window.monitor_input.value == 'true',
		'volume_folder': ''
	};
	if (
		volume_folder !== ''
		&& volume_folder !== document.querySelector(
			`button[data-comicvine_id="${data.comicvine_id}"]`
		).dataset._volume_folder
	) {
		// Custom volume folder
		data.volume_folder = volume_folder;
	};

	usingApiKey()
	.then(api_key => {
		sendAPI('POST', '/volumes', api_key, {}, data)
		.then(response => {
			const title = document.querySelector(
				`button[data-comicvine_id="${data.comicvine_id}"] h2`
			);
			addAlreadyAdded(title);
			closeWindow();
		})
		.catch(e => {
			if (e.status === 509)
				SearchEls.window.submit.innerText = 'ComicVine API rate limit reached';
			else
				console.log(e);
		});
	});
};

// code run on load
usingApiKey()
.then(api_key => fillRootFolderInput(api_key));

SearchEls.search_bar.cancel.onclick = clearSearch;
SearchEls.window.form.action = 'javascript:addVolume();';
SearchEls.search_bar.bar.action = 'javascript:search();';
SearchEls.filters.translations.onchange = e => applyTranslationFilter();

const translated_filter = getLocalStorage('translated_filter')['translated_filter'];
SearchEls.filters.translations.querySelector(`option[value="${translated_filter}"]`).setAttribute('selected', '');
