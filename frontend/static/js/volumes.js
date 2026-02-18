const library_els = {
	pages: {
		loading: document.querySelector('#loading-library'),
		empty: document.querySelector('#empty-library'),
		view: document.querySelector('#library-container'),
	},
	views: {
		list: document.querySelector('#list-library'),
		table: document.querySelector('#table-library'),
	},
	pagination: {
		container: document.querySelector('#library-pagination'),
		prev: document.querySelector('#pagination-prev'),
		next: document.querySelector('#pagination-next'),
		status: document.querySelector('#pagination-status'),
		per_page: document.querySelector('#pagination-per-page')
	},
	view_options: {
		sort: document.querySelector('#sort-button'),
		view: document.querySelector('#view-button'),
		filter: document.querySelector('#filter-button')
	},
	task_buttons: {
		update_all: document.querySelector('#updateall-button'),
		search_all: document.querySelector('#searchall-button')
	},
	search: {
		clear: document.querySelector('#clear-search'),
		container: document.querySelector('#search-container'),
		input: document.querySelector('#search-input')
	},
	stats: {
		volume_count: document.querySelector('#volume-count'),
		volume_monitored_count: document.querySelector('#volume-monitored-count'),
		volume_unmonitored_count: document.querySelector('#volume-unmonitored-count'),
		issue_count: document.querySelector('#issue-count'),
		issue_download_count: document.querySelector('#issue-download-count'),
		file_count: document.querySelector('#file-count'),
		total_file_size: document.querySelector('#total-file-size')
	},
	mass_edit: {
		bar: document.querySelector('.action-bar'),
		button: document.querySelector('#massedit-button'),
		toggle: document.querySelector('#massedit-toggle'),
		select_all: document.querySelector('#selectall-input'),
		cancel: document.querySelector('#cancel-massedit')
	}
};

const pre_build_els = {
	list_entry: document.querySelector('.pre-build-els .list-entry'),
	table_entry: document.querySelector('.pre-build-els .table-entry')
};

const library_state = {
	api_key: null,
	display_mode: 'virtual_scroll',
	volumes: [],
	pagination: {
		page: 1,
		per_page: parseInt(library_els.pagination.per_page.value),
		total: 0,
		total_pages: 1
	}
};

const virtual_state = {
	enabled: false,
	last_start: -1,
	last_end: -1,
	handle: null
};

function showLibraryPage(el) {
	hide(Object.values(library_els.pages), [el]);
};

class LibraryEntry {
	constructor(id, api_key) {
		this.id = id;
		this.api_key = api_key;
		this.list_entry = library_els.views.list.querySelector(`.vol-${id}`);
		this.table_entry = library_els.views.table.querySelector(`.vol-${id}`);
	};

	setMonitored(monitored) {
		sendAPI('PUT', `/volumes/${this.id}`, this.api_key, {}, {
			monitored: monitored
		})
		.then(response => {
			const monitored_button = this.table_entry?.querySelector('.table-monitored');
			if (monitored_button !== null && monitored_button !== undefined) {
				monitored_button.onclick = e => new LibraryEntry(this.id, this.api_key)
					.setMonitored(!monitored);
			}

			if (monitored) {
				this.list_entry?.setAttribute('monitored', '');
				if (monitored_button !== null && monitored_button !== undefined)
					setIcon(monitored_button, icons.monitored, 'Monitored');

			} else {
				this.list_entry?.removeAttribute('monitored');
				if (monitored_button !== null && monitored_button !== undefined)
					setIcon(monitored_button, icons.unmonitored, 'Unmonitored');
			};
		});
	};
};

function clearLibraryEntries() {
	library_els.views.list.querySelectorAll('.list-entry').forEach(
		e => e.remove()
	);
	library_els.views.table.innerHTML = '';
};

