const brokenClientReasonMap = {
    connection_error: "Failed to connect",
    not_client_instance: "What was connected to was not the expected client",
    version_not_supported: "The version is not supported",
    failed_processing_response: "Got an unexpected response back",
    access_denied: "Access denied by client but not because of invalid credentials",
	invalid_credentials: "Failed to login with the given credentials"
}

function createGCAvoidLargeDownloadsInput(inputId) {
	const row = document.createElement('tr');
	const header = document.createElement('th');
	const label = document.createElement('label');
	label.innerText = 'Avoid Large Downloads';
	label.setAttribute('for', inputId);
	header.appendChild(label);
	row.appendChild(header)
	const container = document.createElement('td');
	const input = document.createElement('input');
	input.type = 'checkbox'
	input.id = inputId;
	container.appendChild(input);
	const description = document.createElement('p');
	description.innerText = "If a download on GetComics is larger than 400MB, then avoid downloading the file directly from the GetComics servers. Try all external services first. GetComics throttles the download speed after downloading 400MB of a file."
	container.appendChild(description)
	row.appendChild(container);
	return row;
}

const defaultServicePreference = [
	"Mega", "MediaFire",
	"WeTransfer", "Pixeldrain",
	"GetComics", "GetComics (torrent)"
]

function updatePrefOrder(e) {
	const otherSelects = document.querySelectorAll(
		`#pref-table select:not([data-place="${e.target.dataset.place}"])`
	);

	// Find select that has the value of the target select
	otherSelects.forEach(select => {
		if (select.value !== e.target.value)
			return;

		// Set it to old value of target select
		const usedValues = new Set([...document.querySelectorAll("#pref-table select")].map(s => s.value));
		const openValue = defaultServicePreference.filter(e => !usedValues.has(e))[0];
		select.value = openValue;
	});
}

function createGCServicePreferenceInput(inputId) {
	const row = document.createElement('tr');
	const header = document.createElement('th');
	const label = document.createElement('label');
	label.innerText = 'Service Preference';
	label.setAttribute('for', 'pref-1');
	header.appendChild(label);
	row.appendChild(header)

	const container = document.createElement('td');

	const prefTable = document.createElement("table");
	prefTable.id = "pref-table";
	prefTable.classList.add("short-table");
	const prefTableBody = document.createElement("tbody");
	prefTableBody.id = inputId;
	prefTable.appendChild(prefTableBody);

	defaultServicePreference.forEach((pref, idx) => {
		const prefEntry = document.createElement("tr");
		const prefHeader = document.createElement("th");
		prefHeader.innerText = idx + 1;
		prefEntry.appendChild(prefHeader);
		const prefContent = document.createElement("td");
		const prefSelect = document.createElement("select");
		prefSelect.id = `pref-${idx+1}`;
		prefSelect.dataset.place = idx + 1;
		prefSelect.onchange = updatePrefOrder;
		defaultServicePreference.forEach(serviceOption => {
			const option = document.createElement("option");
			option.value = serviceOption;
			option.innerText = serviceOption.charAt(0).toUpperCase() + serviceOption.slice(1);
			if (serviceOption === pref)
				option.selected = true;
			prefSelect.appendChild(option);
		});
		prefContent.appendChild(prefSelect);
		prefEntry.appendChild(prefContent);
		prefTableBody.appendChild(prefEntry);
	});
	container.appendChild(prefTable);
	
	const description = document.createElement('p');
	description.innerText = "The preference for services to download from when using GetComics as the source."
	container.appendChild(description)

	row.appendChild(container);
	return row;
}

