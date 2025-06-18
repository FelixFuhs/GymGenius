// Assuming API_BASE_URL, getUserId, getAuthToken, getAuthHeaders are globally available
// or will be imported/defined in a shared utility file later.

// For testing purposes, these might be hardcoded or fetched from URL params later.
let currentExerciseId = 'e078a34a-7060-4624-94f2-1020f80d53ce'; // Example Squat ID
let currentUserId = null; // Will be fetched by getUserId()

// Store the fetched explanation globally or re-fetch if panel is re-rendered often.
let aiExplanation = "Explanation will be loaded from the AI.";

const DEFAULT_REST_DURATION = 90; // 90 seconds

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
        weightDisplay.textContent = `${data.recommended_weight_kg} kg`;
        repRangeDisplay.textContent = `${data.target_reps_low} - ${data.target_reps_high} reps @ ${data.target_rir} RIR`;

        const confidencePercent = (data.confidence_score * 100).toFixed(0);
        confidenceFill.style.width = `${confidencePercent}%`;
        confidenceFill.textContent = `${confidencePercent}% confident`;

        aiExplanation = data.explanation; // Store for "Why?" button
        whyExplanationP.textContent = aiExplanation; // Pre-populate, though div is hidden
    } else {
        // Reset to placeholders or error message
        weightDisplay.textContent = "-- kg";
        repRangeDisplay.textContent = "-- reps @ -- RIR";
        confidenceFill.style.width = `0%`;
        confidenceFill.textContent = `Error loading`;
        aiExplanation = "Could not load explanation.";
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

    if (!weightDisplay || !repRangeDisplay || !confidenceFill || !whyButton) return;

    if (isLoading) {
        weightDisplay.textContent = "Loading...";
        repRangeDisplay.textContent = "Calculating...";
        confidenceFill.style.width = `0%`;
        confidenceFill.textContent = `Loading...`;
        whyButton.disabled = true;
    } else {
        // Content will be updated by updateAIRecommendationPanel
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
        const response = await fetch(`${API_BASE_URL}/v1/user/${userId}/exercise/${exerciseId}/recommend-set-parameters`, {
            headers: getAuthHeaders()
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: "Failed to fetch AI recommendations. Network error or invalid response." }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        updateAIRecommendationPanel(data);

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

function setupEventListeners() {
    const whyButton = document.querySelector('.ai-recommendation-card .why-button');
    const whyExplanationDiv = document.querySelector('.ai-recommendation-card .why-explanation');

    if (whyButton && whyExplanationDiv) {
        whyButton.addEventListener('click', () => {
            const isHidden = whyExplanationDiv.style.display === 'none';
            whyExplanationDiv.style.display = isHidden ? 'block' : 'none';
            // Explanation text is already set by updateAIRecommendationPanel
        });
    }

    // Event listener for the set logging form
    const setLoggingForm = document.getElementById('setLoggingForm'); // Assuming your form has this ID
    if (setLoggingForm) {
        setLoggingForm.addEventListener('submit', async function(event) {
            event.preventDefault(); // Prevent default form submission

            const weightInput = document.getElementById('weightInput'); // Assuming ID for weight input
            const repsInput = document.getElementById('repsInput');   // Assuming ID for reps input
            const rirInput = document.getElementById('rirInput');     // Assuming ID for RIR input

            if (!weightInput || !repsInput || !rirInput) {
                console.error("Set logging form input elements not found.");
                alert("Error: Could not find form input fields.");
                return;
            }

            const weight = weightInput.value;
            const reps = repsInput.value;
            const rir = rirInput.value;

            await logSet(weight, reps, rir);
        });
    } else {
        console.warn("Set logging form #setLoggingForm not found.");
    }

    // Add other event listeners here (e.g., for timer buttons if not handled in startRestTimer)
    const manualStartTimerButton = document.getElementById('startRestTimerButton');
    if (manualStartTimerButton) {
        manualStartTimerButton.addEventListener('click', () => {
            // Potentially get duration from an input field if you want configurable manual start
            startRestTimer(DEFAULT_REST_DURATION);
        });
    }
}

// Main initialization function for the workout execution page
async function initWorkoutExecutionPage() {
    console.log("Initializing Workout Execution Page...");

    // Attempt to get User ID from storage
    currentUserId = getUserId();
    if (!currentUserId) {
        console.error("User not logged in or User ID not found. Cannot initialize page.");
        // Potentially redirect to login or display a global error message
        // For now, AI panel will show an error due to missing userId in fetch.
    }

    // How exerciseId is passed to this page needs to be determined.
    // For now, using the hardcoded currentExerciseId.
    // Example: Get from URL query parameter `exerciseId`
    // const urlParams = new URLSearchParams(window.location.search);
    // const exerciseIdFromUrl = urlParams.get('exerciseId');
    // if (exerciseIdFromUrl) {
    //     currentExerciseId = exerciseIdFromUrl;
    // } else {
    //     console.warn("No exerciseId in URL, using default/hardcoded for AI Rec.");
    // }
    const exerciseNamePlaceholder = document.getElementById('exercise-name-placeholder');
    if (exerciseNamePlaceholder && currentExerciseId) {
        // In a real app, you'd fetch exercise details based on currentExerciseId
        // For now, just show the ID or a generic name if you have it
        exerciseNamePlaceholder.textContent = `Exercise ID: ${currentExerciseId.substring(0,8)}...`;
    }


    await fetchAndDisplayAIRecommendations(currentExerciseId, currentUserId);
    setupEventListeners();

    // Initialize other panels
    // initSetLogger(); // Placeholder for future function
    // initRestTimer(); // Placeholder for future function
    await fetchAndDisplayPreviousPerformance(currentExerciseId, currentUserId);
}

async function fetchAndDisplayPreviousPerformance(exerciseId, userId) {
    const lastTimePerfEl = document.querySelector('.performance-comparison .last-time-performance');
    const improvementMetricEl = document.querySelector('.performance-comparison .improvement-metric');

    if (!lastTimePerfEl || !improvementMetricEl) {
        console.error("Previous performance panel elements not found.");
        return;
    }

    // Loading state
    lastTimePerfEl.textContent = "Loading previous performance...";
    improvementMetricEl.textContent = "Calculating...";
    improvementMetricEl.classList.remove('negative'); // Reset styling

    if (!exerciseId) { // userId is implicitly handled by auth token for this specific endpoint as per prompt
        console.warn("Exercise ID is missing for previous performance.");
        lastTimePerfEl.textContent = "Select an exercise.";
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
