// Functions to update the UI for workout_execution.html

/**
 * Renders a single set row in the table.
 * @param {object} setData - Object containing set data (e.g., id, set_number, actual_weight, actual_reps, actual_rir, mti, notes).
 * @param {boolean} isEditing - Whether the row should be in edit mode.
 * @returns {HTMLTableRowElement} The table row element.
 */
function renderSetRow(setData, isEditing = false) {
    const row = document.createElement('tr');
    row.setAttribute('data-set-db-id', setData.id); // Store database ID if available
    row.setAttribute('data-set-ui-id', `set-row-${setData.ui_id || setData.id}`); // Unique UI id for the row

    if (isEditing) {
        // Edit mode: Render input fields
        row.classList.add('editing');
        row.innerHTML = `
            <td class="set-number">${setData.set_number}</td>
            <td><input type="number" class="set-input weight-input" value="${setData.actual_weight || ''}" placeholder="kg"></td>
            <td><input type="number" class="set-input reps-input" value="${setData.actual_reps || ''}" placeholder="reps"></td>
            <td><input type="number" class="set-input rir-input" value="${setData.actual_rir === null || setData.actual_rir === undefined ? '' : setData.actual_rir}" placeholder="RIR"></td>
            <td><textarea class="set-input notes-input" placeholder="Notes...">${setData.notes || ''}</textarea></td>
            <td class="set-actions">
                <button class="save-set-btn" data-set-id="${setData.id}" title="Save Changes">✔️</button>
                <button class="cancel-edit-btn" data-set-id="${setData.id}" title="Cancel Edit">❌</button>
            </td>
        `;
    } else {
        // Display mode: Render text values and Edit/Delete icons
        row.innerHTML = `
            <td class="set-number">${setData.set_number}</td>
            <td class="set-data-weight">${setData.actual_weight || '--'}</td>
            <td class="set-data-reps">${setData.actual_reps || '--'}</td>
            <td class="set-data-rir">${setData.actual_rir === null || setData.actual_rir === undefined ? '--' : setData.actual_rir}</td>
            <td class="set-data-mti">${setData.mti ? setData.mti.toFixed(2) : '--'}</td>
            <td class="set-data-notes">${setData.notes || ''}</td>
            <td class="set-actions">
                <button class="edit-set-btn icon-btn" data-set-id="${setData.id}" title="Edit Set">✎</button>
                <button class="delete-set-btn icon-btn" data-set-id="${setData.id}" title="Delete Set">🗑️</button>
            </td>
        `;
        // Note: MTI and Notes are in separate columns in display mode for clarity.
        // The table header in workout_execution.html might need adjustment if notes are to be displayed.
        // For now, let's assume the HTML has a notes column or MTI column can show notes for simplicity here.
        // The provided HTML has MTI and an "Actions" column. I'll adjust the render to fit that.
        // It implies that notes might not be directly visible in a column but could be in edit mode.
        // Re-adjusting to match HTML structure more closely:
        row.innerHTML = `
            <td class="set-number">${setData.set_number}</td>
            <td class="set-data-weight">${setData.actual_weight || '--'} kg</td>
            <td class="set-data-reps">${setData.actual_reps || '--'}</td>
            <td class="set-data-rir">${setData.actual_rir === null || setData.actual_rir === undefined ? '--' : setData.actual_rir}</td>
            <td class="set-data-mti">${setData.mti ? setData.mti.toFixed(2) : '--'}</td>
            <td class="set-actions">
                <button class="edit-set-btn icon-btn" data-set-id="${setData.id}" title="Edit Set">✎</button>
                <button class="delete-set-btn icon-btn" data-set-id="${setData.id}" title="Delete Set">🗑️</button>
            </td>
        `;
        // If notes are to be displayed, a 'notes' column would be needed in the table header and here.
    }
    return row;
}


/**
 * Updates the display of an existing set row with new data.
 * @param {string} setId - The ID of the set to update.
 * @param {object} updatedSetData - Object containing the new set data.
 */
