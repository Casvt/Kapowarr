var offset = 0;

function fillHistory(api_key) {
	fetch(`${url_base}/api/activity/history?api_key=${api_key}&offset=${offset}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#history');
		table.innerHTML = '';
		json.result.forEach(obj => {
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
			let d = new Date(obj.downloaded_at * 1000);
			let formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5);
			date.innerText = formatted_date;
			entry.append(date);
	
			table.appendChild(entry);
		})
	});
};

function clearHistory(api_key) {
	fetch(`${url_base}/api/activity/history?api_key=${api_key}`, {
		'method': 'DELETE'
	});
	offset = 0;
	document.querySelector('#page-number').innerText = 'Page 1';
	document.querySelector('#history').innerHTML = '';
};

function reduceOffset(api_key) {
	if (offset === 0) return;
	offset--;
	document.querySelector('#page-number').innerText = `Page ${offset + 1}`;
	fillHistory(api_key);
};

function increaseOffset(api_key) {
	if (document.querySelector('#history').innerHTML === '') return;
	offset++;
	document.querySelector('#page-number').innerText = `Page ${offset + 1}`;
	fillHistory(api_key);
};

// code run on load
usingApiKey()
.then(api_key => {
	fillHistory(api_key);
	addEventListener('#refresh-button', 'click', e => fillHistory(api_key));
	addEventListener('#clear-button', 'click', e => clearHistory(api_key));
	addEventListener('#previous-page', 'click', e => reduceOffset(api_key));
	addEventListener('#next-page', 'click', e => increaseOffset(api_key));
});
