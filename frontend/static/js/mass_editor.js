const windows = {
	loading: document.querySelector('#loading-window'),
	list: document.querySelector('#list-window')
};

function fillVolumeList(api_key) {
	document.querySelector('#selectall-input').checked = false;
	const table = document.querySelector('.volume-list');
	table.innerHTML = '';
	fetch(`${url_base}/api/volumes?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		json.result.forEach(vol => {
			const entry = document.createElement('tr');
			entry.dataset.id = vol.id;
			
			const select_container = document.createElement('td');
			const select = document.createElement('input');
			select.type = 'checkbox';
			select.checked = false;
			select_container.appendChild(select);
			entry.appendChild(select_container);

			const title = document.createElement('td');
			title.innerText = vol.title;
			entry.appendChild(title);

			const year = document.createElement('td');
			year.innerText = vol.year;
			entry.appendChild(year);

			const volume_number = document.createElement('td');
			volume_number.innerText = vol.volume_number;
			entry.appendChild(volume_number);

			table.appendChild(entry);
		});
	});
};

function toggleSelection() {
	const checked = document.querySelector('#selectall-input').checked;
	document.querySelectorAll('.volume-list input[type="checkbox"]')
		.forEach(c => c.checked = checked);
};

function runAction(api_key, action) {
	windows.list.classList.add('hidden');
	windows.loading.classList.remove('hidden');

	const volume_ids = [...document.querySelectorAll(
		'.volume-list input[type="checkbox"]:checked'
	)].map(v => parseInt(v.parentNode.parentNode.dataset.id))
	
	fetch(`${url_base}/api/masseditor?api_key=${api_key}`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify({
			'volume_ids': volume_ids,
			'action': action
		})
	})
	.then(response => {
		fillVolumeList(api_key);
		windows.loading.classList.add('hidden');
		windows.list.classList.remove('hidden');
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillVolumeList(api_key);
	addEventListener('.action-bar > button', 'click',
		e => runAction(api_key, e.target.dataset.action)
	);
});

addEventListener('#selectall-input', 'change', e => toggleSelection());
