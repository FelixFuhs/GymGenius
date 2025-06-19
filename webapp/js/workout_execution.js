// Assuming API_BASE_URL, getUserId, getAuthToken, getAuthHeaders are globally available
// or will be imported/defined in a shared utility file later.

// For testing purposes, these might be hardcoded or fetched from URL params later.
let currentExerciseId = 'e078a34a-7060-4624-94f2-1020f80d53ce'; // Example Squat ID
let currentUserId = null; // Will be fetched by getUserId()

// Store the fetched explanation globally or re-fetch if panel is re-rendered often.
let aiExplanation = "Explanation will be loaded from the AI.";

const DEFAULT_REST_DURATION = 90; // 90 seconds
let currentWorkoutId = null; // Will be fetched from URL
let currentlyEditingSetId = null; // Tracks the DB ID of the set being edited
let setsDataCache = []; // To store fetched set data for easier access and revert

// --- UI Helper Imports (assuming workout_execution_ui.js is loaded) ---
// These would be actual imports if using modules, otherwise they are global:
// import { renderSetRow, updateSetRowDisplay, clearSetTable, addNewSetInputRow, updateExerciseName, displayAIRecommendation, displayPreviousPerformance, displayErrorMessage, showLoadingState } from './workout_execution_ui.js';
// For non-module environment, ensure workout_execution_ui.js is loaded first.
const { renderSetRow, updateSetRowDisplay, clearSetTable, addNewSetInputRow, updateExerciseName, displayAIRecommendation, displayPreviousPerformance, displayErrorMessage, showLoadingState } = window; // Or however they are exposed by workout_execution_ui.js

// Function to update the AI Recommendation Panel
function updateAIRecommendationPanel(data) {
    const weightDisplay = document.querySelector('.ai-recommendation-card .weight-display');
    const repRangeDisplay = document.querySelector('.ai-recommendation-card .rep-range');
    const confidenceFill = document.querySelector('.ai-recommendation-card .confidence-fill');
    const whyExplanationP = document.querySelector('.ai-recommendation-card .why-explanation p');

    if (!weightDisplay || !repRangeDisplay || !confidenceFill || !whyExplanationP) {
        console.error("AI Recommendation panel elements not found.");
        return;
    }

    if (data) {
        weightDisplay.textContent = data.recommended_weight_kg ? `${data.recommended_weight_kg} kg` : "-- kg";
        repRangeDisplay.textContent = (data.target_reps_low && data.target_reps_high && data.target_rir !== undefined) ?
                                      `${data.target_reps_low} - ${data.target_reps_high} reps @ ${data.target_rir} RIR` : "-- reps @ -- RIR";

        // Confidence score might be deprecated or less emphasized with readiness score now available.
        // Handle its potential absence gracefully.
        if (data.confidence_score !== undefined && confidenceFill) {
            const confidencePercent = (data.confidence_score * 100).toFixed(0);
            confidenceFill.style.width = `${confidencePercent}%`;
            confidenceFill.textContent = `${confidencePercent}% confident`;
            confidenceFill.style.display = 'flex'; // Ensure it's visible if it was hidden
        } else if (confidenceFill) {
            // If no confidence score, hide or show N/A for that specific element
            confidenceFill.style.width = `0%`;
            confidenceFill.textContent = `N/A`;
            // Or hide it: confidenceFill.style.display = 'none';
        }

        aiExplanation = data.explanation || "No specific explanation provided."; // Store for "Why?" button
        whyExplanationP.textContent = aiExplanation; // Pre-populate, though div is hidden
    } else {
        // Reset to placeholders or error message
        weightDisplay.textContent = "-- kg";
        repRangeDisplay.textContent = "-- reps @ -- RIR";
        if (confidenceFill) {
            confidenceFill.style.width = `0%`;
            confidenceFill.textContent = `Error`;
        }
        aiExplanation = "Could not load recommendation.";
        whyExplanationP.textContent = aiExplanation;
    }
}

// Function to log a set
async function logSet(weight, reps, rir) {
    if (!currentUserId || !currentExerciseId) {
        console.error("User ID or Exercise ID is missing. Cannot log set.");
        // Display error to user on the page
        alert("Error: User or Exercise not identified. Please refresh.");
        return;
    }

    // Basic validation
    if (isNaN(parseFloat(weight)) || parseFloat(weight) < 0) {
        alert("Please enter a valid weight.");
        return;
    }
    if (isNaN(parseInt(reps)) || parseInt(reps) < 0) {
        alert("Please enter a valid number of reps.");
        return;
    }
    // RIR is optional, but if provided, should be a number.
    // The API expects an integer or null for RIR.
    let rirValue = null;
    if (rir !== "" && rir !== null && rir !== undefined) {
        rirValue = parseInt(rir);
        if (isNaN(rirValue)) {
            alert("Please enter a valid RIR value or leave it blank.");
            return;
        }
    }

    const payload = {
        weight_kg: parseFloat(weight),
        reps: parseInt(reps),
        rir: rirValue,
        // Optional: include notes, set_type if your form and API support it
        // notes: document.getElementById('setNotes').value,
        // set_type: "NORMAL" // Or "WARMUP", "DROPSET", etc.
    };

    try {
        const response = await fetch(`${API_BASE_URL}/v1/user/${currentUserId}/exercise/${currentExerciseId}/log-set`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to log set. Network error or invalid response." }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const loggedSetData = await response.json(); // API should return the logged set, possibly with server-generated fields like ID or timestamp

        // Add to UI table
        addSetToTable(loggedSetData); // Assuming loggedSetData is in the format addSetToTable expects

        // Clear input fields (optional, good UX)
        document.getElementById('weightInput').value = '';
        document.getElementById('repsInput').value = '';
        document.getElementById('rirInput').value = '';
        // document.getElementById('setNotes').value = '';


        // Fetch new AI recommendations based on the new set
        await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId);
        // Fetch updated previous performance (which will now include this set)
        await fetchAndDisplayPreviousPerformance(currentExerciseId, currentUserId);


        // Start rest timer
        startRestTimer(DEFAULT_REST_DURATION);

        console.log("Set logged successfully:", loggedSetData);
        // Display success message (e.g., a toast notification)

    } catch (error) {
        console.error("Error logging set:", error);
        alert(`Error logging set: ${error.message}`); // Display error to user
    }
}

