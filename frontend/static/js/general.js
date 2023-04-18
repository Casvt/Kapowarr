//
// General functions
//
function addEventListener(target, event, func) {
	document.querySelectorAll(target).forEach(t => {
		t.addEventListener(event, func);
	});
};

function setAttribute(target, key, value) {
	document.querySelectorAll(target).forEach(t => {
		t.setAttribute(key, value);
	});
};

//
// Tasks
//
const task_to_button = {};
function mapButtons(id) {
	if (id === null) {
		task_to_button['search_all'] = {
			'button': document.querySelector('#searchall-button'),
			'icon': '/static/img/search_white.svg',
			'loading_icon': '/static/img/loading_white.svg'
		};
		task_to_button['update_all'] = {
			'button': document.querySelector('#updateall-button'),
			'icon': '/static/img/refresh.svg',
			'loading_icon': '/static/img/loading_white.svg'
		};
	} else {
		task_to_button[`refresh_and_scan#${id}`] = {
			'button': document.querySelector('#refresh-button'),
			'icon': '/static/img/refresh.svg',
			'loading_icon': '/static/img/loading_white.svg'
		};
		task_to_button[`auto_search#${id}`] = {
			'button': document.querySelector('#autosearch-button'),
			'icon': '/static/img/search_white.svg',
			'loading_icon': '/static/img/loading_white.svg'
		};
		document.querySelectorAll('.issue-entry').forEach(entry => {
			const button = entry.querySelector('.action-column > button:first-child');
			task_to_button[`auto_search_issue#${id}#${entry.dataset.id}`] = {
				'button': button,
				'icon': '/static/img/search.svg',
				'loading_icon': '/static/img/loading.svg'
			};
		});
	};
};

function spinButtons(result, id) {
	// Map all buttons to their actions
	// auto_search_issue#1155 -> button
	// Remap all actions to prev. map key format
	// Loop through buttons and check if key is in action map, then apply button
	const tasks = [];
	let task_string;
	result.forEach(task => {
		if (id === null && task.volume_id !== null || id !== null && task.volume_id === null) return;
		task_string = task.action;
		if (task.volume_id !== null) {
			task_string += `#${task.volume_id}`;
			if (task.issue_id !== null) {
				task_string += `#${task.issue_id}`;
			};
		};
		tasks.push(task_string);
	});

	for (const task in task_to_button) {
		const button_info = task_to_button[task];
		if (button_info.button) {
			const icon = button_info.button.querySelector('img');
			if (tasks.includes(task)) {
				if (icon.src === button_info.loading_icon) continue
				icon.src = button_info.loading_icon;
				icon.classList.add('spinning');
			} else {
				if (icon.src === button_info.icon) continue
				icon.src = button_info.icon;
				icon.classList.remove('spinning');
			};
		};
	};
};

function fillTaskQueue(api_key, id) {
	fetch(`/api/system/tasks?api_key=${api_key}`, {
		'priority': 'low'
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		return response.json();
	})
	.then(json => {
		const table = document.querySelector('#task-queue');
		table.innerHTML = '';
		if (json.result.length >= 1) {
			const entry = document.createElement('p');
			entry.innerText = json.result[0].message;
			table.appendChild(entry);
		};
		spinButtons(json.result, id);
	})
	.catch(e => {
		if (e === 401) window.location.href = `/login?redirect=${window.location.pathname}`;
	});
};

//
// Nav
//
function showNav(e) {
	document.querySelector('#nav-bar').classList.toggle('show-nav');
};

// code run on load

const volume_id = parseInt(window.location.pathname.split('/').at(-1)) || null;
if (volume_id === null) mapButtons(volume_id);

usingApiKey()
.then(api_key => {
	setTimeout(() => fillTaskQueue(api_key, volume_id), 200);
	setInterval(() => fillTaskQueue(api_key, volume_id), 2000);
})

addEventListener('#toggle-nav', 'click', showNav)
