const backupEls = {
	backups: document.getElementById("backup-list"),
	downloadDb: document.getElementById("download-button"),

	uploadDb: {
		open: document.getElementById("upload-button"),
		submit: document.getElementById("submit-upload-db"),
		form: document.getElementById("upload-db-form"),
		file: document.getElementById("database-file"),
		keepHostingSettings: document.getElementById("copy-hosting-upload"),
		error: document.getElementById("upload-error")
	},
	importDb: {
		backupName: document.getElementById("db-backup-name"),
		backupCreation: document.getElementById("db-creation-date"),
		submit: document.getElementById("submit-import-db"),
		form: document.getElementById("import-db-form"),
		keepHostingSettings: document.getElementById("copy-hosting-import")
	}
}

const invalidDbReasonMap = {
	not_kapowarr_db: "Uploaded database is not a Kapowarr database file",
	version_not_supported: "Uploaded database is higher version than this Kapowarr installation can support"
}

const backups = {}

function loadBackups(apiKey) {
	fetchAPI('/system/database/backups', apiKey)
	.then(json => {
		backupEls.backups.innerHTML = '';
		json.result.forEach(backup => {
			backups[backup.index] = {
				filename: backup.filename,
				creationDate: backup.creation_date
			}

			const entry = document.createElement("tr")
			entry.dataset.index = backup.index.toString()

			const filename = document.createElement("td")
			filename.innerText = backup.filename
			entry.appendChild(filename)

            const creation = document.createElement("td")
            let formattedDate = new Date(backup.creation_date * 1000)
                .toLocaleString()
            creation.innerText = formattedDate
            entry.appendChild(creation)

            const actions = document.createElement("td")
            entry.appendChild(actions)

            const downloadBackup = document.createElement("button")
			downloadBackup.innerHTML = icons.download
            downloadBackup.title = "Download database backup"
			downloadBackup.onclick = () =>
				window.location.href = `${url_base}/api/system/database/backups/${backup.index}?api_key=${apiKey}`
            actions.appendChild(downloadBackup)

            const importBackup = document.createElement("button")
			importBackup.innerHTML = icons.upload
            importBackup.title = "Import database backup"
			importBackup.onclick = () => openDatabaseImport(backup.index)
            actions.appendChild(importBackup)

			backupEls.backups.appendChild(entry)
		});
	});
};

let currentBackupIndex = null;

function openDatabaseImport(backupIndex) {
	currentBackupIndex = backupIndex

	backupEls.importDb.backupName.innerText = backups[backupIndex].filename
	backupEls.importDb.backupCreation.innerText = new Date(
		backups[backupIndex].creationDate * 1000
	).toLocaleString()
	backupEls.importDb.keepHostingSettings.checked = false

	showWindow("import-window")
}

function submitDatabaseImport(apiKey) {
	if (currentBackupIndex === null)
		throw new Error("Trying to submit importing a db without having the dialog open")

	backupEls.importDb.submit.innerText = "Importing..."

	sendAPI('POST', `/system/database/backups/${currentBackupIndex}`, apiKey, {}, {
		copy_hosting_settings: backupEls.importDb.keepHostingSettings.checked
	})
	.then(() => setTimeout(
		() => window.location.reload(),
		1000
	))
}

function openDatabaseUpload() {
	hide([backupEls.uploadDb.error])
	backupEls.uploadDb.file.value = ''
	backupEls.uploadDb.keepHostingSettings.checked = false
	showWindow("upload-window")
}

function submitDatabaseUpload(apiKey) {
	if (!backupEls.uploadDb.file.files)
		return

	const formData = new FormData()
	formData.append('file', backupEls.uploadDb.file.files[0])
	formData.append('copy_hosting_settings', backupEls.uploadDb.keepHostingSettings.checked)

	hide([backupEls.uploadDb.error])
	backupEls.uploadDb.submit.innerText = "Importing..."
	sendAPI('POST', '/system/database', apiKey, {}, formData)
	.then(() => setTimeout(
		() => window.location.reload(),
		1000
	))
	.catch(e => {
		e.json().then(json => {
			if (json.error === "InvalidDatabaseFile") {
				backupEls.uploadDb.file.value = ''
				backupEls.uploadDb.submit.innerText = "Import"
				backupEls.uploadDb.error.innerText = invalidDbReasonMap[json.result.reason] || json.result.reason
				hide([], [backupEls.uploadDb.error])
			}
			else
				console.log(e)
		})
	})
}

// code run on load

usingApiKey()
.then(api_key => {
	loadBackups(api_key)
	backupEls.downloadDb.onclick = () =>
		window.location.href = `${url_base}/api/system/database?api_key=${api_key}`
	backupEls.uploadDb.open.onclick = openDatabaseUpload
	backupEls.uploadDb.form.onsubmit = e => {
		e.preventDefault()
		submitDatabaseUpload(api_key)
	}
	backupEls.importDb.form.onsubmit = e => {
		e.preventDefault()
		submitDatabaseImport(api_key)
	}
})
