var offset = 0;

function fillList(api_key) {
	fetch(`/api/blocklist?api_key=${api_key}&offset=${offset}`)
	.then(response => response.json())
	.then(json => {
		const table = document.querySelector('#blocklist');
		table.innerHTML = '';
		json.result.forEach(obj => {
			const entry = document.createElement('tr');
			entry.classList.add('list-entry');
			entry.id = obj.id;

			const link_container = document.createElement('td');
			link_container.classList.add('link-column');
			const link = document.createElement('a');
			link.href = obj.link;
			link.innerText = obj.link;
			link.setAttribute('target', '_blank');
			link_container.appendChild(link);
			entry.append(link_container);
			
			const reason = document.createElement('td');
			reason.classList.add('reason-column');
			reason.innerText = obj.reason;
			entry.appendChild(reason);

			const date = document.createElement('td');
			date.classList.add('date-column');
			var d = new Date(obj.added_at * 1000);
			var formatted_date = d.toLocaleString('en-CA').slice(0,10) + ' ' + d.toTimeString().slice(0,5)
			date.innerText = formatted_date;
			entry.append(date);

			const delete_entry = document.createElement('td');
			const delete_button = document.createElement('button');
			const delete_icon = document.createElement('img');
			delete_icon.src = '/static/img/delete.svg';
			delete_icon.classList.add('delete-entry-icon');
			delete_button.appendChild(delete_icon);
			delete_button.classList.add('delete-entry');
			delete_button.addEventListener('click', e => deleteEntry(obj.id, api_key));
			delete_entry.appendChild(delete_button);
			delete_entry.classList.add('option-column');
			entry.append(delete_entry);

			table.appendChild(entry);
		});
	});
};

function deleteEntry(id, api_key) {
	fetch(`/api/blocklist/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => fillList(api_key));
};

function clearList(api_key) {
	fetch(`/api/blocklist?api_key=${api_key}`, {
		'method': 'DELETE'
	});
	offset = 0;
	document.querySelector('#page-number').innerText = 'Page 1';
	document.querySelector('#blocklist').innerHTML = '';
};

function reduceOffset(api_key) {
	if (offset === 0) return;
	offset--;
	document.querySelector('#page-number').innerText = `Page ${offset + 1}`;
	fillList(api_key);
};

function increaseOffset(api_key) {
	if (document.querySelector('#blocklist').innerHTML === '') return;
	offset++;
	document.querySelector('#page-number').innerText = `Page ${offset + 1}`;
	fillList(api_key);
};

// code run on load
usingApiKey()
.then(api_key => {
	fillList(api_key);
	addEventListener('#clear-button', 'click', e => clearList(api_key));
	addEventListener('#refresh-button', 'click', e => fillList(api_key));
	addEventListener('#previous-page', 'click', e => reduceOffset(api_key));
	addEventListener('#next-page', 'click', e => increaseOffset(api_key));
});
