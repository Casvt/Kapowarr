async function usingApiKey(redirect=true) {
	const api_key = sessionStorage.getItem('api_key');
	if (api_key === null) {

		return fetch(`/api/auth`, {'method': 'POST'})
			.then(response => {
				if (!response.ok) return Promise.reject(response.status);
				return response.json();
			})
			.then(json => {
				sessionStorage.setItem('api_key', json.result.api_key);
				return json.result.api_key;
			})
			.catch(e => {
				if (e === 401) {
					if (redirect) window.location.href = `/login?redirect=${window.location.pathname}`;
					else return null;
				} else {
					console.log(e);
					return null;
				};
			})

	} else {
		return api_key;
	};
};