// Function to set loading state for AI Panel
function setAIRecommendationLoadingState(isLoading) {
    const weightDisplay = document.querySelector('.ai-recommendation-card .weight-display');
    const repRangeDisplay = document.querySelector('.ai-recommendation-card .rep-range');
    const confidenceFill = document.querySelector('.ai-recommendation-card .confidence-fill');
    const whyButton = document.querySelector('.ai-recommendation-card .why-button');
    const aiCard = document.querySelector('.ai-recommendation-card'); // Get the card itself to manage a general loader

    if (!aiCard || !weightDisplay || !repRangeDisplay || !confidenceFill || !whyButton) return;

    if (isLoading) {
        // Option 1: Show a loader overlay on the card (more complex, needs CSS for overlay)
        // Option 2: Simpler, replace content with loader
        weightDisplay.innerHTML = '<span class="loader" style="width:20px; height:20px; border-width:3px;"></span>';
        repRangeDisplay.textContent = "Calculating...";
        confidenceFill.style.width = `0%`;
        confidenceFill.textContent = ``; // Clear text from bar
        whyButton.disabled = true;
    } else {
        // Content will be updated by updateAIRecommendationPanel after data is fetched
        whyButton.disabled = false;
    }
}

async function fetchAndDisplayAIRecommendations(exerciseId, userId) {
    if (!exerciseId || !userId) {
        console.error("Exercise ID or User ID is missing for AI recommendations.");
        updateAIRecommendationPanel(null); // Show error/placeholder state
        return;
    }

    setAIRecommendationLoadingState(true);

    try {
        const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/exercises/${exerciseId}/recommend-set-parameters`, { // Changed 'user' to 'users'
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to fetch AI recommendations. Network error or invalid response." }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        updateAIRecommendationPanel(data); // Existing function to update AI rec card
        updateReadinessDial(data.readiness_score_percent); // New function to update the dial

    } catch (error) {
        console.error("Error fetching AI recommendations:", error);
        updateAIRecommendationPanel(null); // Show error/placeholder state
        // Optionally update a status div with error.message
        const repRangeDisplay = document.querySelector('.ai-recommendation-card .rep-range');
        if(repRangeDisplay) repRangeDisplay.textContent = error.message.includes("User exercise data not found") ? "No data yet for AI." : "Error loading AI recs.";

    } finally {
        setAIRecommendationLoadingState(false);
    }
}

function updateReadinessDial(scorePercent) {
    const progressElement = document.getElementById('readiness-progress');
    const textElement = document.getElementById('readiness-score-text');
    const dialContainer = document.getElementById('readiness-dial-container');
    const lowReadinessMsgEl = document.getElementById('low-readiness-message');

    if (!progressElement || !textElement || !dialContainer || !lowReadinessMsgEl) {
        console.warn("Readiness dial or message HTML elements not found.");
        if(dialContainer) dialContainer.style.display = 'none';
        if(lowReadinessMsgEl) lowReadinessMsgEl.style.display = 'none';
        return;
    }

    // Default to hiding the low readiness message
    lowReadinessMsgEl.style.display = 'none';

    if (scorePercent === null || scorePercent === undefined) {
        progressElement.value = 0;
        textElement.textContent = 'N/A';
        progressElement.classList.remove('low-readiness', 'medium-readiness', 'high-readiness');
        progressElement.classList.add('na-readiness');
        dialContainer.style.display = 'block';
        return;
    }

    const score = Math.round(scorePercent);
    progressElement.value = score;
    textElement.textContent = score + '%';

    progressElement.classList.remove('low-readiness', 'medium-readiness', 'high-readiness', 'na-readiness');
    if (score < 45) {
        progressElement.classList.add('low-readiness');
        lowReadinessMsgEl.style.display = 'block'; // Show message for low readiness
    } else if (score < 75) {
        progressElement.classList.add('medium-readiness');
    } else {
        progressElement.classList.add('high-readiness');
    }
    dialContainer.style.display = 'block'; // Make sure dial container is visible
}

function setupEventListeners() {
    const whyButton = document.querySelector('.ai-recommendation-card .why-button');
    const whyExplanationDiv = document.querySelector('.ai-recommendation-card .why-explanation');

    if (whyButton && whyExplanationDiv) {
        whyButton.addEventListener('click', () => {
            const isHidden = whyExplanationDiv.style.display === 'none';
            whyExplanationDiv.style.display = isHidden ? 'block' : 'none';
        });
    }

    const setTableBody = document.getElementById('set-logging-tbody');
    if (setTableBody) {
        setTableBody.addEventListener('click', async (event) => {
            const target = event.target;
            const setRow = target.closest('tr');
            const setId = setRow ? setRow.dataset.setDbId : null;

            if (target.classList.contains('edit-set-btn')) {
                if (setId) handleEditSet(setId);
            } else if (target.classList.contains('save-set-btn')) {
                if (setId) await handleSaveSet(setId);
            } else if (target.classList.contains('cancel-edit-btn')) {
                if (setId) handleCancelEdit(setId);
            } else if (target.classList.contains('delete-set-btn')) {
                if (setId) await handleDeleteSet(setId);
            } else if (target.classList.contains('log-set-row-btn')) {
                // Logic for logging a brand new set from an input row
                const weightInput = setRow.querySelector('.weight-input');
                const repsInput = setRow.querySelector('.reps-input');
                const rirInput = setRow.querySelector('.rir-input');
                // const notesInput = setRow.querySelector('.notes-input'); // If new rows have notes

                if (weightInput && repsInput && rirInput) {
                    const weight = weightInput.value;
                    const reps = repsInput.value;
                    const rir = rirInput.value;
                    // const notes = notesInput ? notesInput.value : '';

                    // Call a modified logSet or a new function specifically for row-based logging
                    // This requires currentWorkoutId, currentExerciseId, and the set number.
                    // The set number for a new row is determined by its position or a counter.
                    const setNumber = Array.from(setTableBody.children).indexOf(setRow) + 1; // Simple way
                    await logNewSetFromRow(setRow, currentWorkoutId, currentExerciseId, setNumber, weight, reps, rir, '');
                }
            } else if (target.classList.contains('remove-new-set-btn')) {
                 if (setRow && setRow.classList.contains('new-set-row')) {
                    setRow.remove();
                    renumberSetsInUI(); // Renumber remaining sets
                }
            }
        });
    }

    const addSetButton = document.getElementById('add-set-btn');
    if (addSetButton) {
        addSetButton.addEventListener('click', () => {
            const setTableBody = document.getElementById('set-logging-tbody');
            const nextSetNumber = setTableBody.children.length + 1;
            addNewSetInputRow(nextSetNumber); // From workout_execution_ui.js
        });
    }

    // Other general event listeners (timer, next exercise, end workout)
    const shareWorkoutButton = document.getElementById('share-workout-btn');
    if (shareWorkoutButton) {
        shareWorkoutButton.addEventListener('click', handleShareWorkout);
    }

    const copyShareLinkButton = document.getElementById('copy-share-link-btn');
    if (copyShareLinkButton) {
        copyShareLinkButton.addEventListener('click', handleCopyShareLink);
    }

    // --- End Workout Modal Listeners ---
    const endWorkoutBtn = document.getElementById('end-workout-btn');
    const endWorkoutModal = document.getElementById('end-workout-modal');
    const closeEndWorkoutModalBtn = document.getElementById('close-end-workout-modal');
    const cancelEndWorkoutBtn = document.getElementById('cancel-end-workout-btn');
    const endWorkoutForm = document.getElementById('end-workout-form');

    if (endWorkoutBtn && endWorkoutModal) {
        endWorkoutBtn.addEventListener('click', () => {
            // Potentially pre-fill fatigue/stress if values exist from workout start
            const initialFatigue = endWorkoutModal.querySelector('#end-workout-fatigue');
            const initialStress = endWorkoutModal.querySelector('#end-workout-stress');
            // Example: if (workoutStartTimeData.fatigue) initialFatigue.value = workoutStartTimeData.fatigue;
            // Update slider display values as well
            if (initialFatigue) document.getElementById('end-workout-fatigue-value').textContent = initialFatigue.value;
            if (initialStress) document.getElementById('end-workout-stress-value').textContent = initialStress.value;

            endWorkoutModal.style.display = 'block';
        });
    }
    if (closeEndWorkoutModalBtn && endWorkoutModal) {
        closeEndWorkoutModalBtn.addEventListener('click', () => endWorkoutModal.style.display = 'none');
    }
    if (cancelEndWorkoutBtn && endWorkoutModal) {
        cancelEndWorkoutBtn.addEventListener('click', () => endWorkoutModal.style.display = 'none');
    }
    // Close modal if clicked outside of modal-content
    if (endWorkoutModal) {
        window.addEventListener('click', (event) => {
            if (event.target === endWorkoutModal) {
                endWorkoutModal.style.display = 'none';
            }
        });
    }

    // Slider value display updates
    const sleepSlider = document.getElementById('end-workout-sleep');
    const sleepValueSpan = document.getElementById('end-workout-sleep-value');
    if (sleepSlider && sleepValueSpan) {
        sleepSlider.addEventListener('input', () => sleepValueSpan.textContent = sleepSlider.value);
    }

    const stressSlider = document.getElementById('end-workout-stress');
    const stressValueSpan = document.getElementById('end-workout-stress-value');
    if (stressSlider && stressValueSpan) {
        stressSlider.addEventListener('input', () => stressValueSpan.textContent = stressSlider.value);
    }

    const fatigueSlider = document.getElementById('end-workout-fatigue'); // Assuming this exists from before
    const fatigueValueSpan = document.getElementById('end-workout-fatigue-value');
    if (fatigueSlider && fatigueValueSpan) {
        fatigueSlider.addEventListener('input', () => fatigueValueSpan.textContent = fatigueSlider.value);
    }


    if (endWorkoutForm && endWorkoutModal) {
        endWorkoutForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            await processEndWorkoutForm(endWorkoutModal);
        });
    }
}

async function processEndWorkoutForm(modalInstance) {
    if (!currentWorkoutId) {
        displayErrorMessage("No active workout to end.", "error");
        return;
    }

    const fatigueLevel = document.getElementById('end-workout-fatigue').value;
    const sleepHours = document.getElementById('end-workout-sleep').value;
    const hrvMsInput = document.getElementById('end-workout-hrv').value;
    const stressLevel = document.getElementById('end-workout-stress').value;
    const notes = document.getElementById('end-workout-notes').value;

    const hrvMs = hrvMsInput ? parseFloat(hrvMsInput) : null;

    const payload = {
        completed_at: new Date().toISOString(),
        fatigue_level: parseFloat(fatigueLevel),
        sleep_hours: parseFloat(sleepHours),
        stress_level: parseInt(stressLevel),
        notes: notes
    };
    if (hrvMs !== null && !isNaN(hrvMs)) {
        payload.hrv_ms = hrvMs;
    }

    const saveButton = document.getElementById('save-and-end-workout-btn');
    const originalButtonText = saveButton.textContent;
    saveButton.disabled = true;
    saveButton.innerHTML = '<span class="loader-small"></span> Ending...';
    showLoadingState(true);

    try {
        // Assuming the backend endpoint for updating a workout is PUT /v1/workouts/{workout_id}
        // This endpoint might need to be created or confirmed.
        const response = await fetch(`${API_BASE_URL}/v1/workouts/${currentWorkoutId}`, {
            method: 'PUT', // Or PATCH if only sending these fields
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to finalize workout details" }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }

        displayErrorMessage("Workout finalized and saved!", "success");
        modalInstance.style.display = 'none';

        // Use the global workoutFlowManager to truly end the workout flow
        if (window.workoutFlowManager && typeof window.workoutFlowManager.endWorkout === 'function') {
            // Pass false to prevent double API call if endWorkout in flow manager also calls API.
            // For this case, we've already updated the workout, so just clear local state and navigate.
            await window.workoutFlowManager.endWorkout(true, true); // First true: navigate, Second true: local clear only
        } else {
            // Fallback if workoutFlowManager is not on window or endWorkout is different
            localStorage.removeItem('workoutFlowState'); // Minimal cleanup
            window.location.href = 'index.html'; // Navigate home or to dashboard
        }

    } catch (error) {
        console.error("Error finalizing workout:", error);
        displayErrorMessage(`Error finalizing workout: ${error.message}`, "error");
    } finally {
        saveButton.disabled = false;
        saveButton.innerHTML = originalButtonText;
        showLoadingState(false);
    }
}


async function handleShareWorkout() {
    if (!currentWorkoutId) {
        displayErrorMessage("No active workout to share. Workout ID is missing.", "error");
        return;
    }

    const shareButton = document.getElementById('share-workout-btn');
    const originalButtonText = shareButton.textContent;
    shareButton.disabled = true;
    shareButton.innerHTML = '<span class="loader-small"></span> Sharing...';
    showLoadingState(true); // Potentially disable other major actions

    try {
        const response = await fetch(`${API_BASE_URL}/v1/share/workout/${currentWorkoutId}`, {
            method: 'POST',
            headers: getAuthHeaders(), // Ensure this provides the JWT token
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to create share link" }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }

        const result = await response.json();
        const shareUrl = result.share_url;
        const expiresAt = result.expires_at; // Get expiry date

        const shareLinkDisplay = document.getElementById('share-link-display');
        const shareLinkContainer = document.getElementById('share-link-container');
        const expiryInfoPara = shareLinkContainer.querySelector('p:last-child'); // Assuming last p is expiry info


        if (shareLinkDisplay && shareLinkContainer) {
            shareLinkDisplay.value = shareUrl;
            if (expiryInfoPara && expiresAt) {
                 try {
                    const expiryDate = new Date(expiresAt);
                    expiryInfoPara.textContent = `This link will expire on ${expiryDate.toLocaleDateString()} at ${expiryDate.toLocaleTimeString()}.`;
                } catch (e) {
                    expiryInfoPara.textContent = `Link expiry: ${expiresAt}`; // Fallback
                }
            } else if (expiryInfoPara) {
                 expiryInfoPara.textContent = `This link will expire in 7 days.`; // Default if not in response
            }
            shareLinkContainer.style.display = 'block';
            displayErrorMessage("Share link created! It's now visible below the workout controls.", "success");
        } else {
            // Fallback if specific display elements are missing
            alert(`Share link created: ${shareUrl}`);
        }

    } catch (error) {
        console.error("Error sharing workout:", error);
        displayErrorMessage(`Error sharing workout: ${error.message}`, "error");
    } finally {
        shareButton.disabled = false;
        shareButton.innerHTML = originalButtonText;
        showLoadingState(false);
    }
}

function handleCopyShareLink() {
    const shareLinkDisplay = document.getElementById('share-link-display');
    const copyFeedbackMsg = document.getElementById('copy-feedback-msg');

    if (!shareLinkDisplay || !copyFeedbackMsg) return;

    shareLinkDisplay.select(); // Select the text
    shareLinkDisplay.setSelectionRange(0, 99999); // For mobile devices

    try {
        navigator.clipboard.writeText(shareLinkDisplay.value)
            .then(() => {
                copyFeedbackMsg.textContent = "Copied to clipboard!";
                setTimeout(() => { copyFeedbackMsg.textContent = ""; }, 3000);
            })
            .catch(err => {
                console.error('Failed to copy text: ', err);
                copyFeedbackMsg.textContent = "Failed to copy. Please copy manually.";
                copyFeedbackMsg.style.color = "red";
                setTimeout(() => {
                    copyFeedbackMsg.textContent = "";
                    copyFeedbackMsg.style.color = "green"; // Reset color
                }, 3000);
            });
    } catch (err) {
        // Fallback for older browsers (less common now)
        console.error('Clipboard API not available: ', err);
        try {
            document.execCommand('copy');
            copyFeedbackMsg.textContent = "Copied (fallback method)!";
            setTimeout(() => { copyFeedbackMsg.textContent = ""; }, 3000);
        } catch (execErr) {
            console.error('Fallback copy failed: ', execErr);
            copyFeedbackMsg.textContent = "Failed to copy. Please copy manually.";
            copyFeedbackMsg.style.color = "red";
            setTimeout(() => {
                copyFeedbackMsg.textContent = "";
                copyFeedbackMsg.style.color = "green"; // Reset color
            }, 3000);
        }
    }
}


// Main initialization function for the workout execution page
async function initWorkoutExecutionPage() {
    console.log("Initializing Workout Execution Page...");

    const urlParams = new URLSearchParams(window.location.search);
    currentWorkoutId = urlParams.get('workoutId');
    currentExerciseId = urlParams.get('exerciseId');

    currentUserId = getUserId(); // Assuming getUserId() is available (e.g. from app.js or localStorage)

    if (!currentUserId) {
        console.error("User not logged in or User ID not found.");
        displayErrorMessage("User not identified. Please login again.", "error");
        // Potentially redirect to login page or disable page functionality
        showLoadingState(false);
        return;
    }
    if (!currentWorkoutId || !currentExerciseId) {
        console.error("Workout ID or Exercise ID missing from URL.");
        displayErrorMessage("Workout or Exercise ID missing. Cannot load page.", "error");
        // Potentially redirect or show a message to the user
        showLoadingState(false);
        return;
    }

    showLoadingState(true);

    // Fetch exercise details to display name (optional, but good UX)
    try {
        const exerciseDetails = await fetchExerciseDetails(currentExerciseId);
        updateExerciseName(exerciseDetails.name); // From workout_execution_ui.js
    } catch (error) {
        console.error("Failed to fetch exercise details:", error);
        updateExerciseName(`Exercise ID: ${currentExerciseId.substring(0,8)}...`);
    }

    await fetchAndDisplayExistingSets();
    await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId);
    await fetchAndDisplayPreviousPerformance(currentExerciseId, currentUserId);

    setupEventListeners();
    showLoadingState(false);
}

// --- Set Renumbering ---
function renumberSetsInUI() {
    const setTableBody = document.getElementById('set-logging-tbody');
    if (setTableBody) {
        const rows = setTableBody.querySelectorAll('tr');
        rows.forEach((row, index) => {
            const setNumberCell = row.querySelector('.set-number');
            if (setNumberCell) {
                setNumberCell.textContent = index + 1;
            }
            // Update set_number in cached data if this row corresponds to a cached item
            // This is important if a new set is logged after deletion, its number should be correct.
            const setId = row.dataset.setDbId;
            if (setId) {
                const cachedSet = setsDataCache.find(s => s.id === setId);
                if (cachedSet) {
                    cachedSet.set_number = index + 1;
                }
            }
        });
    }
}


// --- Edit/Cancel Set Handlers ---
function handleEditSet(setId) {
    if (currentlyEditingSetId && currentlyEditingSetId !== setId) {
        // Another set is being edited, cancel that edit first
        handleCancelEdit(currentlyEditingSetId, false); // false to not re-fetch recommendations yet
    }

    const setRow = document.querySelector(`tr[data-set-db-id="${setId}"]`);
    const setData = setsDataCache.find(s => s.id === setId);

    if (!setRow || !setData) {
        displayErrorMessage("Could not find set data to edit.", "error");
        return;
    }

    currentlyEditingSetId = setId;
    const editRow = renderSetRow(setData, true); // Get the new row in edit mode
    setRow.parentNode.replaceChild(editRow, setRow); // Replace the old row with the new edit-mode row
}

function handleCancelEdit(setId, triggerRecommendationFetch = true) {
    const setRow = document.querySelector(`tr[data-set-db-id="${setId}"]`);
    const originalSetData = setsDataCache.find(s => s.id === setId);

    if (!setRow || !originalSetData) {
        // Row might have been removed or data not found, effectively "cancelled"
        console.warn(`Cancel edit: Set row or data for ID ${setId} not found.`);
        if (currentlyEditingSetId === setId) currentlyEditingSetId = null;
        return;
    }

    // Restore original row content (from cache)
    const displayRow = renderSetRow(originalSetData, false);
    setRow.parentNode.replaceChild(displayRow, setRow);

    if (currentlyEditingSetId === setId) {
        currentlyEditingSetId = null;
    }

    if (triggerRecommendationFetch) {
        // Usually not needed on cancel unless some global state changed.
        // For now, let's assume no re-fetch is needed on pure cancel.
    }
}


// --- Log New Set from Row Handler ---
async function logNewSetFromRow(setRowEl, workoutId, exerciseId, setNumber, weight, reps, rir, notes) {
    // Basic validation (can be expanded or made more robust)
    const weightVal = parseFloat(weight);
    const repsVal = parseInt(reps);
    const rirVal = rir === '' || rir === null || rir === undefined ? null : parseInt(rir);

    if (isNaN(weightVal) || weightVal < 0) {
        displayErrorMessage("Invalid weight for new set.", "error"); return;
    }
    if (isNaN(repsVal) || repsVal < 0) {
        displayErrorMessage("Invalid reps for new set.", "error"); return;
    }
    if (rirVal !== null && (isNaN(rirVal) || rirVal < 0 || rirVal > 10)) {
        displayErrorMessage("Invalid RIR for new set. Must be 0-10 or empty.", "error"); return;
    }

    const payload = {
        exercise_id: exerciseId,
        set_number: setNumber, // The UI-determined set number for this new set
        actual_weight: weightVal,
        actual_reps: repsVal,
        actual_rir: rirVal,
        notes: notes || '', // Ensure notes is not undefined
        // completed_at could be set here if desired, or backend defaults it
    };

    const logButton = setRowEl.querySelector('.log-set-row-btn');
    const originalButtonText = logButton ? logButton.textContent : 'Log';
    if (logButton) {
        logButton.disabled = true;
        logButton.innerHTML = '<span class="loader-small"></span> Logging...';
    }
    showLoadingState(true); // Broader UI loading state

    try {
        const response = await fetch(`${API_BASE_URL}/v1/workouts/${workoutId}/sets`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to log new set" }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }
        const newSetData = await response.json(); // API returns the created set with its ID, MTI, etc.

        // Add to cache
        setsDataCache.push(newSetData);
        // Sort cache again by set_number to be sure, though new set should be last if numbers are sequential
        setsDataCache.sort((a, b) => a.set_number - b.set_number);


        // Replace the input row with a display row
        const displayRow = renderSetRow(newSetData, false);
        setRowEl.parentNode.replaceChild(displayRow, setRowEl);

        renumberSetsInUI(); // Ensure all numbers are correct after adding
        displayErrorMessage("Set logged successfully!", "success");
        await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId);
        await fetchAndDisplayPreviousPerformance(currentExerciseId, currentUserId);


    } catch (error) {
        console.error("Error logging new set:", error);
        displayErrorMessage(`Error logging set: ${error.message}`, "error");
        if (logButton) logButton.disabled = false; // Re-enable button on error
    } finally {
        if (logButton) {
            logButton.disabled = false;
            logButton.textContent = originalButtonText;
        }
        showLoadingState(false);
    }
}


// --- Save Set Handler ---
async function handleSaveSet(setId) {
    const editRow = document.querySelector(`tr[data-set-db-id="${setId}"]`);
    if (!editRow || !editRow.classList.contains('editing')) {
        displayErrorMessage("Could not find set to save or not in edit mode.", "error");
        return;
    }

    const weightInput = editRow.querySelector('.weight-input');
    const repsInput = editRow.querySelector('.reps-input');
    const rirInput = editRow.querySelector('.rir-input');
    const notesInput = editRow.querySelector('.notes-input'); // Assuming notes input is present in edit mode

    // Basic Validation
    const newWeight = parseFloat(weightInput.value);
    const newReps = parseInt(repsInput.value);
    const newRir = rirInput.value === '' ? null : parseInt(rirInput.value); // Allow empty RIR for null
    const newNotes = notesInput ? notesInput.value : '';

    if (isNaN(newWeight) || newWeight < 0) {
        displayErrorMessage("Invalid weight value.", "error"); return;
    }
    if (isNaN(newReps) || newReps < 0) {
        displayErrorMessage("Invalid reps value.", "error"); return;
    }
    if (newRir !== null && (isNaN(newRir) || newRir < 0 || newRir > 10)) { // RIR scale 0-10
        displayErrorMessage("Invalid RIR value. Must be 0-10 or empty.", "error"); return;
    }

    const payload = {
        actual_weight: newWeight,
        actual_reps: newReps,
        actual_rir: newRir,
        notes: newNotes
    };

    // Filter out fields that haven't changed from original data to send minimal payload
    // This is optional; sending all fields is also fine if backend handles it.
    // For simplicity now, sending all editable fields.

    showLoadingState(true);
    try {
        const response = await fetch(`${API_BASE_URL}/v1/sets/${setId}`, {
            method: 'PATCH',
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to save set" }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }
        // Assuming the API returns the updated set data or just a success message.
        // If it returns the set, use that. Otherwise, merge payload into cached data.
        // const updatedSetFromServer = await response.json(); // If API returns full updated set

        // Update cache
        const cachedSetIndex = setsDataCache.findIndex(s => s.id === setId);
        if (cachedSetIndex > -1) {
            // Update only the changed fields and what the API might have updated (e.g., MTI if recalculated by backend)
            // For now, merge known payload fields. If API returns the set, use that.
            // Let's assume the PATCH doesn't return the full set, just success.
            // We need to re-calculate MTI locally or have the backend return it.
            // For now, let's just update with payload and mark MTI as needing refresh.
            setsDataCache[cachedSetIndex] = { ...setsDataCache[cachedSetIndex], ...payload, mti: null }; // Mark MTI as needing update
        }

        // Re-render the row in display mode
        updateSetRowDisplay(setId, setsDataCache[cachedSetIndex]); // from workout_execution_ui.js
        currentlyEditingSetId = null;

        displayErrorMessage("Set updated successfully!", "success"); // Simple success message
        await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId); // Re-fetch recommendations

    } catch (error) {
        console.error("Error saving set:", error);
        displayErrorMessage(`Error saving set: ${error.message}`, "error");
        // Optionally, leave row in edit mode on error
    } finally {
        showLoadingState(false);
    }
}

// --- Delete Set Handler ---
async function handleDeleteSet(setId) {
    if (currentlyEditingSetId === setId) {
        // If deleting the set that is currently being edited, cancel edit mode first
        handleCancelEdit(setId, false); // Don't trigger recommendations yet
    }

    if (!confirm("Are you sure you want to delete this set? This action cannot be undone.")) {
        return;
    }

    showLoadingState(true);
    try {
        const response = await fetch(`${API_BASE_URL}/v1/sets/${setId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: "Failed to delete set" }));
            throw new Error(errorData.error || `HTTP error ${response.status}`);
        }

        // Remove from UI
        const setRow = document.querySelector(`tr[data-set-db-id="${setId}"]`);
        if (setRow) {
            setRow.remove();
        }

        // Remove from cache
        setsDataCache = setsDataCache.filter(s => s.id !== setId);

        renumberSetsInUI(); // Renumber remaining sets
        displayErrorMessage("Set deleted successfully.", "success");
        await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId); // Re-fetch recommendations

    } catch (error) {
        console.error("Error deleting set:", error);
        displayErrorMessage(`Error deleting set: ${error.message}`, "error");
    } finally {
        showLoadingState(false);
    }
}


