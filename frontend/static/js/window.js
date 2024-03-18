function showWindow(id) {
	// Deselect all windows
	document.querySelectorAll('.window > section').forEach(window => {
		window.removeAttribute('show-window');
	});

	// Select the correct window
	document.querySelector(`.window > section#${id}`).setAttribute('show-window', '');

	// Show the window
	document.querySelector('.window').setAttribute('show-window', '');
};

function showLoadWindow(id) {
	// Deselect all windows
	document.querySelectorAll('.window > section').forEach(window => {
		window.removeAttribute('show-window');
	});

	// Select the correct window
	const loading_window = document.querySelector(`.window > section#${id}`).dataset.loading_window;
	if (loading_window !== undefined) document.querySelector(`.window > section#${loading_window}`).setAttribute('show-window', '');

	// Show the window
	document.querySelector('.window').setAttribute('show-window', '');
};

function closeWindow() {
	document.querySelector('.window').removeAttribute('show-window');
};

// code run on load

document.querySelector('body').onkeydown = e => {
	if (
		document.querySelector('.window[show-window]')
		&&
		e.code === "Escape"
	) {
		e.stopImmediatePropagation();
		closeWindow();
	};
};

document.querySelector('.window').onclick = e => {
	e.stopImmediatePropagation();
	closeWindow();
};

document.querySelectorAll('.window > section').forEach(
	el => el.onclick = e => e.stopImmediatePropagation()
);

document.querySelectorAll(
	'.window > section :where(button[title="Cancel"], button.cancel-window)'
).forEach(e => {
	e.onclick = f => closeWindow();
});
