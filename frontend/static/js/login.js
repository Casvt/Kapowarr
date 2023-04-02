function registerLogin(api_key) {
	sessionStorage.setItem('api_key', api_key);
	parameters = new URLSearchParams(window.location.search);
	redirect_value = parameters.get('redirect');
	if (redirect_value !== null) {
		window.location.href = redirect_value;
	} else {
		window.location.href = '/';
	};
	return;
};

function login() {
	const error = document.getElementById('error-message');
	error.classList.add('hidden');
	const password_input = document.getElementById('password-input');
	const password = password_input.value;
	password_input.value = '';
	fetch(`/api/auth?password=${password}`, {
		'method': 'POST'
	})
	.then(response => {
		// catch errors
		if (!response.ok) {
			return Promise.reject(response.status);
		};
		
		return response.json();
	})
	.then(json => registerLogin(json.result.api_key))
	.catch(e => {
		// Login failed
		error.classList.remove('hidden');
	})
}

// code run on load

fetch('/api/auth', {
	'method': 'POST'
})
.then(response => {
	// catch errors
	if (!response.ok) {
		return Promise.reject(response.status);
	};
	return response.json();
})
.then(json => registerLogin(json.result.api_key))
.catch(e => {});

document.getElementById('login-form').setAttribute('action', 'javascript:login();');
