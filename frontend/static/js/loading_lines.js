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

const LOADING_LINES = [
	"Uncrinkling the pages...",
	"Waking up the letterer...",
	"Checking the staples...",
	"Flipping to the next issue...",
	"Talking the inker into one more panel...",
	"Dusting off the longboxes...",
	"Reordering the back issues...",
	"Asking the colorist for five more minutes...",
	"Chasing down a missing splash page...",
	"Bagging and boarding the evidence...",
	"Alphabetizing the pull list...",
	"Arguing politely with continuity...",
	"Checking that issue #1 isn't another reboot...",
	"Separating the annuals from the regular issues...",
	"Rescuing the variant covers from the wrong stack...",
	"Straightening the spinner rack...",
	"Looking under the couch for one missing issue...",
	"Decoding legacy issue numbering...",
	"Cross-referencing secret identities...",
	"Teaching the database the difference between a volume and a Volume...",
	"Filing the one-shots where they can cause the least confusion...",
	"Putting the trades back on the shelf...",
	"Ignoring a slabbed copy that looks judgmental...",
	"Comparing cover dates with publication dates...",
	"Shuffling the reading order one last time...",
	"Waking ComicVine from its mysterious slumber...",
	"Confirming that no origin story is required...",
	"Counting capes. Recounting capes...",
	"Sharpening the penciler's pencils...",
	"Lining up the speech balloons...",
	"Making room in the longbox...",
	"Returning a borrowed issue before anyone notices...",
	"Asking the editor whether that retcon is still canon...",
	"Putting issue #12 back after issue #11...",
	"De-duplicating the multiverse...",
	"Untangling a crossover event...",
	"Turning the page very carefully...",
	"Locating the annual everyone forgot about...",
	"Checking the barcodes for secret messages...",
	"Peeling off an imaginary 35-cent price sticker...",
	"Flattening dog-ears with a stern look...",
	"Opening the Wednesday pull...",
	"Checking for an accidental double cover...",
	"Measuring the suspicious amount of shelf sag...",
	"Explaining the plan to the sidekick...",
	"Waiting for the cliffhanger to resolve...",
	"Keeping the mint copies mint...",
	"Assembling a needlessly dramatic splash page...",
	"Pretending continuity makes perfect sense...",
	"Reminding the supervillains that import is already in progress...",
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
