// Showing a fun loading message instead of the default message.
// Applies itself to any element with the data-loading-line attribute.

const LOADING_LINES = [
	"Uncrinkling the pages...",
	"Waking up the letterer...",
	"Checking the staples...",
	"Talking the inker into one more panel...",
	"Asking the colorist for five more minutes...",
	"Arguing politely with continuity...",
	"Looking under the couch for one missing issue...",
	"Confirming that no origin story is required...",
	"Counting capes. Recounting capes...",
	"Sharpening the penciler's pencils...",
	"Turning the page very carefully...",
	"Checking the barcodes for secret messages...",
	"Peeling off an imaginary 35-cent price sticker...",
	"Measuring the suspicious amount of shelf sag...",
	"Explaining the plan to the sidekick...",
	"Waiting for the cliffhanger to resolve...",
	"Keeping the mint copies mint...",
	"Assembling a needlessly dramatic loading page...",
	"Pretending continuity makes perfect sense...",
	"Consulting the backup artist...",
	"Interrogating the filing cabinet...",
	"Negotiating with the omniscient narrator...",
	"Checking whether that's actually canon...",
	"Reinforcing the shelf. Again...",
	"Removing the invisible dust...",
	"Polishing the imaginary foil cover...",
	"Locating the dramatic sound effect...",
	"Reticulating the comic-book splines...",
	"Loading the loading message...",
	"Waiting for the hero shot...",
	"Making a heroic amount of progress..."
];

const DEFAULT_LOADING_LINE = "Loading...";

function pickLoadingLine(lines = LOADING_LINES, randomFn = Math.random) {
	if (lines.length === 0)
		return DEFAULT_LOADING_LINE;
	return lines[Math.floor(randomFn() * lines.length)];
};

// code run on load
document.querySelectorAll('[data-loading-line]').forEach(el => {
	el.textContent = pickLoadingLine();
});
