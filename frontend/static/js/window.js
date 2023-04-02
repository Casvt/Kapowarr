function showWindow(id) {
	// Hide all other windows
	document.querySelectorAll('.window').forEach(e => {
		e.classList.add('hidden');
		e.setAttribute('aria-hidden','true');
	});
	
	// Show window
	const window = document.getElementById(id);
	window.classList.remove('hidden');
	window.setAttribute('aria-hidden', 'false');

	return;
};

function closeWindow() {
	document.querySelectorAll('.window').forEach(e => {
		e.classList.add('hidden');
		e.setAttribute('aria-hidden','true');
	});
	return;
};

// code run on load

document.querySelectorAll('.window').forEach(e => {
	e.classList.add('hidden');
	e.setAttribute('aria-hidden','true');
});

document.querySelectorAll('.window-close').forEach(e => {
	e.addEventListener('click', e => closeWindow());
})