function createListEntry(volume, api_key) {
	const list_entry = pre_build_els.list_entry.cloneNode(true);

	list_entry.ariaLabel =
		`View the volume ${volume.title} (${volume.year}) Volume ${volume.volume_number}`;
	list_entry.classList.add(`vol-${volume.id}`);
	list_entry.href = `${url_base}/volumes/${volume.id}`;

	list_entry.querySelector('.list-img').src =
		`${url_base}/api/volumes/${volume.id}/cover?api_key=${api_key}`;

	const list_title = list_entry.querySelector('.list-title');
	list_title.innerText =
	list_title.title =
		`${volume.title} (${volume.year})`;

	list_entry.querySelector('.list-volume').innerText =
		`Volume ${volume.volume_number}`;

	const total_monitored = volume.issue_count_monitored || 0;
	const downloaded_monitored = volume.issues_downloaded_monitored || 0;
	const progress = total_monitored > 0
		? (downloaded_monitored / total_monitored) * 100
		: 0;
	const list_bar = list_entry.querySelector('.list-prog-bar');
	list_entry.querySelector('.list-prog-num').innerText =
		`${downloaded_monitored}/${total_monitored}`;
	list_bar.style.width = `${progress}%`;

	if (progress === 100)
		list_bar.style.backgroundColor = 'var(--success-color)';
	else if (volume.monitored === true)
		list_bar.style.backgroundColor = 'var(--accent-color)';
	else
		list_bar.style.backgroundColor = 'var(--error-color)';

	if (volume.monitored)
		list_entry.setAttribute('monitored', '');

	return list_entry;
};

function createTableEntry(volume, api_key) {
	const table_entry = pre_build_els.table_entry.cloneNode(true);

	table_entry.ariaLabel =
		`View the volume ${volume.title} (${volume.year}) Volume ${volume.volume_number}`;
	table_entry.classList.add(`vol-${volume.id}`);
	table_entry.dataset.id = volume.id;

	table_entry.querySelector('.table-link').href =
		`${url_base}/volumes/${volume.id}`;
	table_entry.querySelector('.table-link').innerText = volume.title;
	table_entry.querySelector('.table-year').innerText = volume.year;
	table_entry.querySelector('.table-volume').innerText =
		`Volume ${volume.volume_number}`;

	const total_monitored = volume.issue_count_monitored || 0;
	const downloaded_monitored = volume.issues_downloaded_monitored || 0;
	const progress = total_monitored > 0
		? (downloaded_monitored / total_monitored) * 100
		: 0;
	const table_bar = table_entry.querySelector('.table-prog-bar');
	table_entry.querySelector('.table-prog-num').innerText =
		`${downloaded_monitored}/${total_monitored}`;
	table_bar.style.width = `${progress}%`;

	if (progress === 100)
		table_bar.style.backgroundColor = 'var(--success-color)';
	else if (volume.monitored === true)
		table_bar.style.backgroundColor = 'var(--accent-color)';
	else
		table_bar.style.backgroundColor = 'var(--error-color)';

	const monitored_button = table_entry.querySelector('.table-monitored');
	monitored_button.onclick = e => new LibraryEntry(volume.id, api_key)
		.setMonitored(!volume.monitored);
	if (volume.monitored)
		setIcon(monitored_button, icons.monitored, 'Monitored');
	else
		setIcon(monitored_button, icons.unmonitored, 'Unmonitored');

	return table_entry;
};

function renderList(volumes, api_key) {
	const space_taker = document.querySelector('.space-taker');
	const fragment = document.createDocumentFragment();

	volumes.forEach(volume => {
		fragment.appendChild(createListEntry(volume, api_key));
	});

	library_els.views.list.insertBefore(fragment, space_taker);
};

function renderTable(volumes, api_key) {
	const fragment = document.createDocumentFragment();
	volumes.forEach(volume => {
		fragment.appendChild(createTableEntry(volume, api_key));
	});
	library_els.views.table.appendChild(fragment);
};

