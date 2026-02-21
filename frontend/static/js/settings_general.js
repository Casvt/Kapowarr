function fillSettings(api_key) {
	fetchAPI('/settings', api_key)
	.then(json => {
		document.querySelector('#bind-address-input').value = json.result.host;
		document.querySelector('#port-input').value = json.result.port;
		document.querySelector('#url-base-input').value = json.result.url_base;
		document.querySelector('#username-input').value = json.result.auth_username;
		document.querySelector('#password-input').value = json.result.auth_password;
		document.querySelector('#api-input').value = api_key;
		document.querySelector('#proxy-type-input').value = json.result.proxy_type || '';
		document.querySelector('#proxy-host-input').value = json.result.proxy_host;
		document.querySelector('#proxy-port-input').value = json.result.proxy_port;
		document.querySelector('#proxy-username-input').value = json.result.proxy_username;
		document.querySelector('#proxy-password-input').value = json.result.proxy_password;
		document.querySelector('#proxy-ignored-addresses-input').value = json.result.proxy_ignored_addresses.join(',');
		document.querySelector('#cv-input').value = json.result.comicvine_api_key;
		document.querySelector('#flaresolverr-input').value = json.result.flaresolverr_base_url;
		document.querySelector('#log-level-input').value = json.result.log_level;
		
		if (json.result.auth_username && json.result.auth_password) {
			document.querySelector('#auth-toggle').value = 'username-password';
		} else if (json.result.auth_password) {
			document.querySelector('#auth-toggle').value = 'password';
		};
	});
	document.querySelector('#theme-input').value = getLocalStorage('theme')['theme'];
};

function saveSettings(api_key) {
	document.querySelector("#save-button p").innerText = 'Saving';
	document.querySelector('#proxy-host-input').classList.remove('error-input');
	document.querySelector('#proxy-username-input').classList.remove('error-input');
	document.querySelector('#proxy-password-input').classList.remove('error-input');
	document.querySelector('#cv-input').classList.remove('error-input');
	document.querySelector("#flaresolverr-input").classList.remove('error-input');

	let proxyIgnoredAddresses = document.querySelector('#proxy-ignored-addresses-input').value.split(',');
	if (proxyIgnoredAddresses[0] === '') {
		proxyIgnoredAddresses = []
	}
	const data = {
		'host': document.querySelector('#bind-address-input').value,
		'port': parseInt(document.querySelector('#port-input').value),
		'url_base': document.querySelector('#url-base-input').value,
		'auth_username': '',
		'auth_password': '',
		'proxy_type': document.querySelector('#proxy-type-input').value || null,
		'proxy_host': document.querySelector('#proxy-host-input').value,
		'proxy_port': parseInt(document.querySelector('#proxy-port-input').value),
		'proxy_username': document.querySelector('#proxy-username-input').value,
		'proxy_password': document.querySelector('#proxy-password-input').value,
		'proxy_ignored_addresses': proxyIgnoredAddresses,
		'comicvine_api_key': document.querySelector('#cv-input').value,
		'flaresolverr_base_url': document.querySelector('#flaresolverr-input').value,
		'log_level': parseInt(document.querySelector('#log-level-input').value)
	};
	
	const auth_toggle = document.querySelector('#auth-toggle');
	if (auth_toggle.value === 'username-password')
		data.auth_username = document.querySelector('#username-input').value;

	if (auth_toggle.value === 'username-password' || auth_toggle.value === 'password')
		data.auth_password = document.querySelector('#password-input').value;

	sendAPI('PUT', '/settings', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		document.querySelector("#save-button p").innerText = 'Saved';
	})
	.catch(async e => {
		document.querySelector("#save-button p").innerText = 'Failed';
		const json = await e.json();
		if (json.error === 'InvalidComicVineApiKey')
			document.querySelector('#cv-input').classList.add('error-input');

		else if (
			json.error === "InvalidKeyValue"
			&& json.result.key === "proxy_host"
		)
			document.querySelector('#proxy-host-input').classList.add('error-input');

		else if (
			json.error === "InvalidKeyValue"
			&& json.result.key === "proxy_username"
		) {
			document.querySelector('#proxy-username-input').classList.add('error-input');
			document.querySelector('#proxy-password-input').classList.add('error-input');
		}

		else if (
			json.error === "InvalidKeyValue"
			&& json.result.key === "flaresolverr_base_url"
		)
			document.querySelector("#flaresolverr-input").classList.add('error-input');

		else
			console.log(json.error);
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
	document.querySelector('#download-logs-button').href =
		`${url_base}/api/system/logs?api_key=${api_key}`;
});

document.querySelector('#theme-input').onchange = e => {
	const value = document.querySelector('#theme-input').value;
	setLocalStorage({'theme': value});
	if (value === 'dark')
		document.querySelector(':root').classList.add('dark-mode');
	else if (value === 'light')
		document.querySelector(':root').classList.remove('dark-mode');
};
