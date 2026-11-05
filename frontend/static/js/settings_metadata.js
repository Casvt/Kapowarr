function fillSettings(api_key) {
	fetchAPI('/settings', api_key)
	.then(json => {
		document.querySelector('#date-type-input').value = json.result.date_type;
		document.querySelector('#export-metadata-input').checked = json.result.export_metadata;
		document.querySelector('#export-extended-metadata-input').checked = json.result.export_extended_metadata;
	});
};

function saveSettings(api_key) {
	document.querySelector("#save-button p").innerText = 'Saving';
	const data = {
		'date_type': document.querySelector('#date-type-input').value,
		'export_metadata': document.querySelector('#export-metadata-input').checked,
		'export_extended_metadata': document.querySelector('#export-extended-metadata-input').checked
	};
	sendAPI('PUT', '/settings', api_key, {}, data)
	.then(response => response.json())
	.then(json => {
		document.querySelector("#save-button p").innerText = 'Saved';
	})
	.catch(e => {
		document.querySelector("#save-button p").innerText = 'Failed';
		console.log(e);
	});
};

// code run on load

usingApiKey()
.then(api_key => {
	fillSettings(api_key);
	document.querySelector('#save-button').onclick = e => saveSettings(api_key);
});
