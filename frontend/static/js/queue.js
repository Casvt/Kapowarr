function fillQueue() {
	fetch(`/api/activity/queue?api_key=${api_key}`)
		.then(response => {
			// catch errors
			if (!response.ok) {
				return Promise.reject(response.status);
			};

			return response.json();
		})
		.then(json => {
			const table = document.getElementById('queue');
			table.innerHTML = '';
			for (i = 0; i < json.result.length; i++) {
				const obj = json.result[i];

				const entry = document.createElement('tr');
				entry.classList.add('queue-entry');
				entry.id = obj.id;

				const status = document.createElement('td');
				status.classList.add('status-column');
				status.innerText = obj.status;
				entry.appendChild(status);

				const title = document.createElement('td');
				const title_link = document.createElement('a');
				title_link.innerText = obj.title;
				title_link.href = obj.original_link;
				title_link.target = '_blank';
				title.appendChild(title_link);
				entry.appendChild(title);

				const size = document.createElement('td');
				size.classList.add('number-column');
				size.innerText = convertSize(obj.size);
				entry.append(size);
				
				const speed = document.createElement('td');
				speed.classList.add('number-column');
				speed.innerText = (Math.round(obj.speed * 0.0001) / 100) + 'MB/s';
				entry.append(speed);

				const progress = document.createElement('td');
				progress.classList.add('number-column');
				progress.innerText = obj.progress + '%';
				entry.append(progress);
				
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
		})
		.catch(e => {
			if (e === 401) {
				window.location.href = '/';
			};
		});
};

function deleteEntry(id) {
	fetch(`/api/activity/queue/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	})
};

function convertSize(size) {
	const sizes = {
		'B': 1,
		'KB': 1000,
		'MB': 1000000,
		'GB': 1000000000,
		'TB': 1000000000000
	};
	for (const [term, division_size] of Object.entries(sizes)) {
		let resulting_size = size / division_size
		if (0 <= resulting_size && resulting_size <= 1000) {
			size = (
				Math.round(
					(size / division_size * 100)
				) / 100
			).toString() + term;
			return size;
		};
	};
	size = (
		Math.round(
			(size / sizes.TB * 100)
		) / 100
	).toString() + 'TB';
	return size;
}

// code run on load
const api_key = sessionStorage.getItem('api_key');

fillQueue();
setInterval(fillQueue, 1500);

document.getElementById('refresh-button').addEventListener('click', e => fillQueue());
