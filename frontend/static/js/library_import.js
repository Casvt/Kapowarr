const liEls = {
	preBuild: {
		liResult: document.querySelector('.pre-build-els .li-result'),
		searchResult: document.querySelector('.pre-build-els .search-result')
	},
	views: {
		start: document.getElementById('start-window'),
		noResult: document.getElementById('no-result-window'),
		list: document.getElementById('list-window'),
		loading: document.getElementById('loading-window'),
		noCv: document.getElementById('no-cv-window')
	},
	rateLimitBanner: document.getElementById('rate-limit-banner'),
	proposalList: document.querySelector('.proposal-list'),
	selectAll: document.getElementById('selectall-input'),
	search: {
		window: document.getElementById('cv-window'),
		input: document.getElementById('search-input'),
		results: document.querySelector('.search-results'),
		container: document.querySelector('.search-results-container'),
		bar: document.querySelector('.search-bar')
	},
	buttons: {
		cancel: document.querySelectorAll('.cancel-button'),
		run: document.getElementById('run-import-button'),
		import: document.getElementById('import-button'),
		importRename: document.getElementById('import-rename-button')
	}
}

const rowidToFilepath = {}
let shiftSelectStart = null
const selectedRows = new Set()

function buildMatchTitle(title, year, issueCount) {
	let result = ''
	if (title)
		result += title

	if (year !== null)
		result += ` (${year})`

	if (issueCount !== null) {
		const plural = issueCount !== 1 ? 's' : ''
		result += ` [${issueCount} issue${plural}]`
	}

	return result
}

function updateSelection() {
	liEls.proposalList.querySelectorAll(".li-result").forEach((entry, rowid) => {
		if (selectedRows.has(rowid))
			entry.classList.add("selected")
		else
			entry.classList.remove("selected")
	})
}

function loadProposal(apiKey) {
	const params = {
		limit: parseInt(document.querySelector('#limit-input').value),
		limit_parent_folder: document.querySelector('#folder-input').value,
		only_english: document.querySelector('#lang-input').value
	};
	const ffi = document.querySelector('#folder-filter-input');
	if (ffi.offsetParent !== null && (ffi.value || null) !== null)
		params.folder_filter = encodeURIComponent(ffi.value);

	hide(
		[
			liEls.views.start,
			document.querySelector('#folder-filter-error'),
			liEls.rateLimitBanner
		],
		[liEls.views.loading]
	);

	liEls.proposalList.innerHTML = '';
	liEls.selectAll.checked = true;

	fetchAPI('/libraryimport', apiKey, params)
	.then(json => {
		json.result.forEach((result, rowid) => {
			const entry = liEls.preBuild.liResult.cloneNode(true);
			entry.dataset.rowid = rowid;
			rowidToFilepath[rowid] = {
				cv_id: result.cv.id || null,
				filepath: result.filepath
			};
			entry.addEventListener("click", e => e.stopPropagation())

			const toggle = entry.querySelector("input[type='checkbox']")
			toggle.onchange = () => toggleSelected(rowid)

			const title = entry.querySelector('.file-column');
			title.innerText = result.file_title;
			title.title = result.filepath;
			title.onclick = (e) => {
				e.stopPropagation()

				if (
					e.ctrlKey
					|| e.shiftKey && shiftSelectStart === null
				) {
					if (selectedRows.has(rowid))
						selectedRows.delete(rowid)
					else
						selectedRows.add(rowid)

					shiftSelectStart = rowid
				}

				else if (e.shiftKey) {
					let start = shiftSelectStart,
						end = rowid
					if (start > end) {
						start = rowid
						end = shiftSelectStart
					}

					const addSelection = selectedRows.has(shiftSelectStart)
					for (let i = start; i <= end; i++) {
						if (addSelection)
							selectedRows.add(i)
						else
							selectedRows.delete(i)
					}
				}

				else {
					selectedRows.clear()
					selectedRows.add(rowid)
					shiftSelectStart = rowid
				}

				updateSelection()
			}

			const CV_link = entry.querySelector('a');
			CV_link.href = result.cv.link || '';
			CV_link.innerText = buildMatchTitle(
				result.cv.title, null, result.cv.issue_count
			)

			entry.querySelector('button').onclick = e => openEditCVMatch(rowid);

			liEls.proposalList.appendChild(entry);
		});

		if (json.result.length > 0) {
			hide([liEls.views.loading], [liEls.views.list]);

			const has_empty_matches = json.result.some(
				r => r.cv.id === null
			);
			if (has_empty_matches) {
				fetchAPI('/system/status', apiKey)
				.then(checks => {
					const search_limited = checks.result.some(
						st => st.type === 'cv_rate_limit'
							&& st.display_subtypes.includes('search_volumes')
					);
					if (search_limited)
						hide([], [liEls.rateLimitBanner]);
				});
			};
		} else
			hide([liEls.views.loading], [liEls.views.noResult]);
	})
	.catch(e => {
		e.json().then(j => {
			if (
				j.error === "InvalidKeyValue"
				&& j.result.key === "comicvine_api_key"
			)
				hide([liEls.views.loading], [liEls.views.noCv]);

			else if (
				j.error === "InvalidKeyValue"
				&& j.result.key === "folder_filter"
			)
				hide(
					[liEls.views.loading],
					[liEls.views.start, document.querySelector('#folder-filter-error')]
				);

			else
				console.log(j);
		});
	});
};

