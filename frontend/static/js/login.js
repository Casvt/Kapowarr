function redirect() {
	parameters = new URLSearchParams(window.location.search);
	redirect_value = parameters.get('redirect') || '/';
	window.location.href = redirect_value;
}

function registerLogin(api_key) {
	sessionStorage.setItem('api_key', api_key);
	redirect();
};

function login() {
	const error = document.querySelector('#error-message');
	error.classList.add('hidden');

	const password_input = document.querySelector('#password-input');
	fetch(`/api/auth?password=${password_input.value}`, {'method': 'POST'})
	.then(response => {
		if (!response.ok) return Promise.reject(response.status);
		return response.json();
	})
	.then(json => registerLogin(json.result.api_key))
	.catch(e => {
		// Login failed
		if (e === 401) {
			error.classList.remove('hidden');
		} else {
			console.log(e);
		};
	});
};

// code run on load

usingApiKey(false)
.then(api_key => {
	if (api_key) redirect();
})

document.querySelector('#login-form').setAttribute('action', 'javascript:login();');
