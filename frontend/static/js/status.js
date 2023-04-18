// code run on load
usingApiKey()
.then(api_key => {
	fetch(`/api/system/about?api_key=${api_key}`)
	.then(response => response.json())
	.then(json => {
		document.querySelector('#version').innerText = json.result.version;
		document.querySelector('#python-version').innerText = json.result.python_version;
		document.querySelector('#database-version').innerText = json.result.database_version;
		document.querySelector('#database-location').innerText = json.result.database_location;
		document.querySelector('#data-folder').innerText = json.result.data_folder;
	});
})
