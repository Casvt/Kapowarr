function fillList() {
	fetch(`/api/blocklist?api_key=${api_key}`)
	.then(response => { return response.json(); })
	.then(json => {
		const table = document.getElementById('blocklist');
		table.innerHTML = '';
		for (i = 0; i < json.result.length; i++) {
			const obj = json.result[i];

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
			delete_button.addEventListener('click', e => deleteEntry(obj.id));
			delete_entry.appendChild(delete_button);
			delete_entry.classList.add('option-column');
			entry.append(delete_entry);

			table.appendChild(entry);
		};
	});
};

function deleteEntry(id) {
	fetch(`/api/blocklist/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		fillList();
	});
};

function clearList() {
	fetch(`/api/blocklist?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		fillList();
	});
};

// code run on load
const api_key = sessionStorage.getItem('api_key');

fillList();

document.getElementById('clear-button').addEventListener('click', e => clearList());
document.getElementById('refresh-button').addEventListener('click', e => fillList());