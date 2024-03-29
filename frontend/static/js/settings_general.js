function fillSettings(api_key) {
	fetchAPI('/settings', api_key)
	.then(json => {
		document.querySelector('#bind-address-input').value = json.result.host;
		document.querySelector('#port-input').value = json.result.port;
		document.querySelector('#url-base-input').value = json.result.url_base;
		document.querySelector('#password-input').value = json.result.auth_password;
		document.querySelector('#api-input').value = api_key;
		document.querySelector('#cv-input').value = json.result.comicvine_api_key;
		document.querySelector('#log-level-input').value = json.result.log_level;
	});
	document.querySelector('#theme-input').value = getLocalStorage('theme')['theme'];
};

function saveSettings(api_key) {
	document.querySelector('#cv-input').classList.remove('error-input');
	const data = {
		'host': document.querySelector('#bind-address-input').value,
		'port': document.querySelector('#port-input').value,
		'url_base': document.querySelector('#url-base-input').value,
		'auth_password': document.querySelector('#password-input').value,
		'comicvine_api_key': document.querySelector('#cv-input').value,
		'log_level': parseInt(document.querySelector('#log-level-input').value)
	};
	sendAPI('PUT', '/settings', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.error !== null) return Promise.reject(json);
	})
	.catch(e => {
		if (e.error === 'InvalidComicVineApiKey')
			document.querySelector('#cv-input').classList.add('error-input');
		else
			console.log(e.error);
	});
};

function generateApiKey(api_key) {
	sendAPI('POST', '/settings/api_key', api_key)
	.then(response => response.json())
	.then(json => {
		setLocalStorage({'api_key': json.result.api_key});
		document.querySelector('#api-input').innerText = json.result.api_key;
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	document.querySelector('#save-button').onclick = e => saveSettings(api_key);
	document.querySelector('#generate-api').onclick = e => generateApiKey(api_key);
});

document.querySelector('#theme-input').onchange = e => {
	const value = document.querySelector('#theme-input').value;
	setLocalStorage({'theme': value});
	if (value === 'dark')
		document.querySelector(':root').classList.add('dark-mode');
	else if (value === 'light')
		document.querySelector(':root').classList.remove('dark-mode');
};
