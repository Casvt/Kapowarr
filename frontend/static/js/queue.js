// 
// Filling data
// 
function fillQueue(api_key) {
	fetch(`/api/activity/queue?api_key=${api_key}`)
		.then(response => {
			if (!response.ok) return Promise.reject(response.status);
			return response.json();
		})
		.then(json => {
			const table = document.getElementById('queue');
			table.innerHTML = '';
			json.result.forEach(obj => {
				const entry = document.createElement('tr');
				entry.classList.add('queue-entry');
				entry.id = obj.id;

				const status = document.createElement('td');
				status.classList.add('status-column');
				status.innerText = obj.status.charAt(0).toUpperCase() + obj.status.slice(1);
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
				delete_entry.classList.add('option-column');
				const delete_button = document.createElement('button');
				delete_button.addEventListener('click', e => deleteEntry(obj.id, api_key));
				delete_entry.appendChild(delete_button);
				const delete_icon = document.createElement('img');
				delete_icon.src = '/static/img/delete.svg';
				delete_button.appendChild(delete_icon);
				entry.append(delete_entry);

				table.appendChild(entry);
			});
		})
		.catch(e => {
			if (e === 401) window.location.href = '/';
		});
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
};

// 
// Actions
// 
function deleteEntry(id, api_key) {
	fetch(`/api/activity/queue/${id}?api_key=${api_key}`, {
		'method': 'DELETE'
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillQueue(api_key);
	setInterval(() => fillQueue(api_key), 1500);
	addEventListener('#refresh-button', 'click', e => fillQueue(api_key));
});
