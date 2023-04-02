// code run on load

const api_key = sessionStorage.getItem('api_key');

fetch(`/api/system/about?api_key=${api_key}`)
.then(response => response.json())
.then(json => {
	document.getElementById('version').innerText = json.result.version;
	document.getElementById('python-version').innerText = json.result.python_version;
	document.getElementById('database-version').innerText = json.result.database_version;
	document.getElementById('database-location').innerText = json.result.database_location;
	document.getElementById('data-folder').innerText = json.result.data_folder;
});