function getVirtualRange(total_entries) {
	const list_el = library_els.views.list;
	
	// Use fixed dimensions for consistent virtual scroll behavior
	const entry_width = 140; // Fixed width in virtual mode
	const gap = 16; // 1rem gap
	const entry_height = 280; // Approximate height: 140px * 1.5 (aspect ratio 2:3) + text/progress
	
	const container_width = list_el.clientWidth || window.innerWidth - 48;
	const columns = Math.max(1, Math.floor((container_width + gap) / (entry_width + gap)));
	
	const list_top = list_el.getBoundingClientRect().top + window.scrollY;
	const relative_scroll = Math.max(0, window.scrollY - list_top);
	const visible_rows = Math.ceil(window.innerHeight / entry_height) + 2;
	const buffer_rows = 3;

	const start_row = Math.max(0, Math.floor(relative_scroll / entry_height) - buffer_rows);
	const end_row = start_row + visible_rows + (buffer_rows * 2);

	const start = start_row * columns;
	const end = Math.min(total_entries, end_row * columns);
	const total_rows = Math.ceil(total_entries / columns);

	return {
		start,
		end,
		padding_top: start_row * entry_height,
		padding_bottom: Math.max(0, (total_rows - end_row) * entry_height)
	};
};

function renderVirtualList(force=false) {
	if (!virtual_state.enabled)
		return;

	const total = library_state.volumes.length;
	if (total === 0)
		return;

	const range = getVirtualRange(total);
	
	// Skip if nothing changed (unless forced)
	if (
		!force
		&& range.start === virtual_state.last_start
		&& range.end === virtual_state.last_end
	)
		return;

	virtual_state.last_start = range.start;
	virtual_state.last_end = range.end;

	// Ensure we render at least some items
	const items_to_render = library_state.volumes.slice(range.start, range.end);
	if (items_to_render.length === 0 && total > 0) {
		// Fallback: render first batch if range calculation failed
		const fallback_end = Math.min(total, 50);
		clearLibraryEntries();
		library_els.views.list.style.paddingTop = '0px';
		library_els.views.list.style.paddingBottom = '0px';
		renderList(library_state.volumes.slice(0, fallback_end), library_state.api_key);
		return;
	}

	clearLibraryEntries();
	library_els.views.list.style.paddingTop = `${range.padding_top}px`;
	library_els.views.list.style.paddingBottom = `${range.padding_bottom}px`;
	renderList(items_to_render, library_state.api_key);
};

function scheduleVirtualRender() {
	if (!virtual_state.enabled)
		return;

	if (virtual_state.handle !== null)
		return;

	virtual_state.handle = requestAnimationFrame(() => {
		virtual_state.handle = null;
		renderVirtualList();
	});
};

function enableVirtualMode() {
	virtual_state.enabled = true;
	virtual_state.last_start = -1;
	virtual_state.last_end = -1;
	library_els.views.list.classList.add('virtual-mode');
	window.addEventListener('scroll', scheduleVirtualRender, { passive: true });
	window.addEventListener('resize', scheduleVirtualRender, { passive: true });
};

function disableVirtualMode() {
	virtual_state.enabled = false;
	virtual_state.last_start = -1;
	virtual_state.last_end = -1;
	if (virtual_state.handle !== null) {
		cancelAnimationFrame(virtual_state.handle);
		virtual_state.handle = null;
	}
	window.removeEventListener('scroll', scheduleVirtualRender);
	window.removeEventListener('resize', scheduleVirtualRender);
	library_els.views.list.classList.remove('virtual-mode');
	library_els.views.list.style.paddingTop = '0px';
	library_els.views.list.style.paddingBottom = '0px';
};

function renderPaginationControls() {
	if (library_state.display_mode !== 'pagination') {
		library_els.pagination.container.classList.add('hidden');
		return;
	}

	library_els.pagination.container.classList.remove('hidden');
	library_els.pagination.status.innerText =
		`Page ${library_state.pagination.page} of ${library_state.pagination.total_pages}`;
	library_els.pagination.prev.disabled = library_state.pagination.page <= 1;
	library_els.pagination.next.disabled =
		library_state.pagination.page >= library_state.pagination.total_pages;
};