function loadEditIndexer(apiKey, indexerId) {
	const form = document.querySelector('#edit-indexer-form tbody');
	form.dataset.id = indexerId;
	form.querySelectorAll(
		'tr:not(:has(input#edit-title-input, input#edit-enabled-input, input#edit-url-input))'
	).forEach(el => el.remove());
	document.querySelector('#test-indexer-edit').classList.remove(
		'show-success', 'show-fail'
	)
	hide([document.querySelector('#edit-error')]);

	fetchAPI(`/indexers/${indexerId}`, apiKey)
	.then(clientData => {
		const clientType = clientData.result.client_type;
		form.dataset.download_type = clientData.result.download_type;
		form.dataset.type = clientType;
		const clientOptions = clientData.result.required_tokens;

		form.querySelector('#edit-title-input').value =
			clientData.result.title || '';

		form.querySelector('#edit-enabled-input').checked =
			clientData.result.enabled;

		form.querySelector('#edit-url-input').value =
			clientData.result.url;

		if (clientOptions.includes('gc_avoid_large_downloads')) {
			const gcAvoidInput = createGCAvoidLargeDownloadsInput('edit-gc-avoid-input');
			gcAvoidInput.querySelector('input').checked =
				clientData.result.gc_avoid_large_downloads ?? true;
			form.appendChild(gcAvoidInput);
		};

		if (clientOptions.includes('gc_service_preference')) {
			const gcServicePreferenceInput = createGCServicePreferenceInput('edit-gc-service-preference-input');
			gcServicePreferenceInput.querySelectorAll("select").forEach((pref, idx) => {
				pref.value = clientData.result.gc_service_preference[idx];
			});
			form.appendChild(gcServicePreferenceInput);
		};

		showWindow('edit-indexer-window');
	});
};

function saveEditIndexer() {
	usingApiKey()
	.then(apiKey => {
		testEditIndexer(apiKey).then(result => {
			if (!result)
				return;

			const form = document.querySelector('#edit-indexer-form tbody');
			const indexerId = form.dataset.id;

			const prefTable = document.querySelectorAll("#pref-table select")
			let gcServicePreference = null
			if (prefTable)
				gcServicePreference = [...prefTable].map(e => e.value)

			const data = {
				title: form.querySelector('#edit-title-input').value,
				enabled: form.querySelector('#edit-enabled-input').checked,
				url: form.querySelector('#edit-url-input').value,
				gc_service_preference: gcServicePreference,
				gc_avoid_large_downloads: form.querySelector('#edit-gc-avoid-input')?.checked ?? null,
			};
			sendAPI('PUT', `/indexers/${indexerId}`, apiKey, {}, data)
			.then(response => {
				loadIndexers(apiKey);
				closeWindow();
			});
		});
	});
};

async function testEditIndexer(apiKey) {
	const error = document.querySelector('#edit-error');
	hide([error]);
	const form = document.querySelector('#edit-indexer-form tbody');
	const testButton = document.querySelector('#test-indexer-edit');
	testButton.classList.remove('show-success', 'show-fail');
	const data = {
		download_type: parseInt(form.dataset.download_type),
		client_type: form.dataset.type,
		url: form.querySelector('#edit-url-input').value
	};
	return await sendAPI('POST', '/indexers/test', apiKey, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.result.success)
			// Test successful
			testButton.classList.add('show-success');
		else {
			// Test failed
			testButton.classList.add('show-fail');
			error.innerText = brokenClientReasonMap[json.result.description];
			hide([], [error]);
		};
		return json.result.success;
	});
};

function deleteIndexer(apiKey) {
	const indexerId = document.querySelector('#edit-indexer-form tbody').dataset.id;
	sendAPI('DELETE', `/indexers/${indexerId}`, apiKey)
	.then(response => {
		loadIndexers(apiKey);
		closeWindow();
	});
};

function loadIndexerOptionList(apiKey, downloadType) {
	const table = document.querySelector('#choose-indexer-list');
	table.innerHTML = '';

	fetchAPI('/indexers/options', apiKey)
	.then(json => {
		Object.keys(json.result[downloadType]).forEach(clientType => {
			const entry = document.createElement('button');
			entry.innerText = clientType;
			entry.onclick = e => loadAddIndexer(apiKey, downloadType, clientType);
			table.appendChild(entry);
		});
		showWindow('choose-indexer-window');
	});
};

