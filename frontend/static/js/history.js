function fillHistory() {
	fetch(`/api/activity/history?api_key=${api_key}`)
		.then(response => {
			// catch errors
			if (!response.ok) {
				return Promise.reject(response.status);
			};

			return response.json();
		})
		.then(json => {
			const table = document.getElementById('history');
			table.innerHTML = '';
			for (i = 0; i < json.result.length; i++) {
				const obj = json.result[i];

				const entry = document.createElement('tr');
				entry.classList.add('history-entry');

				const title = document.createElement('td');
				const title_link = document.createElement('a');
				title_link.innerText = obj.title;
				title_link.href = obj.original_link;
				title_link.target = '_blank';
				title.appendChild(title_link);
				entry.appendChild(title);

				const date = document.createElement('td');
				var d = new Date(obj.downloaded_at * 1000);
				var formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5);
				date.innerText = formatted_date;
				entry.append(date);

				table.appendChild(entry);
			};
		})
		.catch(e => {
			if (e === 401) {
				window.location.href = '/';
			};
		});
};

function clearHistory() {
	fetch(`/api/activity/history?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		// catch errors
		if (!response.ok) {
			return Promise.reject(response.status);
		};
		
		fillHistory();
	})
	.catch(e => {
		if (e == 401) {
			window.location.href = '/';
		};
	});
};

// code run on load
const api_key = sessionStorage.getItem('api_key');

fillHistory();

document.getElementById('refresh-button').addEventListener('click', e => fillHistory());
document.getElementById('clear-button').addEventListener('click', e => clearHistory());
