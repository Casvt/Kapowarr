const StatEls = {
	version: document.querySelector('#version'),
	python_version: document.querySelector('#python-version'),
	database_version: document.querySelector('#database-version'),
	database_location: document.querySelector('#database-location'),
	data_folder: document.querySelector('#data-folder'),
	os: document.querySelector('#os'),
	runs_64bit: document.querySelector('#runs-64bit'),
	status_checks: {
		list: document.querySelector('#status-checks-list'),
		ok: document.querySelector('#status-checks-ok')
	},
	buttons: {
		copy: document.querySelector('#copy-about'),
		restart: document.querySelector('#restart-button'),
		shutdown: document.querySelector('#shutdown-button')
	}
};

const about_table = `
| Key| Value |
|--------|--------|
| Kapowarr version | {k_version} |
| Python version | {p_version} |
| Database version | {d_version} |
| Database location | {d_loc} |
| Data folder | {folder} |
| OS | {os} |
| Can run 64bit | {runs_64bit} |

`;

const subtypeLabels = {
	'search_volumes': 'Searching volumes',
	'fetch_volume': 'Fetching volume metadata',
	'fetch_issues': 'Fetching issue metadata'
};

const statusDescriptions = {
	'cv_rate_limit': 'ComicVine rate limit reached'
};

function loadStatusChecks(api_key) {
	fetchAPI('/system/status/checks', api_key)
	.then(json => {
		StatEls.status_checks.list.innerHTML = '';
		if (json.result.length === 0) {
			hide([StatEls.status_checks.list],
				[StatEls.status_checks.ok]);
		} else {
			hide([StatEls.status_checks.ok],
				[StatEls.status_checks.list]);
			json.result.forEach(entry => {
				const item = document.createElement('div');
				item.classList.add('status-check-item');

				const text = document.createElement('p');
				const desc = statusDescriptions[entry.type]
					|| entry.description;
				const subs = entry.subtypes
					.map(s => subtypeLabels[s] || s)
					.join(', ');
				text.innerText = `${desc}: ${subs}`;

				const clearBtn = document.createElement('button');
				clearBtn.innerText = 'Clear';
				clearBtn.onclick = e => {
					sendAPI(
						'DELETE',
						'/system/status/checks',
						api_key,
						{type: entry.type}
					).then(() => loadStatusChecks(api_key));
				};

				item.appendChild(text);
				item.appendChild(clearBtn);
				StatEls.status_checks.list.appendChild(item);
			});
		};
	})
	.catch(e => console.log(e));
};

// code run on load

usingApiKey()
.then(api_key => {
	loadStatusChecks(api_key);

	fetchAPI('/system/about', api_key)
	.then(json => {
		StatEls.version.innerText = json.result.version;
		StatEls.python_version.innerText = json.result.python_version;
		StatEls.database_version.innerText = json.result.database_version;
		StatEls.database_location.innerText = json.result.database_location;
		StatEls.data_folder.innerText = json.result.data_folder;
		StatEls.os.innerText = json.result.os;
		StatEls.runs_64bit.innerText = json.result.runs_64bit ? 'Yes' : 'No';
		
		StatEls.buttons.copy.onclick = e => {
			copy(about_table
				.replace('{k_version}', json.result.version)
				.replace('{p_version}', json.result.python_version)
				.replace('{d_version}', json.result.database_version)
				.replace('{d_loc}', json.result.database_location)
				.replace('{folder}', json.result.data_folder)
				.replace('{os}', json.result.os)
				.replace('{runs_64bit}', json.result.runs_64bit)
			);
		};
	});
	StatEls.buttons.restart.onclick =
		e => {
			StatEls.buttons.restart.innerText = 'Restarting';
			socket.disconnect();
			sendAPI('POST', '/system/power/restart', api_key);
			setTimeout(() => window.location.reload(), 1000);
		};
	StatEls.buttons.shutdown.onclick =
		e => {
			StatEls.buttons.shutdown.innerText = 'Shutting down';
			socket.disconnect();
			sendAPI('POST', '/system/power/shutdown', api_key);
			setTimeout(() => window.location.reload(), 1000);
		};
});


function copy(text) {
	range = document.createRange();
	selection = document.getSelection();

	let container = document.createElement("span");
	container.textContent = text;
	container.ariaHidden = true;
	container.style.all = "unset";
	container.style.position = "fixed";
	container.style.top = 0;
	container.style.clip = "rect(0, 0, 0, 0)";
	container.style.whiteSpace = "pre";
	container.style.userSelect = "text";
	
	document.body.appendChild(container);
	
	try {
		range.selectNodeContents(container);
		selection.addRange(range);
		document.execCommand("copy");
		StatEls.buttons.copy.innerText = 'Copied';
	}
	catch (err) {
		// Failed
		StatEls.buttons.copy.innerText = 'Failed';
	}
	finally {
		selection.removeAllRanges();
		document.body.removeChild(container);
	}
}