async function fetchExerciseDetails(exerciseId) {
    const response = await fetch(`${API_BASE_URL}/v1/exercises/${exerciseId}`, { headers: getAuthHeaders() });
    if (!response.ok) throw new Error('Failed to fetch exercise details');
    return response.json();
}

async function fetchAndDisplayExistingSets() {
    if (!currentWorkoutId) {
        console.warn("No currentWorkoutId, cannot fetch existing sets.");
        clearSetTable(); // From workout_execution_ui.js
        return;
    }
    try {
        const response = await fetch(`${API_BASE_URL}/v1/workouts/${currentWorkoutId}/sets?exercise_id=${currentExerciseId}`, {
            method: 'GET',
            headers: getAuthHeaders()
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || "Failed to fetch sets");
        }
        const result = await response.json();
        setsDataCache = result.data || []; // Store sets in cache

        clearSetTable(); // From workout_execution_ui.js
        const setTableBody = document.getElementById('set-logging-tbody');
        if (setTableBody) {
            setsDataCache.forEach(set => {
                // Ensure set_number is present, default if not (should be from DB)
                if (set.set_number === undefined || set.set_number === null) {
                    console.warn("Set data missing set_number, assigning based on order:", set);
                    // This indicates a data issue if set_number isn't reliably returned by API for existing sets
                }
                // The renderSetRow function expects set_number.
                // If it's missing from API for some reason, need to handle it.
                // For now, assume API provides it.
                setTableBody.appendChild(renderSetRow(set, false)); // renderSetRow from workout_execution_ui.js
            });
            renumberSetsInUI(); // Ensure UI numbering is correct after initial load
        }
    } catch (error) {
        console.error("Error fetching existing sets:", error);
        displayErrorMessage(`Error loading sets: ${error.message}`, "error");
    }
}


