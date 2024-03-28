function fillSettings(api_key) {
	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#download-folder-input').value = json.result.download_folder;
		document.querySelector('#seeding-handling-input').value = json.result.seeding_handling;
		document.querySelector('#delete-torrents-input').checked = json.result.delete_completed_torrents;
		fillPref(json.result.service_preference);
	});
};

function saveSettings(api_key) {
	document.querySelector('#download-folder-input').classList.remove('error-input');
	const data = {
		'download_folder': document.querySelector('#download-folder-input').value,
		'seeding_handling': document.querySelector('#seeding-handling-input').value,
		'delete_completed_torrents': document.querySelector('#delete-torrents-input').checked,
		'service_preference': [...document.querySelectorAll('#pref-table select')].map(e => e.value)
	};
	fetch(`${url_base}/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
	})
	.catch(e => {
		if (e === 404) {
			document.querySelector('#download-folder-input').classList.add('error-input');
		} else {
			console.log(e);
		};
	});
};

//
// Empty download folder
//
function emptyFolder(api_key) {
	fetch(`${url_base}/api/activity/folder?api_key=${api_key}`, {
		'method': 'DELETE'
	})
	.then(response => {
		document.querySelector('#empty-download-folder').innerText = 'Done';
	});
};

//
// Service preference
//
function fillPref(pref) {
	const selects = document.querySelectorAll('#pref-table select');
	for (let i = 0; i < pref.length; i++) {
		const service = pref[i];
		const select = selects[i];
		select.addEventListener('change', updatePrefOrder);
		pref.forEach(option => {
			const entry = document.createElement('option');
			entry.value = option;
			entry.innerText = option.charAt(0).toUpperCase() + option.slice(1);
			if (option === service)
				entry.selected = true;
			select.appendChild(entry);
		});
	};
};

function updatePrefOrder(e) {
	const other_selects = document.querySelectorAll(
		`#pref-table select:not([data-place="${e.target.dataset.place}"])`
	);
	// Find select that has the value of the target select
	for (let i = 0; i < other_selects.length; i++) {
		if (other_selects[i].value === e.target.value) {
			// Set it to old value of target select
			all_values = [...document.querySelector('#pref-table select').options].map(e => e.value)
			used_values = new Set([...document.querySelectorAll('#pref-table select')].map(s => s.value));
			open_value = all_values.filter(e => !used_values.has(e))[0];
			other_selects[i].value = open_value;
			break;
		};
	};
};

// code run on load
usingApiKey()
.then(api_key => {
	fillSettings(api_key);

	addEventListener('#save-button', 'click', e => saveSettings(api_key));
	addEventListener('#empty-download-folder', 'click', e => emptyFolder(api_key));
});