function renderCurrentView(force_virtual=false) {
	clearLibraryEntries();

	if (library_state.volumes.length === 0) {
		disableVirtualMode();
		showLibraryPage(library_els.pages.empty);
		renderPaginationControls();
		return;
	}

	const showing_table =
		library_els.mass_edit.toggle.hasAttribute('checked')
		|| library_els.view_options.view.value === 'table';

	if (
		library_state.display_mode === 'virtual_scroll'
		&& !showing_table
	) {
		enableVirtualMode();
		renderVirtualList(force_virtual);
	} else {
		disableVirtualMode();
		if (showing_table)
			renderTable(library_state.volumes, library_state.api_key);
		else
			renderList(library_state.volumes, library_state.api_key);
	}

	renderPaginationControls();
	showLibraryPage(library_els.pages.view);
};

function getLibraryParams() {
	const params = {
		sort: library_els.view_options.sort.value,
		filter: library_els.view_options.filter.value
	};
	const query = library_els.search.input.value;
	if (query !== '')
		params.query = query;

	return params;
};

function fetchLibrary(api_key, page=1) {
	showLibraryPage(library_els.pages.loading);
	const params = getLibraryParams();

	if (library_state.display_mode === 'pagination') {
		params.page = page;
		params.per_page = library_state.pagination.per_page;

		fetchAPI('/volumes', api_key, params)
		.then(json => {
			library_state.volumes = json.result.items;
			library_state.pagination.page = json.result.page;
			library_state.pagination.per_page = json.result.per_page;
			library_state.pagination.total = json.result.total;
			library_state.pagination.total_pages = json.result.total_pages;
			renderCurrentView();
		});

		return;
	}

	fetchAPI('/volumes', api_key, params)
	.then(json => {
		library_state.volumes = json.result;
		renderCurrentView(true);
	});
};

function searchLibrary() {
	if (library_state.api_key === null)
		return;

	if (library_state.display_mode === 'pagination')
		fetchLibrary(library_state.api_key, 1);
	else
		fetchLibrary(library_state.api_key);
};

function clearSearch(api_key) {
	library_els.search.input.value = '';
	if (library_state.display_mode === 'pagination')
		fetchLibrary(api_key, 1);
	else
		fetchLibrary(api_key);
};

function fetchStats(api_key) {
	fetchAPI('/volumes/stats', api_key)
	.then(json => {
		library_els.stats.volume_count.innerText = json.result.volumes;
		library_els.stats.volume_monitored_count.innerText = json.result.monitored;
		library_els.stats.volume_unmonitored_count.innerText = json.result.unmonitored;
		library_els.stats.issue_count.innerText = json.result.issues;
		library_els.stats.issue_download_count.innerText = json.result.downloaded_issues;
		library_els.stats.file_count.innerText = json.result.files;
		library_els.stats.total_file_size.innerText =
			json.result.total_file_size > 0
			? convertSize(json.result.total_file_size)
			: '0 MB';
	});
};

//
// Mass Edit
//
function runAction(api_key, action, args={}) {
	showLibraryPage(library_els.pages.loading);

	const volume_ids = [...library_els.views.table.querySelectorAll(
		'input[type="checkbox"]:checked'
	)].map(v => parseInt(v.parentNode.parentNode.dataset.id))

	sendAPI('POST', '/masseditor', api_key, {}, {
		'volume_ids': volume_ids,
		'action': action,
		'args': args
	})
	.then(response => {
		library_els.mass_edit.select_all.checked = false;
		if (library_state.display_mode === 'pagination')
			fetchLibrary(api_key, library_state.pagination.page);
		else
			fetchLibrary(api_key);
	});
};

function fetchDisplayMode(api_key) {
	return fetchAPI('/settings', api_key)
		.then(json => {
			const mode = json.result.library_display_mode;
			// Validate mode value, default to virtual_scroll if invalid or missing
			if (mode === 'pagination' || mode === 'virtual_scroll') {
				console.log('Library display mode:', mode);
				return mode;
			}
			console.log('Library display mode defaulting to virtual_scroll, got:', mode);
			return 'virtual_scroll';
		})
		.catch(err => {
			console.error('Failed to fetch display mode:', err);
			return 'virtual_scroll';
		});
};