function loadAddIndexer(apiKey, downloadType, clientType) {
	const error = document.querySelector("#add-error");
	hide([error]);

	const form = document.querySelector('#add-indexer-form tbody');
	form.dataset.download_type = downloadType;
	form.dataset.type = clientType;
	form.querySelectorAll(
		'tr:not(:has(input#add-title-input, input#add-enabled-input, input#add-url-input))'
	).forEach(el => el.remove());
	document.querySelector('#test-indexer-add').classList.remove(
		'show-success', 'show-fail'
	)
	form.querySelectorAll(
		'#add-title-input, #add-enabled-input, #add-url-input'
	).forEach(el => el.value = '');

	fetchAPI('/indexers/options', apiKey)
	.then(json => {
		const clientOptions = json.result[downloadType][clientType];

		if (clientOptions.required_tokens.includes('gc_avoid_large_downloads'))
			form.appendChild(createGCAvoidLargeDownloadsInput('add-gc-avoid-input'));

		if (clientOptions.required_tokens.includes('gc_service_preference'))
			form.appendChild(createGCServicePreferenceInput('add-gc-service-preference-input'));

		showWindow('add-indexer-window');
	});
};

function saveAddIndexer() {
	const error = document.querySelector("#add-error");
	hide([error]);

	usingApiKey()
	.then(apiKey => {
		testAddIndexer(apiKey).then(result => {
			if (!result)
				return;

			const form = document.querySelector('#add-indexer-form tbody');
			
			const prefTable = document.querySelectorAll("#pref-table select")
			let gcServicePreference = null
			if (prefTable)
				gcServicePreference = [...prefTable].map(e => e.value)

			const data = {
				download_type: parseInt(form.dataset.download_type),
				client_type: form.dataset.type,
				title: form.querySelector('#add-title-input').value,
				enabled: form.querySelector('#add-enabled-input').checked,
				url: form.querySelector('#add-url-input').value,
				gc_service_preference: gcServicePreference,
				gc_avoid_large_downloads: form.querySelector('#add-gc-avoid-input')?.checked ?? null,
			};
			sendAPI('POST', '/indexers', apiKey, {}, data)
			.then(response => {
				loadIndexers(apiKey);
				closeWindow();
			})
			.catch(e => {
				if (e.status === 400) {
					// Only one instance allowed
					error.innerText = "Only one instance of this indexer allowed";
					hide([], [error]);
				}
				else
					console.log(e);
			});
		});
	});
};

async function testAddIndexer(apiKey) {
	const error = document.querySelector('#add-error');
	hide([error]);
	const form = document.querySelector('#add-indexer-form tbody');
	const testButton = document.querySelector('#test-indexer-add');
	testButton.classList.remove('show-success', 'show-fail');
	const data = {
		download_type: parseInt(form.dataset.download_type),
		client_type: form.dataset.type,
		url: form.querySelector('#add-url-input').value
	};
	return await sendAPI('POST', '/indexers/test', apiKey, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.result.success)
			// Test successful
			testButton.classList.add('show-success');
		else
			// Test failed
			testButton.classList.add('show-fail');
			error.innerText = brokenClientReasonMap[json.result.description];
			hide([], [error]);
		return json.result.success;
	});
};

const typeToList = {
	1: document.querySelector("#ddl-indexer-list")
};

function loadIndexers(apiKey) {
	Object.values(typeToList).forEach(
		l => l.querySelectorAll(":not(:first-child)").forEach(el => el.remove())
	);
	
	fetchAPI('/indexers', apiKey)
	.then(json => {
		json.result.forEach(indexer => {
			const entry = document.createElement('button');
			entry.onclick = e => loadEditIndexer(apiKey, indexer.id);
			entry.innerText = indexer.title;
			typeToList[indexer.download_type].appendChild(entry);
		});
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	loadIndexers(api_key);
	document.querySelector('#delete-indexer-edit').onclick = e => deleteIndexer(api_key);
	document.querySelector('#test-indexer-edit').onclick = e => testEditIndexer(api_key);
	document.querySelector('#test-indexer-add').onclick = e => testAddIndexer(api_key);
	
	Object.entries(typeToList).forEach(tl => {
		tl[1].querySelector('button:first-child').onclick = e => loadIndexerOptionList(api_key, tl[0]);
	})
});

document.querySelector('#edit-indexer-form').action = 'javascript:saveEditIndexer()';
document.querySelector('#add-indexer-form').action = 'javascript:saveAddIndexer()';