function updateSetRowDisplay(setId, updatedSetData) {
    const row = document.querySelector(`tr[data-set-db-id="${setId}"]`);
    if (!row) {
        console.error(`Cannot update row: Set row with ID ${setId} not found.`);
        return;
    }

    // Assuming updatedSetData contains all necessary fields for display
    row.classList.remove('editing');
    row.innerHTML = `
        <td class="set-number">${updatedSetData.set_number}</td>
        <td class="set-data-weight">${updatedSetData.actual_weight || '--'} kg</td>
        <td class="set-data-reps">${updatedSetData.actual_reps || '--'}</td>
        <td class="set-data-rir">${updatedSetData.actual_rir === null || updatedSetData.actual_rir === undefined ? '--' : updatedSetData.actual_rir}</td>
        <td class="set-data-mti">${updatedSetData.mti ? updatedSetData.mti.toFixed(2) : '--'}</td>
        <td class="set-actions">
            <button class="edit-set-btn icon-btn" data-set-id="${updatedSetData.id}" title="Edit Set">✎</button>
            <button class="delete-set-btn icon-btn" data-set-id="${updatedSetData.id}" title="Delete Set">🗑️</button>
        </td>
    `;
    // Re-attach event listeners if needed, or rely on event delegation from a parent.
    // This will be handled by the main workout_execution.js which calls this.
}


/**
 * Clears all set rows from the table.
 */
function clearSetTable() {
    const tbody = document.getElementById('set-logging-tbody');
    if (tbody) {
        tbody.innerHTML = '';
    }
}

/**
 * Adds a new set row to the table, typically for a new, unlogged set.
 * This is different from renderSetRow which might be used for existing sets.
 * @param {number} setNumber - The number for the new set.
 */
function addNewSetInputRow(setNumber) {
    const tbody = document.getElementById('set-logging-tbody');
    if (!tbody) return;

    const row = document.createElement('tr');
    // Add a temporary UI ID for new rows not yet saved to DB
    const tempUiId = `new-set-${Date.now()}`;
    row.setAttribute('data-set-ui-id', tempUiId);
    row.classList.add('new-set-row'); // Class to identify new rows if needed

    row.innerHTML = `
        <td class="set-number">${setNumber}</td>
        <td><input type="number" class="set-input weight-input" placeholder="kg"></td>
        <td><input type="number" class="set-input reps-input" placeholder="reps"></td>
        <td><input type="number" class="set-input rir-input" placeholder="RIR"></td>
        <td class="mti-value">--</td>
        <td class="set-actions">
            <button class="log-set-row-btn action-button">Log</button>
            <button class="remove-new-set-btn icon-btn" title="Remove this row">🗑️</button>
        </td>
    `;
    tbody.appendChild(row);
    // Event listeners for 'log-set-row-btn' and 'remove-new-set-btn' for this new row
    // will be attached in workout_execution.js, likely using event delegation.
}


// --- UI update functions for other parts of the page ---

function updateExerciseName(name) {
    const placeholder = document.getElementById('exercise-name-placeholder');
    if (placeholder) {
        placeholder.textContent = name || "[Exercise Name]";
    }
}

