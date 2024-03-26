const LIEls = {
	pre_build: {
		li_result: document.querySelector('.pre-build-els .li-result')
	},
	views: {
		start: document.querySelector('#start-window'),
		no_result: document.querySelector('#no-result-window'),
		list: document.querySelector('#list-window'),
		loading: document.querySelector('#loading-window'),
		no_cv: document.querySelector('#no-cv-window')
	},
	proposal_list: document.querySelector('.proposal-list'),
	select_all: document.querySelector('#selectall-input'),
	search: {
		window: document.querySelector('#cv-window'),
		input: document.querySelector('#search-input'),
		results: document.querySelector('.search-results'),
		container: document.querySelector('.search-results-container'),
		bar: document.querySelector('.search-bar')
	},
	buttons: {
		cancel: document.querySelector('.cancel-button'),
		run: document.querySelector('#run-import-button'),
		import: document.querySelector('#import-button'),
		import_rename: document.querySelector('#import-rename-button')
	}
};

function loadProposal(api_key) {
	hide([LIEls.views.start], [LIEls.views.loading]);

	const params = {
		limit: parseInt(document.querySelector('#limit-input').value),
		limit_parent_folder: document.querySelector('#folder-input').value,
		only_english: document.querySelector('#lang-input').value
	};
	LIEls.proposal_list.innerHTML = '';
	LIEls.select_all.checked = true;

	fetchAPI('/libraryimport', api_key, params)
	.then(json => {
		json.result.forEach(result => {
			const entry = LIEls.pre_build.li_result.cloneNode(true);
			entry.dataset.cv_id = result.cv.id || '';
			entry.dataset.group_number = result.group_number;
			entry.dataset.filepath = encodeURIComponent(result.filepath);

			const title = entry.querySelector('.file-column');
			title.innerText = result.file_title;
			title.title = result.filepath;

			const CV_link = entry.querySelector('a');
			CV_link.href = result.cv.link || '';
			CV_link.innerText = result.cv.title || '';

			entry.querySelector('.issue-count').innerText = result.cv.issue_count;

			entry.querySelector('button').onclick = e => openEditCVMatch(result.filepath);

			LIEls.proposal_list.appendChild(entry);
		});

		if (json.result.length > 0)
			hide([LIEls.views.loading], [LIEls.views.list]);
		else
			hide([LIEls.views.loading], [LIEls.views.no_result]);
	})
	.catch(e => {
		if (e.status === 400)
			hide([LIEls.views.loading], [LIEls.views.no_cv]);
		else
			console.log(e);
	});
};

function toggleSelectAll() {
	const checked = LIEls.select_all.checked;
	LIEls.proposal_list.querySelectorAll('input[type="checkbox"]').forEach(
		e => e.checked = checked
	);
};

function openEditCVMatch(filepath) {
	LIEls.search.window.dataset.filepath =
		encodeURIComponent(filepath);
	LIEls.search.results.innerHTML = '';
	hide([LIEls.search.container]);
	LIEls.search.input.value = '';
	showWindow('cv-window');
	LIEls.search.input.focus();
};

function editCVMatch(
	filepath,
	comicvine_id,
	comicvine_info,
	title,
	year,
	issue_count,
	group_number=null
) {
	let target_td;
	if (group_number === null)
		target_td = document.querySelectorAll(`tr[data-filepath="${filepath}"]`);
	else
		target_td = document.querySelectorAll(`tr[data-group_number="${group_number}"]`);

	target_td.forEach(tr => {
		tr.dataset.cv_id = comicvine_id;
		const link = tr.querySelector('a');
		link.href = comicvine_info;
		link.innerText = `${title} (${year})`;
		tr.querySelector('.issue-count').innerText = issue_count;
	});
};

function searchCV() {
	const input = LIEls.search.input;
	input.blur();
	usingApiKey()
	.then(api_key => {
		LIEls.search.results.innerHTML = '';
		fetchAPI('/volumes/search', api_key, {query: input.value})
		.then(json => {
			json.result.forEach(result => {
				const entry = document.createElement('tr');

				const title = document.createElement('td');
				const title_link = document.createElement('a');
				title_link.target = '_blank';
				title_link.href = result.comicvine_info;
				title_link.innerText = `${result.title} (${result.year})`;
				title.appendChild(title_link);
				entry.appendChild(title);

				const issue_count = document.createElement('td');
				issue_count.innerText = result.issue_count;
				entry.appendChild(issue_count);

				const select = document.createElement('td');
				const select_button = document.createElement('button');
				select_button.innerText = 'Select';
				select_button.addEventListener('click', e => {
					editCVMatch(
						document.querySelector('#cv-window').dataset.filepath,
						result.comicvine_id,
						result.comicvine_info,
						result.title,
						result.year,
						result.issue_count
					);
					closeWindow();
				});
				select.appendChild(select_button);
				entry.appendChild(select);

				const select_for_all = document.createElement('td');
				const select_for_all_button = document.createElement('button');
				select_for_all_button.innerText = 'Select for group';
				select_for_all_button.addEventListener('click', e => {
					const filepath = LIEls.search.window.dataset.filepath;
					const group_number = document.querySelector(`tr[data-filepath="${filepath}"]`)
						.dataset.group_number;
					editCVMatch(
						filepath,
						result.comicvine_id,
						result.comicvine_info,
						result.title,
						result.year,
						result.issue_count,
						group_number
					);
					closeWindow();
				});
				select_for_all.appendChild(select_for_all_button);
				entry.appendChild(select_for_all);

				LIEls.search.results.appendChild(entry);
			});
			hide([], [LIEls.search.container]);
		});
	});
};

function importLibrary(api_key, rename=false) {
	const data = [...LIEls.proposal_list.querySelectorAll(
		'tr:not([data-cv_id=""]) input[type="checkbox"]:checked'
	)].map(e => { return {
		'filepath': e.parentNode.nextSibling.nextSibling.title,
		'id': parseInt(e.parentNode.parentNode.dataset.cv_id)
	} });

	hide([LIEls.views.list], [LIEls.views.loading]);
	sendAPI('POST', '/libraryimport', api_key, {rename_files: rename}, data)
	.then(response => hide([LIEls.views.loading], [LIEls.views.start]));
};

// code run on load

usingApiKey()
.then(api_key => {
	LIEls.buttons.run.onclick = e => loadProposal(api_key);
	LIEls.buttons.import.onclick = e => importLibrary(api_key, false);
	LIEls.buttons.import_rename.onclick = e => importLibrary(api_key, true);
});

LIEls.search.bar.action = 'javascript:searchCV();';
LIEls.select_all.onchange = e => toggleSelectAll();
LIEls.buttons.cancel.onclick = e => hide(
	[LIEls.views.list, LIEls.views.no_result, LIEls.views.no_cv],
	[LIEls.views.start]
);
