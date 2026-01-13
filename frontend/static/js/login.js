function loadFields() {
	fetch(`${url_base}/api/public`)
	.then(response => response.json())
	.then(json => {
		const am = json.result.authentication_method;
		if (am == 1) {
			document.querySelector("#username-input").remove();
			document.querySelector("#login-form").classList.remove('hidden');
			document.querySelector("#password-input").focus();
		} else {
			document.querySelector("#login-form").classList.remove('hidden');
		};
	});
};

function login() {
	const error = document.querySelector('#error-message');
	error.classList.add('hidden');

	const password_input = document.querySelector('#password-input');
	const data = {
		'password': password_input.value
	};
	
	const username_input = document.querySelector('#username-input');
	if (username_input !== null)
		data.username = username_input.value
	
	fetch(`${url_base}/api/auth`, {
		'method': 'POST',
		'headers': {'Content-Type': 'application/json'},
		'body': JSON.stringify(data)
	})
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

function registerLogin(api_key) {
	const data = JSON.parse(localStorage.getItem('kapowarr'));
	data.api_key = api_key;
	data.last_login = Date.now();
	localStorage.setItem('kapowarr', JSON.stringify(data));
	redirect();
};

function redirect() {
	parameters = new URLSearchParams(window.location.search);
	redirect_value = parameters.get('redirect') || `${url_base}/`;
	window.location.href = redirect_value;
};

// code run on load

const url_base = document.querySelector('#url_base').dataset.value;

usingApiKey(false)
.then(api_key => {
	if (api_key)
		redirect();
	else
		loadFields();
})

if (JSON.parse(localStorage.getItem('kapowarr') || {'theme': 'light'})['theme'] === 'dark')
	document.querySelector(':root').classList.add('dark-mode');

document.querySelector('#login-form').action = 'javascript:login();';
