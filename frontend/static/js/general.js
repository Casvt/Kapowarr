//
// General functions
//
function minDecimalPoints(n, pointCount) {
	return n.toLocaleString("en", { minimumFractionDigits: pointCount });
};

function setIcon(container, icon, title='') {
	container.title = title;
	container.innerHTML = icon;
};

function setImage(container, img, title='') {
	container.title = title;
	container.querySelector('img').src = `${url_base}/static/img/${img}`;
};

function hide(to_hide, to_show=null) {
	to_hide.forEach(el => el.classList.add('hidden'));
	if (to_show !== null)
		to_show.forEach(el => el.classList.remove('hidden'));
};

async function fetchAPI(endpoint, api_key, params={}, json_return=true) {
	let formatted_params = '';
	if (Object.keys(params).length) {
		formatted_params = '&' + Object.entries(params).map(p => p.join('=')).join('&');
	};

	return fetch(`${url_base}/api${endpoint}?api_key=${api_key}${formatted_params}`)
	.then(response => {
		if (!response.ok) return Promise.reject(response);
		if (json_return)
			return response.json();
		else
			return response;
	})
	.catch(response => {
		if (response.status === 401) {
			setLocalStorage({api_key: null})
			window.location.href = `${url_base}/login?redirect=${window.location.pathname}`;
		} else {
			return Promise.reject(response);
		};
	});
};

async function sendAPI(method, endpoint, api_key, params={}, body={}) {
	let formatted_params = '';
	if (Object.keys(params).length) {
		formatted_params = '&' + Object.entries(params).map(p => p.join('=')).join('&');
	};

	headers = {}
	if (!(body instanceof FormData)) {
		headers["Content-Type"] = "application/json"
		body = JSON.stringify(body)
	}

	return fetch(`${url_base}/api${endpoint}?api_key=${api_key}${formatted_params}`, {
		'method': method,
		'headers': headers,
		'body': body
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response);
		return response
	})
	.catch(response => {
		if (response.status === 401) {
			setLocalStorage({api_key: null})
			window.location.href = `${url_base}/login?redirect=${window.location.pathname}`;
		} else {
			return Promise.reject(response);
		};
	});
};

