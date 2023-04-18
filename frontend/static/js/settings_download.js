function fillSettings(api_key) {
	fetch(`/api/settings?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#download-folder-input').value = json.result.download_folder;
	});
};

function saveSettings(api_key) {
	document.querySelector('#download-folder-input').classList.remove('error-input');
	const data = {
		'download_folder': document.querySelector('#download-folder-input').value
	};
	fetch(`/api/settings?api_key=${api_key}`, {
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

// code run on load
usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	addEventListener('#save-button', 'click', e => saveSettings(api_key))
});
