function fillSettings(data) {
	document.getElementById('download-folder-input').value = data.download_folder;
};

function saveSettings() {
	const data = {
		'download_folder': document.getElementById('download-folder-input').value
	};
	fetch(`/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
	.then(response => {
		return response.json();
	})
	.then(json => {
		// catch errors
		if (!json.error === null) {
			return Promise.reject(json);
		};
	})
	.catch(e => {
		console.log(e.error);
	});
};

// code run on load

const api_key = sessionStorage.getItem('api_key');

fetch(`/api/settings?api_key=${api_key}`)
.then(response => {
	return response.json();
})
.then(json => {
	fillSettings(json.result);
});