//
// Icons
//
const icons = {
	monitored: '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svgjs="http://svgjs.com/svgjs" version="1.1" width="256" height="256" x="0" y="0" viewBox="0 0 24 24" style="enable-background:new 0 0 512 512" xml:space="preserve"><g><path d="M2.849,23.55a2.954,2.954,0,0,0,3.266-.644L12,17.053l5.885,5.853a2.956,2.956,0,0,0,2.1.881,3.05,3.05,0,0,0,1.17-.237A2.953,2.953,0,0,0,23,20.779V5a5.006,5.006,0,0,0-5-5H6A5.006,5.006,0,0,0,1,5V20.779A2.953,2.953,0,0,0,2.849,23.55Z"/></g></svg>',
	unmonitored: '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svgjs="http://svgjs.com/svgjs" version="1.1" width="256" height="256" x="0" y="0" viewBox="0 0 24 24" style="enable-background:new 0 0 512 512" xml:space="preserve"><g><path d="M20.137,24a2.8,2.8,0,0,1-1.987-.835L12,17.051,5.85,23.169a2.8,2.8,0,0,1-3.095.609A2.8,2.8,0,0,1,1,21.154V5A5,5,0,0,1,6,0H18a5,5,0,0,1,5,5V21.154a2.8,2.8,0,0,1-1.751,2.624A2.867,2.867,0,0,1,20.137,24ZM6,2A3,3,0,0,0,3,5V21.154a.843.843,0,0,0,1.437.6h0L11.3,14.933a1,1,0,0,1,1.41,0l6.855,6.819a.843.843,0,0,0,1.437-.6V5a3,3,0,0,0-3-3Z"/></g></svg>',
	clear: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M256,0C114.615,0,0,114.615,0,256s114.615,256,256,256s256-114.615,256-256C511.847,114.678,397.322,0.153,256,0z M256,64   c39.843,0.004,78.686,12.477,111.083,35.669L99.669,367.061c-61.503-86.178-41.499-205.897,44.679-267.4   C176.93,76.409,215.972,63.939,256,64z M256,448c-39.837-0.002-78.673-12.475-111.061-35.669l267.392-267.413   c61.514,86.17,41.527,205.891-44.643,267.406C335.098,435.588,296.042,448.064,256,448z"></path></svg>',
	download: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M210.731,386.603c24.986,25.002,65.508,25.015,90.51,0.029c0.01-0.01,0.019-0.019,0.029-0.029l68.501-68.501   c7.902-8.739,7.223-22.23-1.516-30.132c-8.137-7.357-20.527-7.344-28.649,0.03l-62.421,62.443l0.149-329.109   C277.333,9.551,267.782,0,256,0l0,0c-11.782,0-21.333,9.551-21.333,21.333l-0.192,328.704L172.395,288   c-8.336-8.33-21.846-8.325-30.176,0.011c-8.33,8.336-8.325,21.846,0.011,30.176L210.731,386.603z" /><path d="M490.667,341.333L490.667,341.333c-11.782,0-21.333,9.551-21.333,21.333V448c0,11.782-9.551,21.333-21.333,21.333H64   c-11.782,0-21.333-9.551-21.333-21.333v-85.333c0-11.782-9.551-21.333-21.333-21.333l0,0C9.551,341.333,0,350.885,0,362.667V448   c0,35.346,28.654,64,64,64h384c35.346,0,64-28.654,64-64v-85.333C512,350.885,502.449,341.333,490.667,341.333z" /></svg>',
	upload: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="M172.399,117.448l62.421-62.443l-0.149,329.344c0,11.782,9.551,21.333,21.333,21.333l0,0   c11.782,0,21.333-9.551,21.333-21.333l0.149-328.981l62.123,62.144c8.475,8.185,21.98,7.951,30.165-0.524   c7.985-8.267,7.985-21.374,0-29.641L301.273,18.76c-24.986-25.002-65.508-25.015-90.51-0.029c-0.01,0.01-0.019,0.019-0.029,0.029   l-68.501,68.523c-8.185,8.475-7.951,21.98,0.524,30.165C151.024,125.433,164.131,125.433,172.399,117.448z"/><path d="M490.671,341.341L490.671,341.341c-11.782,0-21.333,9.551-21.333,21.333v85.333c0,11.782-9.551,21.333-21.333,21.333h-384   c-11.782,0-21.333-9.551-21.333-21.333v-85.333c0-11.782-9.551-21.333-21.333-21.333l0,0c-11.782,0-21.333,9.551-21.333,21.333   v85.333c0,35.346,28.654,64,64,64h384c35.346,0,64-28.654,64-64v-85.333C512.004,350.892,502.453,341.341,490.671,341.341z"/></svg>'
};

const images = {
	check: 'check.svg',
	cancel: 'cancel.svg'
};

