//
// Filling data
//
function addQueueEntry(api_key, obj) {
	const table = document.getElementById('queue');

	const entry = document.createElement('tr');
	entry.classList.add('queue-entry');
	entry.id = `d-${obj.id}`;

	const status = document.createElement('td');
	status.classList.add('status-column');
	status.innerText = obj.status.charAt(0).toUpperCase() + obj.status.slice(1);
	entry.appendChild(status);

	const title = document.createElement('td');
	const title_link = document.createElement('a');
	title_link.innerText = obj.title;
	title_link.href = obj.page_link;
	title_link.target = '_blank';
	title.appendChild(title_link);
	entry.appendChild(title);

	const source = document.createElement('td');
	source.classList.add('status-column');
	source.innerText = obj.source.charAt(0).toUpperCase() + obj.source.slice(1);
	entry.appendChild(source);

	const size = document.createElement('td');
	size.classList.add('number-column');
	size.innerText = convertSize(obj.size);
	entry.append(size);

	const speed = document.createElement('td');
	speed.classList.add('number-column');
	speed.innerText = (Math.round(obj.speed / 100000) / 10) + 'MB/s';
	entry.append(speed);

	const progress = document.createElement('td');
	progress.classList.add('number-column');
	if (obj.size === -1)
		progress.innerText = convertSize(obj.progress);
	else
		progress.innerText = (Math.round(obj.progress * 10) / 10) + '%';
	entry.append(progress);

	const delete_entry = document.createElement('td');
	delete_entry.classList.add('option-column');
	const delete_button = document.createElement('button');
	delete_button.addEventListener('click', e => deleteEntry(obj.id, api_key));
	delete_entry.appendChild(delete_button);
	const delete_icon = document.createElement('img');
	delete_icon.src = `${url_base}/static/img/delete.svg`;
	delete_button.appendChild(delete_icon);
	entry.append(delete_entry);

	table.appendChild(entry);
};

function updateQueueEntry(obj) {
	const tr = document.querySelector(`#queue > tr#d-${obj.id}`);
	tr.querySelector('td:nth-child(1)').innerText = obj.status.charAt(0).toUpperCase() + obj.status.slice(1);
	tr.querySelector('td:nth-child(4)').innerText = convertSize(obj.size);
	tr.querySelector('td:nth-child(5)').innerText = (Math.round(obj.speed / 100000) / 10) + 'MB/s';
	tr.querySelector('td:nth-child(6)').innerText = obj.size === -1 ? convertSize(obj.progress) : (Math.round(obj.progress * 10) / 10) + '%';
};

function removeQueueEntry(id) {
	document.querySelector(`#queue > tr#d-${id}`).remove();
};

function fillQueue(api_key) {
	fetch(`${url_base}/api/activity/queue?api_key=${api_key}`)
		.then(response => {
			if (!response.ok) return Promise.reject(response.status);
			return response.json();
		})
		.then(json => {
			const table = document.getElementById('queue');
			table.innerHTML = '';
			json.result.forEach(obj => addQueueEntry(api_key, obj));
		})
		.catch(e => {
			if (e === 401) window.location.href = `${url_base}/`;
		});
};

//
// Actions
//
function deleteEntry(id, api_key) {
	fetch(`${url_base}/api/activity/queue/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillQueue(api_key);
	socket.on('queue_added', data => addQueueEntry(api_key, data));
	socket.on('queue_status', updateQueueEntry);
	socket.on('queue_ended', data => removeQueueEntry(data.id));
	addEventListener('#refresh-button', 'click', e => fillQueue(api_key));
});
