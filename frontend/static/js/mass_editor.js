const EditorEls = {
	windows: {
		loading: document.querySelector('#loading-window'),
		list: document.querySelector('#list-window')
	},
	select_all: document.querySelector('#selectall-input'),
	volumes: document.querySelector('.volume-list'),
	action_bar: document.querySelector('.action-bar')
};

function fillVolumeList(api_key) {
	hide([EditorEls.windows.list], [EditorEls.windows.loading]);
	EditorEls.select_all.checked = false;
	EditorEls.volumes.innerHTML = '';

	fetchAPI('/volumes', api_key)
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

			const monitored = document.createElement('td');
			monitored.innerHTML = vol.monitored ? icons.monitored : icons.unmonitored;
			monitored.title = vol.monitored ? 'Monitored' : 'Unmonitored';
			entry.appendChild(monitored);

			EditorEls.volumes.appendChild(entry);
		});
		hide([EditorEls.windows.loading], [EditorEls.windows.list]);
	});
};

function toggleSelection() {
	const checked = EditorEls.select_all.checked;
	EditorEls.volumes.querySelectorAll('input[type="checkbox"]')
		.forEach(c => c.checked = checked);
};

function runAction(api_key, action, args={}) {
	hide([EditorEls.windows.list], [EditorEls.windows.loading]);

	const volume_ids = [...EditorEls.volumes.querySelectorAll(
		'input[type="checkbox"]:checked'
	)].map(v => parseInt(v.parentNode.parentNode.dataset.id))

	sendAPI('POST', '/masseditor', api_key, {}, {
		'volume_ids': volume_ids,
		'action': action,
		'args': args
	})
	.then(response => fillVolumeList(api_key));
};

// code run on load

usingApiKey()
.then(api_key => {
	fillVolumeList(api_key);

	EditorEls.action_bar.querySelectorAll('.action-divider > button').forEach(
		b => b.onclick = e => runAction(api_key, e.target.dataset.action)
	);
	EditorEls.action_bar.querySelector('button[data-action="delete"]').onclick =
		e => runAction(
			api_key,
			e.target.dataset.action,
			{
				'delete_folder': document.querySelector(
					'select[name="delete_folder"]'
				).value === "true"
			}
		);
});

EditorEls.select_all.onchange = e => toggleSelection();
