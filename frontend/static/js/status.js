const StatEls = {
	version: document.querySelector('#version'),
	python_version: document.querySelector('#python-version'),
	database_version: document.querySelector('#database-version'),
	database_location: document.querySelector('#database-location'),
	data_folder: document.querySelector('#data-folder')
};

// code run on load

usingApiKey()
.then(api_key => {
	fetchAPI('/system/about', api_key)
	.then(json => {
		StatEls.version.innerText = json.result.version;
		StatEls.python_version.innerText = json.result.python_version;
		StatEls.database_version.innerText = json.result.database_version;
		StatEls.database_location.innerText = json.result.database_location;
		StatEls.data_folder.innerText = json.result.data_folder;
	});
})