//
// Tasks
//
const task_to_button = {};
function mapButtons(id) {
	if (window.location.pathname === (url_base + '/')) {
		task_to_button['update_all'] = {
			'button': document.querySelector('#updateall-button'),
			'icon': `${url_base}/static/img/refresh.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};

	} else if (window.location.pathname === (url_base + '/system/tasks')) {
		document.querySelectorAll('.task-interval-table > tbody > tr').forEach(entry => {
			task_to_button[entry.dataset.task_name] = {
				'button': entry.querySelector('button'),
				'icon': `${url_base}/static/img/refresh.svg`,
				'loading_icon': `${url_base}/static/img/loading.svg`
			};
		});

	} else if (id !== null) {
		task_to_button[`refresh_and_scan#${id}`] = {
			'button': document.querySelector('#refresh-button'),
			'icon': `${url_base}/static/img/refresh.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};
		task_to_button[`auto_search#${id}`] = {
			'button': document.querySelector('#autosearch-button'),
			'icon': `${url_base}/static/img/search.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};
		task_to_button[`mass_rename#${id}`] = {
			'button': document.querySelector('#rename-button'),
			'icon': `${url_base}/static/img/rename.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};
		task_to_button[`mass_convert#${id}`] = {
			'button': document.querySelector('#convert-button'),
			'icon': `${url_base}/static/img/convert.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};

		document.querySelectorAll('.issue-entry').forEach(entry => {
			task_to_button[`auto_search_issue#${id}#${entry.dataset.id}`] = {
				'button': entry.querySelector('.action-column > button:first-child'),
				'icon': `${url_base}/static/img/search.svg`,
				'loading_icon': `${url_base}/static/img/loading.svg`
			};
			task_to_button[`mass_convert_issue#${id}#${entry.dataset.id}`] = {
				'button': entry.querySelector('.action-column > button:last-child'),
				'icon': `${url_base}/static/img/convert.svg`,
				'loading_icon': `${url_base}/static/img/loading.svg`
			};
		});
	};
};

function buildTaskString(task) {
	let task_string = task.action;
	if (task.volume_id !== null) {
		task_string += `#${task.volume_id}`;
		if (task.issue_id !== null) {
			task_string += `#${task.issue_id}`;
		};
	};
	return task_string;
};

function setTaskMessage(message) {
	const table = document.querySelector('#task-queue');
	table.innerHTML = '';
	if (message !== '') {
		const entry = document.createElement('p');
		entry.innerText = message;
		table.appendChild(entry);
	};
};

function spinButton(task_string) {
	const button_info = task_to_button[task_string];
	const icon = button_info.button.querySelector('img');

	if (icon.src === button_info.loading_icon)
		return;

	icon.src = button_info.loading_icon;
	icon.classList.add('spinning');
};

function unspinButton(task_string) {
	const button_info = task_to_button[task_string];
	const icon = button_info.button.querySelector('img');

	if (icon.src === button_info.icon)
		return;

	icon.src = button_info.icon;
	icon.classList.remove('spinning');
};

function fillTaskQueue(api_key) {
	fetch(`${url_base}/api/system/tasks?api_key=${api_key}`, {
		'priority': 'low'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		return response.json();
	})
	.then(json => {
		setTaskMessage(json.result[0].message);
		json.result.forEach(task => {
			const task_string = buildTaskString(task);
			if (task_string in task_to_button)
				spinButton(task_string);
		});
	})
	.catch(e => {
		if (e === 401) {
			setLocalStorage({api_key: null})
			window.location.href =
				`${url_base}/login?redirect=${window.location.pathname}`;
		}
	});
};

function handleTaskAdded(data) {
	const task_string = buildTaskString(data);
	if (task_string in task_to_button)
		spinButton(task_string);
};

function handleTaskRemoved(data) {
	setTaskMessage('');

	const task_string = buildTaskString(data);
	if (task_string in task_to_button)
		unspinButton(task_string);
};

function updateBadge(count) {
	const badge = document.querySelector('#system-issues-badge');
	if (!badge) return;
	badge.innerText = count;
	if (count > 0)
		badge.classList.remove('hidden');
	else
		badge.classList.add('hidden');
};

function handleStatusCount(data) {
	updateBadge(data.count);
};

function initStatusBadge(api_key) {
	fetchAPI('/system/status', api_key)
	.then(json => {
		updateBadge(json.result.length);
	})
	.catch(e => console.log(e));
};

