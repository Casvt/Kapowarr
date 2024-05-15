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
		explain: document.querySelector('#search-explain'),
		loading: document.querySelector('#search-loading')
	},
	filters: {
		translations: document.querySelector('#filter-translations'),
		publisher: document.querySelector('#filter-publisher'),
		volume_number: document.querySelector('#filter-volume-number'),
		year: document.querySelector('#filter-year'),
		issue_count: document.querySelector('#filter-issue-count')
	},
	window: {
		form: document.querySelector('#add-form'),
		title: document.querySelector('#add-window h2'),
		cover: document.querySelector('#add-cover'),
		cv_input: document.querySelector('#comicvine-input'),
		monitor_input: document.querySelector('#monitor-input'),
		root_folder_input: document.querySelector('#rootfolder-input'),
		volume_folder_input: document.querySelector('#volumefolder-input'),
		auto_search_input: document.querySelector('#auto-search-input'),
		submit: document.querySelector('#add-volume')
	}
};

//
// Searching
//
function addAlreadyAdded(entry, id) {
	entry.onclick = e => window.location.href = `${url_base}/volumes/${id}`;

	const title = entry.querySelector('h2');
	const aa_icon = document.createElement('img');
	aa_icon.src = `${url_base}/static/img/check_circle.svg`;
	aa_icon.alt = 'Volume is already added';
	title.appendChild(aa_icon);
};

function buildResults(results, api_key) {
	SearchEls.search_results.querySelectorAll('button:not(.filter-bar)').forEach(e => e.remove());
	results.forEach(result => {
		const entry = SearchEls.pre_build.search_entry.cloneNode(true);
		entry.dataset.title =
		entry.ariaLabel =
			result.year !== null ? `${result.title} (${result.year})` : result.title;
		entry.dataset.cover = result.cover;
		entry.dataset.comicvine_id = result.comicvine_id;
		entry.dataset._translated = result.translated;
		entry.dataset._title = result.title;
		entry.dataset._year = result.year;
		entry.dataset._volume_number = result.volume_number;
		entry.dataset._publisher = result.publisher;
		entry.dataset._issue_count = result.issue_count;

		// Only allow adding volume if it isn't already added
		if (result.already_added === null)
			entry.onclick = e => showAddWindow(result.comicvine_id, api_key);

		entry.querySelector('img').src = result.cover;

		const title = entry.querySelector('h2');
		title.innerText = result.title;

		if (result.year !== null) {
			const year = document.createElement("span");
			year.innerText = ` (${result.year})`;
			title.appendChild(year);
		};

		if (result.already_added !== null)
			addAlreadyAdded(entry, result.already_added);

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

	// Fill filters
	const years = new Set(results.map(r => r.year).sort());
	SearchEls.filters.year.innerHTML = '';
	const all_years_option = document.createElement('option');
	all_years_option.value = '';
	all_years_option.innerText = 'All Years';
	all_years_option.selected = true;
	SearchEls.filters.year.appendChild(all_years_option);

	years.forEach(y => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = y;
		SearchEls.filters.year.appendChild(entry);
	});

	const issue_counts = new Set(results.map(r => r.issue_count).sort((a, b) => a - b));
	SearchEls.filters.issue_count.innerHTML = '';
	const all_issue_counts_option = document.createElement('option');
	all_issue_counts_option.value = '';
	all_issue_counts_option.innerText = 'All Issue Counts';
	all_issue_counts_option.selected = true;
	SearchEls.filters.issue_count.appendChild(all_issue_counts_option);

	issue_counts.forEach(ic => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = `${ic} issues`;
		SearchEls.filters.issue_count.appendChild(entry);
	});

	const volume_numbers = new Set(results.map(r => r.volume_number).sort((a, b) => a - b));
	SearchEls.filters.volume_number.innerHTML = '';
	const all_volume_numbers_option = document.createElement('option');
	all_volume_numbers_option.value = '';
	all_volume_numbers_option.innerText = 'All Volume Numbers';
	all_volume_numbers_option.selected = true;
	SearchEls.filters.volume_number.appendChild(all_volume_numbers_option);

	volume_numbers.forEach(vn => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = `Volume ${vn}`;
		SearchEls.filters.volume_number.appendChild(entry);
	});

	const publishers = new Set(results.map(r => r.publisher).sort());
	SearchEls.filters.publisher.innerHTML = '';
	const all_publishers_option = document.createElement('option');
	all_publishers_option.value = '';
	all_publishers_option.innerText = 'All Publishers';
	all_publishers_option.selected = true;
	SearchEls.filters.publisher.appendChild(all_publishers_option);

	publishers.forEach(pub => {
		const entry = document.createElement('option');
		entry.value = entry.innerText = pub;
		SearchEls.filters.publisher.appendChild(entry);
	});

	applyFilters();
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
	], [
		SearchEls.msgs.loading
	]);
	usingApiKey().then(api_key => {
		const query = SearchEls.search_bar.input.value;
		fetchAPI('/volumes/search', api_key, {query: query})
		.then(json => {

			buildResults(json.result, api_key);

			if (!SearchEls.search_results.querySelector('button:not(.filter-bar)'))
				hide([SearchEls.msgs.loading], [SearchEls.msgs.empty]);
			else
				hide([SearchEls.msgs.loading], [SearchEls.search_results]);
		})
		.catch(e => {
			if (e.status === 400)
				hide([SearchEls.msgs.loading], [SearchEls.msgs.failed]);
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

function applyFilters() {
	const translation = SearchEls.filters.translations.value,
		year = SearchEls.filters.year.value,
		issue_count = (
			SearchEls.filters.issue_count.value || ' issues'
		).split(' issues')[0],
		volume_number = (
			SearchEls.filters.volume_number.value || 'Volume '
			).split('Volume ')[1],
		publisher = SearchEls.filters.publisher.value;

	setLocalStorage({'translated_filter': translation});

	let filter = '';

	if (translation === 'only-english')
		filter += '[data-_translated="false"]';
	if (year !== '')
		filter += `[data-_year="${year}"]`;
	if (issue_count !== '')
		filter += `[data-_issue_count="${issue_count}"]`;
	if (volume_number !== '')
		filter += `[data-_volume_number="${volume_number}"]`;
	if (publisher !== '')
		filter += `[data-_publisher="${publisher}"]`;

	if (filter === '')
		hide([], SearchEls.search_results.querySelectorAll('button'));
	else
		hide(
			SearchEls.search_results.querySelectorAll('button'),
			SearchEls.search_results.querySelectorAll(`button${filter}`)
		);
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
		'volume_folder': '',
		'auto_search': SearchEls.window.auto_search_input.checked
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
		.then(response => response.json())
		.then(json => {
			const entry = document.querySelector(
				`button[data-comicvine_id="${data.comicvine_id}"]`
			);
			addAlreadyAdded(entry, json.result.id);
			closeWindow();
		})
		.catch(e => {
			if (e.status === 509) {
				SearchEls.window.submit.innerText = 'ComicVine API rate limit reached';
				showWindow("add-window");
			} else
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

SearchEls.filters.translations.onchange =
SearchEls.filters.publisher.onchange =
SearchEls.filters.volume_number.onchange =
SearchEls.filters.year.onchange =
SearchEls.filters.issue_count.onchange =
	e => applyFilters();

const translated_filter = getLocalStorage('translated_filter')['translated_filter'];
SearchEls.filters.translations.querySelector(`option[value="${translated_filter}"]`).setAttribute('selected', '');
