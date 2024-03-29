//
// General functions
//
function twoDigits(n) {
	return n.toLocaleString("en", { minimumFractionDigits: 2 });
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
	let formatted_params;
	if (params) {
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
	let formatted_params;
	if (params) {
		formatted_params = '&' + Object.entries(params).map(p => p.join('=')).join('&');
	};

	return fetch(`${url_base}/api${endpoint}?api_key=${api_key}${formatted_params}`, {
		'method': method,
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(body)
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
	unmonitored: '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svgjs="http://svgjs.com/svgjs" version="1.1" width="256" height="256" x="0" y="0" viewBox="0 0 24 24" style="enable-background:new 0 0 512 512" xml:space="preserve"><g><path d="M20.137,24a2.8,2.8,0,0,1-1.987-.835L12,17.051,5.85,23.169a2.8,2.8,0,0,1-3.095.609A2.8,2.8,0,0,1,1,21.154V5A5,5,0,0,1,6,0H18a5,5,0,0,1,5,5V21.154a2.8,2.8,0,0,1-1.751,2.624A2.867,2.867,0,0,1,20.137,24ZM6,2A3,3,0,0,0,3,5V21.154a.843.843,0,0,0,1.437.6h0L11.3,14.933a1,1,0,0,1,1.41,0l6.855,6.819a.843.843,0,0,0,1.437-.6V5a3,3,0,0,0-3-3Z"/></g></svg>'
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
	if (window.location.pathname === '/' ||
		window.location.pathname === url_base) {
		task_to_button['search_all'] = {
			'button': document.querySelector('#searchall-button'),
			'icon': `${url_base}/static/img/search.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};
		task_to_button['update_all'] = {
			'button': document.querySelector('#updateall-button'),
			'icon': `${url_base}/static/img/refresh.svg`,
			'loading_icon': `${url_base}/static/img/loading.svg`
		};

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

		document.querySelectorAll('.issue-entry').forEach(entry => {
			const button = entry.querySelector('.action-column > button:first-child');
			task_to_button[`auto_search_issue#${id}#${entry.dataset.id}`] = {
				'button': button,
				'icon': `${url_base}/static/img/search.svg`,
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

function connectToWebSocket() {
	const socket = io({
		path: `${url_base}/api/socket.io`,
		transports: ["polling"],
		upgrade: false,
		autoConnect: false
	});
	socket.on('connect', () => console.log('Connected to WebSocket'));
	socket.on('disconnect', () => console.log('Disconnected from WebSocket'));
	socket.on('request_disconnect', () => {
		console.log('Disconnecting from WebSocket');
		socket.disconnect();
	});
	socket.on('task_added', handleTaskAdded);
	socket.on('task_ended', handleTaskRemoved);
	socket.on('task_status', data => setTaskMessage(data.message));
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
function convertSize(size) {
	if (size === null || size <= 0)
		return 'Unknown';

	for (const [term, division_size] of Object.entries(sizes)) {
		let resulting_size = size / division_size
		if (0 <= resulting_size && resulting_size <= 1000) {
			size = twoDigits(
				Math.round(
					(size / division_size * 100)
				) / 100
			) + term;
			return size;
		};
	};

	size = (
		Math.round(
			(size / sizes.TB * 100)
		) / 100
	).toString() + 'TB';

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
	'last_login': 0
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

function getLocalStorage(keys) {
	const storage = JSON.parse(localStorage.getItem('kapowarr'));
	const result = {};
	if (typeof keys === 'string')
		result[keys] = storage[keys];

	else if (typeof keys === 'object')
		for (const key in keys)
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

// code run on load

const url_base = document.querySelector('#url_base').dataset.value;
const volume_id = parseInt(window.location.pathname.split('/').at(-1)) || null;
mapButtons(volume_id);

usingApiKey()
.then(api_key => {
	setTimeout(() => fillTaskQueue(api_key), 200);
});

setupLocalStorage();
if (getLocalStorage('theme')['theme'] === 'dark')
	document.querySelector(':root').classList.add('dark-mode');
const socket = connectToWebSocket();

document.querySelector('#toggle-nav').onclick = e =>
	document.querySelector('#nav-bar').classList.toggle('show-nav');
