//
// Rotating loading-screen flavor text
//
// Swaps the static "Loading..." heading for a comic-themed line, picked at
// random each time a loading screen is shown. One data source and one
// lookup function, so any loading screen can opt in with a single data
// attribute rather than each page carrying its own copy.
//
// `pickLoadingLine` takes its lines and its random function as arguments,
// so it can be exercised with a stubbed random and no DOM.
//
// Rule for adding a line: it must not be readable as a true status message.
// A line that names something Kapowarr actually does to your library --
// matching, renaming, moving, importing, converting, sorting, de-duplicating,
// reading metadata, talking to ComicVine -- tells the user work is happening
// that isn't. Keep every line anchored to a physical object or a person the
// software obviously does not have (a longbox, a staple, the colorist), so it
// reads as flavor and never as progress.
//

const LOADING_LINES = [
	"Uncrinkling the pages...",
	"Waking up the letterer...",
	"Checking the staples...",
	"Talking the inker into one more panel...",
	"Dusting off the longboxes...",
	"Asking the colorist for five more minutes...",
	"Bagging and boarding the evidence...",
	"Arguing politely with continuity...",
	"Straightening the spinner rack...",
	"Looking under the couch for one missing issue...",
	"Putting the trades back on the shelf...",
	"Ignoring a slabbed copy that looks judgmental...",
	"Confirming that no origin story is required...",
	"Counting capes. Recounting capes...",
	"Sharpening the penciler's pencils...",
	"Lining up the speech balloons...",
	"Making room in the longbox...",
	"Returning a borrowed issue before anyone notices...",
	"Asking the editor whether that retcon is still canon...",
	"Untangling a crossover event...",
	"Turning the page very carefully...",
	"Checking the barcodes for secret messages...",
	"Peeling off an imaginary 35-cent price sticker...",
	"Flattening dog-ears with a stern look...",
	"Opening the Wednesday pull...",
	"Measuring the suspicious amount of shelf sag...",
	"Explaining the plan to the sidekick...",
	"Waiting for the cliffhanger to resolve...",
	"Keeping the mint copies mint...",
	"Assembling a needlessly dramatic splash page...",
	"Pretending continuity makes perfect sense...",
];

// Must exactly match the fallback text baked into every template's
// <h2>Loading...</h2>, so a slow or blocked script never leaves a blank
// heading.
const DEFAULT_LOADING_LINE = "Loading...";

function pickLoadingLine(lines = LOADING_LINES, randomFn = Math.random) {
	if (!Array.isArray(lines) || lines.length === 0)
		return DEFAULT_LOADING_LINE;
	const index = Math.floor(randomFn() * lines.length);
	return lines[Math.max(0, Math.min(lines.length - 1, index))];
};

function applyLoadingLines() {
	try {
		document.querySelectorAll('[data-loading-line]').forEach(el => {
			el.textContent = pickLoadingLine();
		});
	} catch (e) {
		// Any failure here leaves the template's own static "Loading..."
		// text in place -- never throw past this.
	};
};

// code run on load
applyLoadingLines();
