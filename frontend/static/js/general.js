function showNav(e) {
	document.getElementById('nav').classList.toggle('show-nav');
}

function fillTaskQueue() {
	fetch(`/api/system/tasks?api_key=${sessionStorage.getItem('api_key')}`, {
		'priority': 'low'
	})
	.then(response => {
		if (!response.ok) {
			return Promise.reject(response.status);
		};
		return response.json();
	})
	.then(json => {
		const table = document.getElementById('task-queue');
		table.innerHTML = '';
		if (json.result.length >= 1) {
			const entry = document.createElement('p');
			entry.innerText = json.result[0].message;
			table.appendChild(entry);
		};
	})
	.catch(e => {
		if (e === 401) {
			window.location.href = `/login?redirect=${window.location.pathname}`;
		}
	})
}

// code run on load
setTimeout(fillTaskQueue, 200);
setInterval(fillTaskQueue, 2000);

document.getElementById('nav-button').addEventListener('click', e => showNav(e))