function connectToWebSocket(api_key) {
	const socket = io({
		path: `${url_base}/api/socket.io`,
		transports: ["polling"],
		upgrade: false,
		autoConnect: false,
		closeOnBeforeunload: true,
		auth: {'api_key': api_key}
	});
	socket.on('connect', () => console.log('Connected to WebSocket'));
	socket.on('disconnect', () => console.log('Disconnected from WebSocket'));

	socket.on('task_added', handleTaskAdded);
	socket.on('task_ended', handleTaskRemoved);
	socket.on('task_status', data => setTaskMessage(data.message));
	socket.on('status_count', handleStatusCount);
	socket.connect();
	return socket;
};

//
// Size conversion
//
const sizes = {
	'B': 1,
	'KB': 1000,
	'MB': 1000000,
	'GB': 1000000000,
	'TB': 1000000000000
};
function convertSize(size, decimalPointCount) {
	if (size === null || size <= 0)
		return 'Unknown';

	for (const [term, division_size] of Object.entries(sizes)) {
		let resulting_size = size / division_size
		if (0 <= resulting_size && resulting_size <= 1000) {
			size = minDecimalPoints(
				Math.round(
					(size / division_size * 100)
				) / 100,
				decimalPointCount
			) + ' ' + term;
			return size;
		};
	};

	size = (
		Math.round(
			(size / sizes.TB * 100)
		) / 100
	).toString() + ' TB';

	return size;
};

//
// LocalStorage
//
const default_values = {
	'lib_sorting': 'title',
	'lib_view': 'posters',
	'lib_filter': '',
	'theme': 'light',
	'translated_filter': 'all',
	'api_key': null,
	'last_login': 0,
	'monitor_new_volume': true,
	'monitor_new_issues': true,
	'monitoring_scheme': "all"
};

function setupLocalStorage() {
	if (!localStorage.getItem('kapowarr'))
		localStorage.setItem('kapowarr', JSON.stringify(default_values));

	const missing_keys = [
		...Object.keys(default_values)
	].filter(e =>
		![...Object.keys(JSON.parse(localStorage.getItem('kapowarr')))].includes(e)
	)

	if (missing_keys.length) {
		const storage = JSON.parse(localStorage.getItem('kapowarr'));

		missing_keys.forEach(missing_key => {
			storage[missing_key] = default_values[missing_key]
		})

		localStorage.setItem('kapowarr', JSON.stringify(storage));
	};
	return;
};

function getLocalStorage(...keys) {
	const storage = JSON.parse(localStorage.getItem('kapowarr'));
	const result = {};
	for (const key of keys)
		result[key] = storage[key];

	return result;
};

function setLocalStorage(keys_values) {
	const storage = JSON.parse(localStorage.getItem('kapowarr'));

	for (const [key, value] of Object.entries(keys_values))
		storage[key] = value;

	localStorage.setItem('kapowarr', JSON.stringify(storage));
	return;
};

function setupTheme() {
	const theme = getLocalStorage('theme')['theme']
	let className = ''
	if (theme === 'dark') {
		className = 'dark-mode'
	}

	const root = document.querySelector(":root")
	root.classList.remove(...root.classList.values())
	if (className)
		document.querySelector(":root").classList.add(className)

	const expires = new Date()
	if (className === "")
		// Expire it, which removes it
		expires.setTime(expires.getTime() - 86400 * 1000)
	else
		expires.setTime(expires.getTime() + 86400 * 1000)

	document.cookie = `theme=${className}; expires=${expires.toUTCString()}; path=/;`
	return
}

// code run on load

const url_base = document.querySelector('#url_base').dataset.value;
const volume_id = parseInt(window.location.pathname.split('/').at(-1)) || null;
mapButtons(volume_id);

let socket;
usingApiKey()
.then(api_key => {
	setTimeout(() => fillTaskQueue(api_key), 200);
	socket = connectToWebSocket(api_key);
	initStatusBadge(api_key);
});

setupLocalStorage();
setupTheme();

document.querySelector('#toggle-nav').onclick = e =>
	document.querySelector('#nav-bar').classList.toggle('show-nav');
