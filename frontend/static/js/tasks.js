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
	fetch(`${url_base}/api/system/tasks/planning?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#task-intervals');
		table.innerHTML = '';
		json.result.forEach(e => {
			const entry = document.createElement('tr');

			const name = document.createElement('td');
			name.innerText = e.display_name;
			entry.appendChild(name);

			const interval = document.createElement('td');
			interval.innerText = convertInterval(e.interval);
			entry.appendChild(interval);

			const last_run = document.createElement('td');
			last_run.innerText = convertTime(e.last_run, false);
			entry.appendChild(last_run);

			const next_run = document.createElement('td');
			next_run.innerText = convertTime(e.next_run, true);
			entry.appendChild(next_run);

			table.appendChild(entry);
		});
	});
};

// 
// Task history
// 
function fillHistory(api_key) {
	fetch(`${url_base}/api/system/tasks/history?api_key=${api_key}`)
		.then(response => {
			if (!response.ok) return Promise.reject(response.status);
			return response.json();
		})
		.then(json => {
			const table = document.querySelector('#history');
			table.innerHTML = '';
			json.result.forEach(obj => {
				const entry = document.createElement('tr');
				entry.classList.add('history-entry');

				const title = document.createElement('td');
				title.innerText = obj.display_title;
				entry.appendChild(title);

				const date = document.createElement('td');
				var d = new Date(obj.run_at * 1000);
				var formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5)
				date.innerText = formatted_date;
				entry.append(date);

				table.appendChild(entry);
			});
		})
		.catch(e => {
			if (e === 401) window.location.href = `${url_base}/`;
		});
};

function clearHistory(api_key) {
	fetch(`${url_base}/api/system/tasks/history?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	document.querySelector('#history').innerHTML = '';
};

// code run on load

usingApiKey()
.then(api_key => {
	fillHistory(api_key);
	fillPlanning(api_key);
	addEventListener('#clear-button', 'click', e => clearHistory(api_key));
});