async function fetchAndDisplayPreviousPerformance(exerciseId, userId) {
    const lastTimePerfEl = document.querySelector('.performance-comparison .last-time-performance');
    const improvementMetricEl = document.querySelector('.performance-comparison .improvement-metric');

    if (!lastTimePerfEl || !improvementMetricEl) {
        console.error("Previous performance panel elements not found.");
        return;
    }

    // Loading state
    lastTimePerfEl.innerHTML = '<div class="loader-container" style="min-height: 50px; padding: 10px;"><span class="loader" style="width:20px; height:20px; border-width:3px;"></span> Loading...</div>';
    improvementMetricEl.textContent = ""; // Clear it, or show a mini-loader too
    improvementMetricEl.classList.remove('negative'); // Reset styling

    if (!exerciseId) { // userId is implicitly handled by auth token for this specific endpoint as per prompt
        console.warn("Exercise ID is missing for previous performance.");
        lastTimePerfEl.textContent = "Exercise not specified.";
        improvementMetricEl.textContent = "--";
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/workouts/exercise/${exerciseId}/previous-performance`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            if (response.status === 404) { // Specific handling for "not found"
                lastTimePerfEl.textContent = "No previous performance recorded for this exercise.";
                improvementMetricEl.textContent = "First time doing this exercise?";
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Failed to fetch previous performance." }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            return; // Exit after handling non-OK response
        }

        const data = await response.json();

        if (data && data.previous_set) {
            const prev = data.previous_set;
            lastTimePerfEl.textContent = `Last time: ${prev.weight_kg || '--'}kg × ${prev.reps || '--'} @ ${prev.rir === null || prev.rir === undefined ? '--' : prev.rir} RIR`;

            if (data.progression_metric_string) {
                improvementMetricEl.textContent = data.progression_metric_string;
                if (data.is_positive_progression === false) { // Check for explicitly false
                    improvementMetricEl.classList.add('negative');
                } else {
                     // Default is positive or neutral, green styling applies
                    improvementMetricEl.classList.remove('negative');
                }
            } else {
                // Fallback if no progression string, just show previous data or simple diff if possible
                improvementMetricEl.textContent = "Previous data loaded.";
            }
        } else {
            lastTimePerfEl.textContent = "No previous performance data found.";
            improvementMetricEl.textContent = "Ready to set a new PR!";
        }

    } catch (error) {
        console.error("Error fetching previous performance:", error);
        lastTimePerfEl.textContent = "Could not load previous performance.";
        improvementMetricEl.textContent = `Error: ${error.message.substring(0, 30)}...`; // Show a snippet of the error
    }
}

// Function to add a logged set to the history table
function addSetToTable(set) {
    const historyTableBody = document.querySelector('.set-history-table tbody');
    if (!historyTableBody) {
        console.error("Set history table body not found.");
        return;
    }

    const row = historyTableBody.insertRow();
    // Columns: Set #, Weight, Reps, RIR, Date/Time (optional, or just order)
    // Assuming 'set' object has properties like: set_number, weight_kg, reps, rir_value
    // If set_number is not directly available, count existing rows or manage it externally.
    const setNumber = historyTableBody.rows.length; // Simple set number based on rows

    row.insertCell().textContent = setNumber;
    row.insertCell().textContent = `${set.weight_kg} kg`;
    row.insertCell().textContent = set.reps;
    row.insertCell().textContent = set.rir !== null && set.rir !== undefined ? set.rir : 'N/A'; // Handle optional RIR
    // Optionally, add a timestamp or notes if available in 'set'
    // row.insertCell().textContent = new Date(set.timestamp).toLocaleTimeString();
}

let restTimerInterval = null;
let restTimerSecondsRemaining = 0;

// Function to start/update the rest timer
function startRestTimer(durationInSeconds) {
    const timerDisplay = document.getElementById('restTimerDisplay'); // Assuming an element with this ID shows the time
    const startTimerButton = document.getElementById('startRestTimerButton'); // Assuming a button to manually start/add time
    const stopTimerButton = document.getElementById('stopRestTimerButton'); // Assuming a button to stop/reset

    if (!timerDisplay) {
        console.error("Rest timer display element not found.");
        return;
    }

    if (restTimerInterval) {
        clearInterval(restTimerInterval); // Clear any existing timer
    }

    restTimerSecondsRemaining = durationInSeconds;

    function updateTimerDisplay() {
        const minutes = Math.floor(restTimerSecondsRemaining / 60);
        const seconds = restTimerSecondsRemaining % 60;
        timerDisplay.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    }

    updateTimerDisplay(); // Initial display

    restTimerInterval = setInterval(() => {
        restTimerSecondsRemaining--;
        updateTimerDisplay();

        if (restTimerSecondsRemaining <= 0) {
            clearInterval(restTimerInterval);
            timerDisplay.textContent = "Time's up!";
            // Optionally, play a sound or show a more prominent notification
            // alert("Rest period finished!");
            if (startTimerButton) startTimerButton.disabled = false; // Re-enable start button
            if (stopTimerButton) stopTimerButton.textContent = 'Reset Timer';
        }
    }, 1000);

    if (startTimerButton) startTimerButton.disabled = true; // Disable start button while timer is running
    if (stopTimerButton) {
        stopTimerButton.textContent = 'Stop Timer'; // Change text to "Stop"
        stopTimerButton.onclick = function() { // Make stop button functional
            clearInterval(restTimerInterval);
            restTimerSecondsRemaining = 0;
            updateTimerDisplay();
            timerDisplay.textContent = "0:00";
            if (startTimerButton) startTimerButton.disabled = false;
            stopTimerButton.textContent = 'Reset Timer';
        };
    }
}


// DOMContentLoaded listener
document.addEventListener('DOMContentLoaded', initWorkoutExecutionPage);

// Basic Auth/Helper function placeholders (assuming they exist elsewhere, e.g. app.js or config.js)
// These are simplified and might need to be adapted based on actual shared code.
if (typeof getAuthToken !== 'function') {
    window.getAuthToken = function() { return localStorage.getItem('accessToken'); }
}
if (typeof getUserId !== 'function') {
    window.getUserId = function() { return localStorage.getItem('userId'); }
}
if (typeof getAuthHeaders !== 'function') {
    window.getAuthHeaders = function() {
        const token = getAuthToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }
}
// Ensure API_BASE_URL is defined (e.g., from config.js or globally)
if (typeof API_BASE_URL === 'undefined') {
    window.API_BASE_URL = 'http://localhost:5000'; // Default if not set
    console.warn("API_BASE_URL was not defined, using default http://localhost:5000");
}
