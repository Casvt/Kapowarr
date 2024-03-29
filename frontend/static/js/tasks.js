const TaskEls = {
	pre_build: {
		task: document.querySelector('.pre-build-els .task-entry'),
		history: document.querySelector('.pre-build-els .history-entry')
	},
	intervals: document.querySelector('#task-intervals'),
	history: document.querySelector('#history'),
	buttons: {
		refresh: document.querySelector('#refresh-button'),
		clear: document.querySelector('#clear-button')
	}
};

//
// Task planning
//
function convertInterval(interval) {
	result = Math.round(interval / 3600); // seconds -> hours
	return `${result} hours`;
};

function convertTime(epoch, future) {
	result = Math.round(Math.abs(Date.now() / 1000 - epoch) / 3600); // delta hours
	if (future) return `in ${result} hours`;
	else return `${result} hours ago`;
};

function fillPlanning(api_key) {
	fetchAPI('/system/tasks/planning', api_key)
	.then(json => {
		TaskEls.intervals.innerHTML = '';
		json.result.forEach(e => {
			const entry = TaskEls.pre_build.task.cloneNode(true);

			entry.querySelector('.name-column').innerText = e.display_name;
			entry.querySelector('.interval-column').innerText =
				convertInterval(e.interval);
			entry.querySelector('.prev-column').innerText =
				convertTime(e.last_run, false);
			entry.querySelector('.next-column').innerText =
				convertTime(e.next_run, true);

			TaskEls.intervals.appendChild(entry);
		});
	});
};

//
// Task history
//
function fillHistory(api_key) {
	fetchAPI('/system/tasks/history', api_key)
	.then(json => {
		TaskEls.history.innerHTML = '';
		json.result.forEach(obj => {
			const entry = TaskEls.pre_build.history.cloneNode(true);

			entry.querySelector('.title-column').innerText = obj.display_title;

			var d = new Date(obj.run_at * 1000);
			var formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5)
			entry.querySelector('.date-column').innerText = formatted_date;

			TaskEls.history.appendChild(entry);
		});
	});
};

function clearHistory(api_key) {
	sendAPI('DELETE', '/system/tasks/history', api_key)
	TaskEls.history.innerHTML = '';
};

// code run on load

usingApiKey()
.then(api_key => {
	fillHistory(api_key);
	fillPlanning(api_key);
	TaskEls.buttons.refresh.onclick = e => fillHistory(api_key);
	TaskEls.buttons.clear.onclick = e => clearHistory(api_key);
});
