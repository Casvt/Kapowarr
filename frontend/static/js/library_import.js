const windows = {
	start: document.querySelector('#start-window'),
	no_result: document.querySelector('#no-result-window'),
	list: document.querySelector('#list-window'),
	loading: document.querySelector('#loading-window')
};

function loadProposal(api_key) {
	windows.start.classList.add('hidden');
	windows.loading.classList.remove('hidden');
	const limit = parseInt(document.querySelector('#limit-input').value);
	const table = document.querySelector('.proposal-list');
	table.innerHTML = '';
	fetch(`${url_base}/api/libraryimport?api_key=${api_key}&limit=${limit}`)
	.then(response => response.json())
	.then(json => {
		json.result.forEach(result => {
			const entry = document.createElement('tr');
			entry.dataset.cv_id = result.cv.id || '';
			entry.dataset.group_number = result.group_number;
			entry.dataset.filepath = encodeURIComponent(result.filepath);
			
			const select = document.createElement('td');
			const select_button = document.createElement('input');
			select_button.type = 'checkbox';
			select_button.checked = true;
			select.appendChild(select_button);
			entry.appendChild(select);

			const title = document.createElement('td');
			title.innerText = result.file_title;
			title.title = result.filepath;
			entry.appendChild(title);

			const CV_match = document.createElement('td');
			const CV_link = document.createElement('a');
			CV_link.href = result.cv.link || '';
			CV_link.innerText = result.cv.title || '';
			CV_link.target = '_blank';
			CV_match.appendChild(CV_link);
			entry.appendChild(CV_match);

			const actions = document.createElement('td');

			const change_match = document.createElement('button');
			change_match.title = 'Change match';
			const change_match_icon = document.createElement('img');
			change_match_icon.src = '/static/img/edit.svg';
			change_match_icon.alt = '';
			change_match.appendChild(change_match_icon);
			change_match.addEventListener('click', e => openEditCVMatch(result.filepath));
			actions.appendChild(change_match);

			entry.appendChild(actions);
			
			table.appendChild(entry);
		});

		windows.loading.classList.add('hidden');
		if (json.result.length > 0)
			windows.list.classList.remove('hidden');
		else
			windows.no_result.classList.remove('hidden');
	});
};

function toggleSelectAll() {
	const checked = document.querySelector('#selectall-input').checked;
	document.querySelectorAll('.proposal-list input[type="checkbox"]').forEach(
		e => e.checked = checked
	);
};

function openEditCVMatch(filepath) {
	document.querySelector('#cv-window').dataset.filepath =
		encodeURIComponent(filepath);
	document.querySelector('#search-input').value = '';
	document.querySelector('.search-results').innerHTML = '';
	document.querySelector('.search-results-container').classList.add('hidden');
	showWindow('cv-window');
	document.querySelector('#search-input').focus();
};

function editCVMatch(
	filepath,
	comicvine_id,
	comicvine_info,
	title,
	year,
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
	});
};

function searchCV() {
	const input = document.querySelector('#search-input');
	input.blur();
	usingApiKey()
	.then(api_key => {
		const table = document.querySelector('.search-results');
		table.innerHTML = '';
		const query = input.value;
		fetch(`${url_base}/api/volumes/search?api_key=${api_key}&query=${query}`)
		.then(response => response.json())
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

				const select = document.createElement('td');
				const select_button = document.createElement('button');
				select_button.innerText = 'Select';
				select_button.addEventListener('click', e => {
					editCVMatch(
						document.querySelector('#cv-window').dataset.filepath,
						result.comicvine_id,
						result.comicvine_info,
						result.title,
						result.year
					);
					closeWindow();
				});
				select.appendChild(select_button);
				entry.appendChild(select);

				const select_for_all = document.createElement('td');
				const select_for_all_button = document.createElement('button');
				select_for_all_button.innerText = 'Select for group';
				select_for_all_button.addEventListener('click', e => {
					const filepath = document.querySelector('#cv-window')
						.dataset.filepath;
					const group_number = document.querySelector(`tr[data-filepath="${filepath}"]`)
						.dataset.group_number;
					editCVMatch(
						filepath,
						result.comicvine_id,
						result.comicvine_info,
						result.title,
						result.year,
						group_number
					);
					closeWindow();
				});
				select_for_all.appendChild(select_for_all_button);
				entry.appendChild(select_for_all);

				table.appendChild(entry);
			});
			document.querySelector('.search-results-container').classList.remove('hidden');
		});
	});
};

function importLibrary(api_key, rename=false) {
	const data = [...document.querySelectorAll(
		'.proposal-list > tr:not([data-cv_id=""]) input[type="checkbox"]:checked'
	)].map(e => { return {
		'filepath': e.parentNode.nextSibling.title,
		'id': parseInt(e.parentNode.parentNode.dataset.cv_id)
	} });

	windows.list.classList.add('hidden');
	windows.loading.classList.remove('hidden');
	fetch(`${url_base}/api/libraryimport?api_key=${api_key}&rename_files=${rename}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(data)
	})
	.then(response => {
		windows.loading.classList.add('hidden');
		windows.start.classList.remove('hidden');
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	addEventListener('#run-import-button', 'click', e => loadProposal(api_key));
	addEventListener('#import-button', 'click', e => importLibrary(api_key, false));
	addEventListener('#import-rename-button', 'click', e => importLibrary(api_key, true));
});

setAttribute('.search-bar', 'action', 'javascript:searchCV();');
addEventListener('#selectall-input', 'change', e => toggleSelectAll());
addEventListener('.cancel-button', 'click', e => {
	windows.list.classList.add('hidden');
	windows.no_result.classList.add('hidden');
	windows.start.classList.remove('hidden');
});