function displayAIRecommendation(recommendation) {
    const card = document.querySelector('.ai-recommendation-card');
    if (!card) return;

    const weightDisplay = card.querySelector('.weight-display');
    const repRangeDisplay = card.querySelector('.rep-range');
    const confidenceFill = card.querySelector('.confidence-fill');
    const whyButton = card.querySelector('.why-button'); // Keep this line
    const whyExplanation = card.querySelector('.why-explanation p');


    if (recommendation && recommendation.recommended_weight_kg !== undefined) {
        weightDisplay.textContent = `${recommendation.recommended_weight_kg.toFixed(1)} kg`;
        repRangeDisplay.textContent = `${recommendation.target_reps_low}-${recommendation.target_reps_high} reps @ ${recommendation.target_rir} RIR`;

        // Example: confidence could be a fixed value or part of recommendation
        const confidence = recommendation.confidence || 0.85; // Default if not provided
        confidenceFill.style.width = `${confidence * 100}%`;
        confidenceFill.textContent = `${Math.round(confidence * 100)}% confident`;

        if (whyExplanation) { // Check if the element exists
            whyExplanation.textContent = recommendation.explanation || "No explanation provided.";
        }
        card.style.display = ''; // Make visible if hidden
    } else if (recommendation && recommendation.message) { // Handle cases like "No data"
        weightDisplay.textContent = recommendation.message;
        repRangeDisplay.textContent = "";
        confidenceFill.style.width = `0%`;
        confidenceFill.textContent = "";
        if (whyExplanation) whyExplanation.textContent = "";

    } else {
        // Hide or show a default message if no recommendation
        weightDisplay.textContent = "N/A";
        repRangeDisplay.textContent = "No recommendation available.";
        confidenceFill.style.width = '0%';
        confidenceFill.textContent = '0% confident';
        if (whyExplanation) whyExplanation.textContent = "No explanation available.";
    }
}


function displayPreviousPerformance(performance) {
    const container = document.querySelector('.performance-comparison');
    if (!container) return;

    const lastTimePerfEl = container.querySelector('.last-time-performance');
    const improvementMetricEl = container.querySelector('.improvement-metric');

    if (performance && performance.previous_set) {
        const prev = performance.previous_set;
        lastTimePerfEl.textContent = `Last time: ${prev.weight_kg}kg × ${prev.reps} reps @ ${prev.rir} RIR`;
        improvementMetricEl.textContent = performance.progression_metric_string || "No progression data.";
        improvementMetricEl.className = 'improvement-metric'; // Reset class
        if (performance.is_positive_progression === true) {
            improvementMetricEl.classList.add('positive');
        } else if (performance.is_positive_progression === false) {
            improvementMetricEl.classList.add('negative');
        }
    } else {
        lastTimePerfEl.textContent = "No previous sets recorded for this exercise.";
        improvementMetricEl.textContent = "";
    }
}

function displayErrorMessage(message, type = 'error') {
    // Simple alert for now, could be a modal or a dedicated error area
    alert(`${type.toUpperCase()}: ${message}`);
}

function showLoadingState(isLoading) {
    // Placeholder for showing/hiding a global loader or disabling buttons
    console.log(`UI Loading State: ${isLoading ? 'ON' : 'OFF'}`);
    const buttons = document.querySelectorAll('button');
    if (isLoading) {
        buttons.forEach(button => button.disabled = true);
    } else {
        buttons.forEach(button => button.disabled = false);
        // Note: This is a very broad way to disable buttons.
        // More specific selectors should be used in a real app.
        // Also, log-set-row-btn initial state needs to be handled carefully.
    }
}

// Example from original file, kept for reference or if it's used by workout_execution.js
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('rest-timer-canvas');
    if (canvas && typeof canvas.getContext === 'function') {
        const ctx = canvas.getContext('2d');
        const radius = canvas.width / 2 - 10;
        const lineWidth = 8;

        ctx.beginPath();
        ctx.arc(canvas.width / 2, canvas.height / 2, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = '#e9ecef';
        ctx.lineWidth = lineWidth;
        ctx.stroke();
        console.log('Rest timer canvas placeholder drawn.');
    } else {
        console.warn('Rest timer canvas not found or not supported.');
    }

    // Event listener for the "Why this weight?" button
    const whyButton = document.querySelector('.ai-recommendation-card .why-button');
    const whyExplanation = document.querySelector('.ai-recommendation-card .why-explanation');

    if (whyButton && whyExplanation) {
        whyButton.addEventListener('click', () => {
            // Toggle display of the explanation
            whyExplanation.style.display = whyExplanation.style.display === 'none' ? 'block' : 'none';
        });
    }
});

// Make functions available for workout_execution.js to import or use if bundled.
// If not using modules, they are globally available on `window` or just in scope.
// For simplicity here, assuming they are available in scope for workout_execution.js
// e.g. window.WorkoutExecutionUI = { renderSetRow, ... }; if you want to namespace.
