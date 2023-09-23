function loadProposal(api_key) {
	const table = document.querySelector('.proposal-list');
	table.innerHTML = '';
	fetch(`${url_base}/api/libraryimport?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		json.result.forEach(result => {
			const entry = document.createElement('tr');
			entry.dataset.cv_id = result.cv.id || '';

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
			change_match.addEventListener('click', e => editCVMatch(result.filepath));
			actions.appendChild(change_match);

			const remove_row = document.createElement('button');
			remove_row.title = 'Remove entry';
			const remove_row_icon = document.createElement('img');
			remove_row_icon.src = '/static/img/delete.svg';
			remove_row_icon.alt = '';
			remove_row.appendChild(remove_row_icon);
			remove_row.addEventListener('click', e => entry.remove());
			actions.appendChild(remove_row);

			entry.appendChild(actions);
			
			table.appendChild(entry);
		});

		document.querySelector('.table-container').classList.remove('hidden');
		document.querySelector('#run-button').innerText = 'Run';
		document.querySelector('#import-button').classList.remove('hidden');
	});
};

function editCVMatch(filepath) {
	document.querySelector('#cv-window').dataset.filepath = filepath;
	document.querySelector('#search-input').value = '';
	document.querySelector('.search-results').innerHTML = '';
	document.querySelector('.search-results-container').classList.add('hidden');
	showWindow('cv-window');
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
					const td = document.querySelector(`td[title="${document.querySelector('#cv-window').dataset.filepath}"]`);

					td.parentNode.dataset.cv_id = result.comicvine_id;

					const link = td.nextSibling.firstChild;
					link.href = result.comicvine_info;
					link.innerText = `${result.title} (${result.year})`;
					
					closeWindow();
				});
				select.appendChild(select_button);
				entry.appendChild(select);

				table.appendChild(entry);
			});
			document.querySelector('.search-results-container').classList.remove('hidden');
		});
	});
};

function importLibrary(api_key) {
	const import_button = document.querySelector('#import-button');
	const data = [...document.querySelectorAll('.proposal-list > tr:not([data-cv_id=""])')]
		.map(e => { return {
			'filepath': e.querySelector('td').title,
			'id': parseInt(e.dataset.cv_id)
		} });
	
	import_button.innerText = 'Importing';
	fetch(`${url_base}/api/libraryimport?api_key=${api_key}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(data)
	})
	.then(response => {
		import_button.innerText = 'Import';
		import_button.classList.add('hidden');
		document.querySelector('.table-container').classList.add('hidden');
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	addEventListener('#run-button', 'click', e => {
		e.target.innerText = 'Running';
		loadProposal(api_key);
	});
	addEventListener('#refresh-button', 'click', e => loadProposal(api_key));
	addEventListener('#import-button', 'click', e => importLibrary(api_key));
	setAttribute('.search-bar', 'action', 'javascript:searchCV();');
});
