function fillSettings(api_key) {
	fetch(`${url_base}/api/settings?api_key=${api_key}`)
	.then(response => response.json())
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
	fetch(`${url_base}/api/settings?api_key=${api_key}`, {
		'method': 'PUT',
		'body': JSON.stringify(data),
		'headers': {'Content-Type': 'application/json'}
	})
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
	fetch(`${url_base}/api/settings/api_key?api_key=${api_key}`, {
		'method': 'POST'
	})
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
	addEventListener('#save-button', 'click', e => saveSettings(api_key));
	addEventListener('#generate-api', 'click', e => generateApiKey(api_key));
});

addEventListener('#theme-input', 'change', e => {
	const value = document.querySelector('#theme-input').value;
	setLocalStorage({'theme': value});
	if (value === 'dark')
		document.querySelector(':root').classList.add('dark-mode');
	else if (value === 'light')
		document.querySelector(':root').classList.remove('dark-mode');
});