function toggleSelectAll() {
	const checked = liEls.selectAll.checked;
	liEls.proposalList.querySelectorAll('input[type="checkbox"]').forEach(
		e => e.checked = checked
	);
};

function toggleSelected(rowid) {
	if (!selectedRows.has(rowid))
		return

	const checked = liEls.proposalList.querySelector(
		`tr[data-rowid="${rowid}"] input[type="checkbox"]`
	).checked

	selectedRows.forEach(rowid =>
		liEls.proposalList.querySelector(
			`tr[data-rowid="${rowid}"] input[type="checkbox"]`
		).checked = checked
	)
}

let editMatchId = null

function openEditCVMatch(rowid) {
	editMatchId = rowid
	liEls.search.results.innerHTML = '';
	hide([liEls.search.container]);
	liEls.search.input.value = '';
	showWindow('cv-window');
	liEls.search.input.focus();
};

function editCVMatch(
	comicvine_id,
	site_url,
	title,
	year,
	issue_count
) {
	let target_td;
	if (selectedRows.has(editMatchId))
		target_td = selectedRows
	else
		target_td = [editMatchId]

	target_td.forEach(rowid => {
		const tr = liEls.proposalList.querySelector(`tr[data-rowid="${rowid}"]`)
		rowidToFilepath[rowid].cv_id = parseInt(comicvine_id);
		const link = tr.querySelector('a');
		link.href = site_url;
		link.innerText = buildMatchTitle(title, year, issue_count)
	});
};

function searchCV() {
	const input = liEls.search.input;
	input.blur();
	usingApiKey()
	.then(api_key => {
		liEls.search.results.innerHTML = '';
		fetchAPI('/volumes/search', api_key, {query: input.value})
		.then(json => {
			json.result.forEach(result => {
				const entry = liEls.preBuild.searchResult.cloneNode(true);

				const title = entry.querySelector('td:nth-child(1) a');
				title.href = result.site_url;
				title.innerText = buildMatchTitle(
					result.title, result.year, result.issue_count
				)

				const select_button = entry.querySelector('td:nth-child(2) button');
				select_button.onclick = e => {
					editCVMatch(
						result.comicvine_id,
						result.site_url,
						result.title,
						result.year,
						result.issue_count
					);
					closeWindow();
				};

				liEls.search.results.appendChild(entry);
			});
			hide([], [liEls.search.container]);
		});
	});
};

function importLibrary(api_key, rename=false) {
	const data = [...liEls.proposalList.querySelectorAll(
		'tr:has(input[type="checkbox"]:checked)'
	)]
		.filter(i => rowidToFilepath[i.dataset.rowid].cv_id !== null)
		.map(e => {
			const rowid = e.dataset.rowid;
			return {
				'filepath': rowidToFilepath[rowid].filepath,
				'id': rowidToFilepath[rowid].cv_id
			};
		});

	hide([liEls.views.list], [liEls.views.loading]);
	sendAPI('POST', '/libraryimport', api_key, {rename_files: rename}, data)
	.then(() => hide([liEls.views.loading], [liEls.views.start]));
};

// code run on load

usingApiKey()
.then(api_key => {
	liEls.buttons.run.onclick = e => loadProposal(api_key);
	liEls.buttons.import.onclick = e => importLibrary(api_key, false);
	liEls.buttons.importRename.onclick = e => importLibrary(api_key, true);
});

liEls.search.bar.action = 'javascript:searchCV();';
liEls.selectAll.onchange = e => toggleSelectAll();
liEls.buttons.cancel.forEach(b =>
	b.onclick = e => hide(
		[liEls.views.list, liEls.views.noResult, liEls.views.noCv],
		[liEls.views.start]
	)
);
document.addEventListener("click", () => {
	if (selectedRows.size) {
		selectedRows.clear()
		updateSelection()
		shiftSelectStart = null
	}
})
document.addEventListener("keydown", (e) => {
	if (e.key === "Escape") {
		selectedRows.clear()
		updateSelection()
		shiftSelectStart = null
	}
})
