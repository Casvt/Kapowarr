// Common utilities for settings pages

let hasUnsavedChanges = false;
let initialValues = {};
let userConfirmedLeave = false; // Flag to prevent double warnings

/**
 * Initialize unsaved changes tracking
 * @param {Object} getCurrentValues - Function that returns current form values as an object
 * 
 * Note: getCurrentValues() should follow the same pattern as fillSettings() - 
 * fields are used explicitly to match the API structure and handle type conversions.
 * This ensures type safety and handles special cases (localStorage, transformations, arrays).
 */
function initUnsavedChangesTracking(getCurrentValues) {
	// Store initial values
	initialValues = JSON.parse(JSON.stringify(getCurrentValues()));
	hasUnsavedChanges = false;
	userConfirmedLeave = false; // Reset flag when initializing
	updateSaveButtonState();
	
	// Add change listeners to all inputs, selects, and textareas
	const inputs = document.querySelectorAll('#settings-form input, #settings-form select, #settings-form textarea');
	inputs.forEach(input => {
		// Skip if it's a button or submit input
		if (input.type === 'button' || input.type === 'submit') return;
		
		input.addEventListener('change', () => checkForChanges(getCurrentValues));
		input.addEventListener('input', () => checkForChanges(getCurrentValues));
	});
	
	// Warn before leaving page (browser navigation: close tab, refresh, etc.)
	window.addEventListener('beforeunload', (e) => {
		if (hasUnsavedChanges && !userConfirmedLeave) {
			e.preventDefault();
			e.returnValue = ''; // Chrome requires returnValue to be set
			return ''; // Some browsers require a return value
		}
	});
	
	// Intercept navigation links (in-app navigation)
	document.querySelectorAll('nav a').forEach(link => {
		link.addEventListener('click', (e) => {
			if (hasUnsavedChanges) {
				if (!confirm('You have unsaved changes. Are you sure you want to leave this page?')) {
					e.preventDefault();
					return false;
				} else {
					// User confirmed, set flag to prevent beforeunload from also showing
					userConfirmedLeave = true;
				}
			}
		});
	});
}

/**
 * Check if current values differ from initial values
 */
function checkForChanges(getCurrentValues) {
	const currentValues = getCurrentValues();
	const currentStr = JSON.stringify(currentValues);
	const initialStr = JSON.stringify(initialValues);
	
	hasUnsavedChanges = currentStr !== initialStr;
	updateSaveButtonState();
}

/**
 * Update save button visual state based on unsaved changes
 */
function updateSaveButtonState() {
	const saveButton = document.querySelector('#save-button');
	if (!saveButton) return;
	
	if (hasUnsavedChanges) {
		saveButton.classList.add('has-unsaved-changes');
	} else {
		saveButton.classList.remove('has-unsaved-changes');
	}
}

/**
 * Mark settings as saved (reset tracking)
 * @param {Object} getCurrentValues - Function that returns current form values as an object
 */
function markAsSaved(getCurrentValues) {
	initialValues = JSON.parse(JSON.stringify(getCurrentValues()));
	hasUnsavedChanges = false;
	updateSaveButtonState();
}

