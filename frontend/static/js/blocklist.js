const BlockEls = {
	table: document.querySelector('#blocklist'),
	page_turner: {
		container: document.querySelector('.page-turner'),
		previous: document.querySelector('#previous-page'),
		next: document.querySelector('#next-page'),
		number: document.querySelector('#page-number')
	},
	buttons: {
		refresh: document.querySelector('#refresh-button'),
		clear: document.querySelector('#clear-button')
	},
	entry: document.querySelector('.pre-build-els .list-entry')
};

var offset = 0;

function fillList(api_key) {
	fetchAPI('/blocklist', api_key, {offset: offset})
	.then(json => {
		BlockEls.table.innerHTML = '';
		json.result.forEach(obj => {
			const entry = BlockEls.entry.cloneNode(true);

			const link = entry.querySelector('a');
			link.href = obj.link;
			link.innerText = obj.link;

			entry.querySelector('.reason-column').innerText = obj.reason;

			var d = new Date(obj.added_at * 1000);
			var formatted_date =
				d.toLocaleString('en-CA').slice(0,10)
				+ ' '
				+ d.toTimeString().slice(0,5);
			entry.querySelector('.date-column').innerText = formatted_date;

			entry.querySelector('button').onclick = e => deleteEntry(obj.id, api_key);

			BlockEls.table.appendChild(entry);
		});
	});
};

function deleteEntry(id, api_key) {
	sendAPI('DELETE', `/blocklist/${id}`, api_key)
	.then(response => fillList(api_key));
};

function clearList(api_key) {
	sendAPI('DELETE', '/blocklist', api_key)
	offset = 0;
	BlockEls.page_turner.number.innerText = 'Page 1';
	BlockEls.table.innerHTML = '';
};

function reduceOffset(api_key) {
	if (offset === 0) return;
	offset--;
	BlockEls.page_turner.number.innerText = `Page ${offset + 1}`;
	fillList(api_key);
};

function increaseOffset(api_key) {
	if (BlockEls.table.innerHTML === '') return;
	offset++;
	BlockEls.page_turner.number.innerText = `Page ${offset + 1}`;
	fillList(api_key);
};

// code run on load
usingApiKey()
.then(api_key => {
	fillList(api_key);
	BlockEls.buttons.clear.onclick = e => clearList(api_key);
	BlockEls.buttons.refresh.onclick = e => fillList(api_key);
	BlockEls.page_turner.previous.onclick = e => reduceOffset(api_key);
	BlockEls.page_turner.next.onclick = e => increaseOffset(api_key);
});
