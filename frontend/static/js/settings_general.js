function fillSettings(data) {
	document.getElementById('bind-address-input').value = data.host;
	document.getElementById('port-input').value = data.port;
	document.getElementById('password-input').value = data.auth_password;
	document.getElementById('api-input').innerText = api_key;
	document.getElementById('cv-input').value = data.comicvine_api_key;
	document.getElementById('log-level-input').value = data.log_level;
};

function saveSettings() {
	const data = {
		'host': document.getElementById('bind-address-input').value,
		'port': document.getElementById('port-input').value,
		'auth_password': document.getElementById('password-input').value,
		'comicvine_api_key': document.getElementById('cv-input').value,
		'log_level': document.getElementById('log-level-input').value
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

function generateApiKey() {
	fetch(`/api/settings/api_key?api_key=${api_key}`, {
		'method': 'POST'
	})
	.then(response => {
		return response.json();
	})
	.then(json => {
		sessionStorage.setItem('api_key', json.result.api_key);
		document.getElementById('api-input').innerText = json.result.api_key;
		api_key = json.result.api_key;
	});
};

// code run on load

let api_key = sessionStorage.getItem('api_key');

fetch(`/api/settings?api_key=${api_key}`)
.then(response => {
	return response.json();
})
.then(json => {
	fillSettings(json.result);
});

document.getElementById('save-button').addEventListener('click', e => saveSettings());
document.getElementById('generate-api').addEventListener('click', e => generateApiKey());