// code run on load

library_els.view_options.sort.value = getLocalStorage('lib_sorting')['lib_sorting'];
library_els.view_options.view.value = getLocalStorage('lib_view')['lib_view'];
library_els.view_options.filter.value = getLocalStorage('lib_filter')['lib_filter'];
usingApiKey()
.then(api_key => {
	library_state.api_key = api_key;
	fetchStats(api_key);

	fetchDisplayMode(api_key)
	.then(mode => {
		library_state.display_mode = mode;
		fetchLibrary(
			api_key,
			library_state.display_mode === 'pagination' ? 1 : library_state.pagination.page
		);
	});

	library_els.search.clear.onclick =
		e => clearSearch(api_key);

	library_els.task_buttons.update_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {'cmd': 'update_all'});
	library_els.task_buttons.search_all.onclick =
		e => sendAPI('POST', '/system/tasks', api_key, {}, {'cmd': 'search_all'});

	library_els.view_options.sort.onchange = e => {
		setLocalStorage({'lib_sorting': library_els.view_options.sort.value});
		if (library_state.display_mode === 'pagination')
			fetchLibrary(api_key, 1);
		else
			fetchLibrary(api_key);
	};
	library_els.view_options.view.onchange = e => {
		setLocalStorage({'lib_view': library_els.view_options.view.value});
		renderCurrentView(true);
	};
	library_els.view_options.filter.onchange = e => {
		setLocalStorage({'lib_filter': library_els.view_options.filter.value});
		if (library_state.display_mode === 'pagination')
			fetchLibrary(api_key, 1);
		else
			fetchLibrary(api_key);
	};

	library_els.pagination.prev.onclick = e => {
		if (library_state.pagination.page > 1)
			fetchLibrary(api_key, library_state.pagination.page - 1);
	};
	library_els.pagination.next.onclick = e => {
		if (library_state.pagination.page < library_state.pagination.total_pages)
			fetchLibrary(api_key, library_state.pagination.page + 1);
	};
	library_els.pagination.per_page.onchange = e => {
		library_state.pagination.per_page = parseInt(
			library_els.pagination.per_page.value
		);
		if (library_state.display_mode === 'pagination')
			fetchLibrary(api_key, 1);
	};

    library_els.mass_edit.button.onclick =
    library_els.mass_edit.cancel.onclick =
        e => {
            const toggle = library_els.mass_edit.toggle;
            if (toggle.hasAttribute('checked')) {
                toggle.removeAttribute('checked');
            } else {
                const select = document.querySelector('select[name="root_folder_id"]');
                if (select.querySelector('option') === null) {
                    fetchAPI('/rootfolder', api_key)
                    .then(json => {
                        json.result.forEach(rf => {
                            const entry = document.createElement('option');
                            entry.value = rf.id;
                            entry.innerText = rf.folder;
                            select.appendChild(entry);
                        });
                        toggle.setAttribute('checked', '');
						renderCurrentView(true);
                    });
				} else {
                    toggle.setAttribute('checked', '');
				}
            }
			renderCurrentView(true);
        };
	library_els.mass_edit.bar.querySelectorAll('.action-divider > button[data-action]').forEach(
		b => b.onclick = e => runAction(api_key, e.target.dataset.action)
	);
	library_els.mass_edit.bar.querySelector('button[data-action="delete"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'delete_folder': document.querySelector(
					'select[name="delete_folder"]'
				).value === "true"
			}
		);
	library_els.mass_edit.bar.querySelector('button[data-action="root_folder"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'root_folder_id': parseInt(document.querySelector(
					'select[name="root_folder_id"]'
				).value)
			}
		);
});
library_els.search.container.action = 'javascript:searchLibrary();';
library_els.mass_edit.select_all.onchange =
	e => library_els.views.table.querySelectorAll('input[type="checkbox"]')
			.forEach(c => c.checked = library_els.mass_edit.select_all.checked);
