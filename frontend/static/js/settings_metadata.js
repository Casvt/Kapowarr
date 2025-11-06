function getCurrentValues() {
	return {
		date_type: document.querySelector('#date-type-input').value
	};
}

function fillSettings(api_key) {
	fetchAPI('/settings', api_key)
	.then(json => {
		document.querySelector('#date-type-input').value = json.result.date_type;
		
		// Initialize unsaved changes tracking after settings are loaded
		initUnsavedChangesTracking(getCurrentValues);
	});
};

function saveSettings(api_key) {
	document.querySelector("#save-button p").innerText = 'Saving';
	const data = {
		'date_type': document.querySelector('#date-type-input').value
	};
	sendAPI('PUT', '/settings', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		if (json.error !== null) return Promise.reject(json);
		document.querySelector("#save-button p").innerText = 'Saved';
		markAsSaved(getCurrentValues);
	})
	.catch(e => {
		document.querySelector("#save-button p").innerText = 'Failed';
		console.log(e.error);
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	document.querySelector('#save-button').onclick = e => saveSettings(api_key);
});
