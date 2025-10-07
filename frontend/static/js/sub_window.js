function showSubWindow(id) {
	// Deselect all sub-windows
	document.querySelectorAll('.sub-window > section').forEach(window => {
		window.removeAttribute('show-window');
	});

	// Select the correct sub-window
	thing = document.querySelector(`.sub-window > section#${id}`);
	thing.setAttribute('show-window', '');

	// Show the window
	document.querySelector('.sub-window').setAttribute('show-window', '');
};

function closeSubWindow() {
	document.querySelector('.sub-window').removeAttribute('show-window');
};

// code run on load

document.querySelector('body').onkeydown = e => {
	if (
		e.code === "Escape"
		&&
		document.querySelector('.sub-window[show-window]')
	) {
		e.stopImmediatePropagation();
		closeSubWindow();
	};
};

document.querySelector('.sub-window').onclick = e => {
	e.stopImmediatePropagation();
	closeSubWindow();
};

document.querySelectorAll('.sub-window > section').forEach(
	el => el.onclick = e => e.stopImmediatePropagation()
);

document.querySelectorAll(
	'.sub-window > section :where(button[title="Cancel"], button.cancel-sub-window)'
).forEach(e => {
	e.onclick = f => closeSubWindow();
});
