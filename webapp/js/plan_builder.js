// Plan Builder specific JavaScript

const API_BASE_URL = 'http://localhost:5000'; // Define your backend API base URL

// Auth helper functions (assuming token and userId are stored in localStorage after login)
function getAuthToken() {
    return localStorage.getItem('accessToken');
}

function getUserId() {
    return localStorage.getItem('userId');
}

function getAuthHeaders() {
    const token = getAuthToken();
    const headers = {
        'Content-Type': 'application/json',
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}


document.addEventListener('DOMContentLoaded', () => {
    console.log('Plan Builder script loaded');

    // Function to detect touch devices
    function isTouchDevice() {
        return ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || (navigator.msMaxTouchPoints > 0);
    }

    // Display message for touch devices
    if (isTouchDevice()) {
        const planCreationArea = document.getElementById('plan-creation-area'); // Or another suitable parent
        if (planCreationArea) {
            const touchMessage = document.createElement('div');
            touchMessage.id = 'touch-device-message';
            touchMessage.innerHTML = '<p><strong>Note:</strong> For the best experience with drag-and-drop plan editing, we recommend using a desktop or laptop. Touchscreen drag-and-drop may have limitations.</p>';
            // Prepend to planCreationArea or insert before a specific element
            if (planCreationArea.firstChild) {
                planCreationArea.insertBefore(touchMessage, planCreationArea.firstChild);
            } else {
                planCreationArea.appendChild(touchMessage);
            }
        }
    }

    // Fetch exercises from API
    function fetchExercises() {
        const exerciseListContainer = document.getElementById('exercise-list-container'); // Assuming parent container
        if (exerciseListContainer) {
            exerciseListContainer.innerHTML = '<div class="loader-container"><span class="loader"></span> Loading exercises...</div>';
        }

        // Assuming /v1/exercises does not require auth based on backend review.
        return fetch(`${API_BASE_URL}/v1/exercises`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => data.data || []) // The exercises are in a "data" property
            .catch(err => {
                console.error('Failed to fetch exercises:', err);
                if (exerciseListContainer) {
                    exerciseListContainer.innerHTML = '<p style="color: red;">Failed to load exercises. Please try again later.</p>';
                }
                // alert('Failed to load exercises. Please try again later.'); // Alert might be too intrusive
                return [];
            })
            .finally(() => {
                // If the container was replaced by an error message, this won't run for it, which is fine.
                // If successful, displayExercises will populate the actual exerciseListElement.
                // If exerciseListContainer itself was the target for exercises, ensure displayExercises clears the loader.
            });
    }

    const exerciseListElement = document.getElementById('exercise-list'); // This is the UL inside the container
    const dropZoneElement = document.getElementById('drop-zone');
    const volumeListElement = document.getElementById('volume-list');
    const frequencyListElement = document.getElementById('frequency-list');
    const savePlanButton = document.getElementById('save-plan');
    const loadPlansButton = document.getElementById('load-plan');
    const clearPlanButton = document.getElementById('clear-plan');
    const planSaveFeedbackDiv = document.getElementById('plan-save-feedback');
    const feedbackTotalVolumeSpan = document.getElementById('feedback-total-volume');
    const feedbackFrequencyListUl = document.getElementById('feedback-frequency-list');
    const userPlansListElement = document.getElementById('user-plans-list');
    const planNameInput = document.getElementById('plan-name'); // Assuming an input field for plan name

    let currentPlanExercises = [];
    let availableExercises = [];
    let currentLoadedPlanId = null;
    let currentLoadedPlanName = "My New Plan"; // Default or loaded plan name

    // Update Save Button Text
    function updateSaveButtonText() {
        if (savePlanButton) {
            savePlanButton.textContent = currentLoadedPlanId ? 'Update Plan' : 'Save New Plan';
        }
    }

    // Function to display exercises fetched from API
    function displayExercises(exercises) {
        if (!exerciseListElement) return;
        exerciseListElement.innerHTML = ''; // Clear existing list
        exercises.forEach(exercise => {
            const listItem = document.createElement('li');
            listItem.id = `exercise-item-${exercise.id}`; // Add unique ID for potential direct manipulation
            listItem.textContent = `${exercise.name} (${exercise.type} - ${exercise.muscleGroup})`;
            listItem.setAttribute('draggable', true);
            listItem.setAttribute('data-exercise-id', exercise.id);
            listItem.addEventListener('dragstart', handleDragStart);
            listItem.addEventListener('dragend', handleDragEnd); // Add dragend listener
            exerciseListElement.appendChild(listItem);
        });
    }

    // --- Drag and Drop Handlers ---
    function handleDragStart(event) {
        console.log('Drag start for exercise ID:', event.target.dataset.exerciseId);
        event.dataTransfer.setData('text/plain', event.target.dataset.exerciseId);
        event.dataTransfer.effectAllowed = 'move';
        event.target.classList.add('dragging');
    }

    function handleDragEnd(event) {
        event.target.classList.remove('dragging');
    }

    function handleDragOver(event) {
        event.preventDefault(); // Necessary to allow drop
        if (dropZoneElement) {
            dropZoneElement.classList.add('drag-over');
        }
        // Placeholder for visual feedback
    }

    function handleDragLeave(event) {
        if (dropZoneElement) {
            dropZoneElement.classList.remove('drag-over');
        }
    }

    function handleDrop(event) {
        event.preventDefault();
        if (dropZoneElement) {
            dropZoneElement.classList.remove('drag-over');
        }
        const exerciseId = event.dataTransfer.getData('text/plain');
        console.log('Dropped exercise ID in plan:', exerciseId);

        // Avoid adding duplicates if an exercise is already in the plan by ID
        const isAlreadyInPlan = currentPlan.some(ex => ex.id.toString() === exerciseId);
        if (isAlreadyInPlan) {
            console.log('Exercise already in plan:', exerciseId);
            alert('This exercise is already in your current plan.');
            return;
        }

        const exerciseFromList = availableExercises.find(ex => ex.id.toString() === exerciseId);
        if (exerciseFromList) {
            // Add default sets/reps when adding from list
            const exerciseToAdd = {
                ...exerciseFromList,
                sets: 3, // Default sets
                reps: 10 // Default reps
            };
            addExerciseToPlan(exerciseToAdd);
        }
    }

    // --- Plan Management Functions ---
    function addExerciseToPlan(exercise) {
        if (planSaveFeedbackDiv) {
            planSaveFeedbackDiv.style.display = 'none';
            if (feedbackTotalVolumeSpan) feedbackTotalVolumeSpan.textContent = 'N/A';
            if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '';
        }
        // Ensure exercise has default sets/reps if not provided (e.g. when dragged)
        const exerciseToAdd = {
            ...exercise,
            sets: exercise.sets || 3, // Default sets
            reps: exercise.reps || 10 // Default reps
        };
        currentPlanExercises.push(exerciseToAdd);
        renderPlan();
        calculatePlanDetails();
        console.log('Current plan exercises:', currentPlanExercises);
    }

    function removeExerciseFromPlan(exerciseIdToRemove) {
        if (planSaveFeedbackDiv) {
            planSaveFeedbackDiv.style.display = 'none';
            if (feedbackTotalVolumeSpan) feedbackTotalVolumeSpan.textContent = 'N/A';
            if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '';
        }
        const idToRemove = exerciseIdToRemove.toString(); // Ensure comparison with string IDs from dataset
        currentPlanExercises = currentPlanExercises.filter(ex => ex.id.toString() !== idToRemove);
        renderPlan();
        calculatePlanDetails();
    }

    function renderPlan() {
        if (!dropZoneElement) return;
        dropZoneElement.innerHTML = '';

        if (planNameInput) planNameInput.value = currentLoadedPlanName; // Display current plan name

        if (currentPlanExercises.length === 0) {
            const p = document.createElement('p');
            p.textContent = 'Drag and drop exercises here to build your day.';
            dropZoneElement.appendChild(p);
        } else {
            const ul = document.createElement('ul');
            ul.id = 'plan-exercise-list';
            currentPlanExercises.forEach((exercise, index) => {
                const li = document.createElement('li');
                // Display sets and reps, allow modification
                li.innerHTML = `
                    <span>${exercise.name} (${exercise.main_target_muscle_group || exercise.muscleGroup || 'N/A'})</span>
                    <input type="number" class="plan-exercise-sets" data-index="${index}" value="${exercise.sets}" min="1"> sets
                    <input type="text" class="plan-exercise-reps" data-index="${index}" value="${exercise.reps}" placeholder="e.g., 10 or AMRAP"> reps
                    <button class="remove-exercise-btn" data-exercise-id="${exercise.id}">Remove</button>
                `;
                ul.appendChild(li);
            });
            dropZoneElement.appendChild(ul);

            // Add event listeners for set/rep changes and remove buttons
            dropZoneElement.querySelectorAll('.plan-exercise-sets, .plan-exercise-reps').forEach(input => {
                input.addEventListener('change', handleSetRepChange);
            });
            dropZoneElement.querySelectorAll('.remove-exercise-btn').forEach(btn => {
                btn.addEventListener('click', (e) => removeExerciseFromPlan(e.target.dataset.exerciseId));
            });
        }
        updateSaveButtonText();
    }

    function calculatePlanDetails() {
        const volumeByMuscleGroup = {};
        const muscleGroupsHit = new Set();

        currentPlan.forEach(exercise => {
            if (exercise.muscleGroup && exercise.sets) {
                // For Volume: Total sets per muscle group
                // Skip "Full Body" for specific muscle group volume, or handle as needed
                if (exercise.muscleGroup !== 'Full Body') {
                    const sets = parseInt(exercise.sets, 10);
                    if (!isNaN(sets)) {
                        volumeByMuscleGroup[exercise.muscleGroup] = (volumeByMuscleGroup[exercise.muscleGroup] || 0) + sets;
                    }
                }
                // For Frequency: Unique muscle groups hit in this session
                muscleGroupsHit.add(exercise.muscleGroup);
            }
        });

        // Update Volume display
        if (volumeListElement) {
            volumeListElement.innerHTML = ''; // Clear previous list
            if (Object.keys(volumeByMuscleGroup).length === 0) {
                volumeListElement.innerHTML = '<li>No specific muscle group volume calculated.</li>';
            } else {
                for (const group in volumeByMuscleGroup) {
                    const listItem = document.createElement('li');
                    listItem.textContent = `${group}: ${volumeByMuscleGroup[group]} sets`;
                    volumeListElement.appendChild(listItem);
                }
            }
        }

        // Update Frequency display
        if (frequencyListElement) {
            frequencyListElement.innerHTML = ''; // Clear previous list
            if (muscleGroupsHit.size === 0) {
                frequencyListElement.innerHTML = '<li>No muscle groups targeted yet.</li>';
            } else {
                muscleGroupsHit.forEach(group => {
                    const listItem = document.createElement('li');
                    listItem.textContent = group;
                    frequencyListElement.appendChild(listItem);
                });
            }
        }
        console.log("Volume by Muscle Group:", volumeByMuscleGroup);
        console.log("Muscle Groups Hit:", muscleGroupsHit);
    }

    function handleSetRepChange(event) {
        if (planSaveFeedbackDiv) {
            planSaveFeedbackDiv.style.display = 'none';
            if (feedbackTotalVolumeSpan) feedbackTotalVolumeSpan.textContent = 'N/A';
            if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '';
        }
        const index = parseInt(event.target.dataset.index, 10);
        const property = event.target.classList.contains('plan-exercise-sets') ? 'sets' : 'reps';
        let value = event.target.value;
        if (property === 'sets') {
            value = parseInt(value, 10) || 1; // Ensure sets is a positive integer
        }
        currentPlanExercises[index][property] = value;
        calculatePlanDetails(); // Recalculate if sets/reps change affects details
        console.log('Updated exercise:', currentPlanExercises[index]);
    }

    async function savePlan() {
        const userId = getUserId();
        if (!userId) {
            alert('User not logged in. Please login to save plans.');
            return;
        }

        const planName = planNameInput ? planNameInput.value.trim() : currentLoadedPlanName;
        if (!planName) {
            alert('Please enter a name for the plan.');
            if(planNameInput) planNameInput.focus();
            return;
        }

        if (currentPlanExercises.length === 0) {
            alert('Cannot save an empty plan. Add some exercises.');
            return;
        }

        const planData = {
            name: planName,
            // Assuming a single-day plan structure for now for simplicity in UI
            // Backend expects 'days_per_week', 'plan_length_weeks', 'goal_focus' - using defaults or nulls
            days_per_week: 1, // Defaulting to 1 for UI simplicity
            plan_length_weeks: 1, // Defaulting to 1
            goal_focus: 0.5, // Default to balanced
            days: [
                {
                    day_number: 1,
                    name: "Day 1", // Default name for the single day
                    exercises: currentPlanExercises.map((ex, index) => ({
                        exercise_id: ex.id.toString(), // Ensure it's the UUID string
                        order_index: index,
                        sets: parseInt(ex.sets, 10) || 3, // Ensure sets is int
                        // Backend expects rep_range_low/high or similar, not a single 'reps' string for non-int values
                        // This needs careful mapping based on backend table structure for plan_exercises
                        // For now, if reps is a number, use it for both. If not, it might need special handling or UI change.
                        rep_range_low: parseInt(ex.reps, 10) || null,
                        rep_range_high: parseInt(ex.reps, 10) || null,
                        // target_rir, rest_seconds, notes can be added if UI supports
                    }))
                }
            ]
        };

        const method = currentLoadedPlanId ? 'PUT' : 'POST';
        const endpoint = currentLoadedPlanId
            ? `${API_BASE_URL}/v1/plans/${currentLoadedPlanId}`
            : `${API_BASE_URL}/v1/users/${userId}/plans`;

        const originalSaveButtonText = savePlanButton.textContent;
        savePlanButton.disabled = true;
        savePlanButton.innerHTML = `<span class="loader"></span> ${method === 'POST' ? 'Saving...' : 'Updating...'}`;

        try {
            const response = await fetch(endpoint, {
                method: method,
                headers: getAuthHeaders(),
                body: JSON.stringify(planData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to save plan. Unknown error.' }));
                throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`);
            }

            const savedPlan = await response.json();
            // alert(`Plan ${method === 'POST' ? 'saved' : 'updated'} successfully!`);
            console.log('Saved/Updated plan:', savedPlan);

            if (feedbackTotalVolumeSpan) feedbackTotalVolumeSpan.textContent = savedPlan.total_volume || 'N/A';
            if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '';

            if (savedPlan.muscle_group_frequency && typeof savedPlan.muscle_group_frequency === 'object') {
                if (Object.keys(savedPlan.muscle_group_frequency).length > 0) {
                    for (const muscleGroup in savedPlan.muscle_group_frequency) {
                        const listItem = document.createElement('li');
                        listItem.textContent = `${muscleGroup}: ${savedPlan.muscle_group_frequency[muscleGroup]} session(s)`;
                        if (feedbackFrequencyListUl) feedbackFrequencyListUl.appendChild(listItem);
                    }
                } else {
                    if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '<li>No specific muscle group frequency calculated.</li>';
                }
            } else {
                if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '<li>Frequency data not available.</li>';
            }

            if (planSaveFeedbackDiv) planSaveFeedbackDiv.style.display = 'block';
            alert('Plan saved!'); // Or remove if UI feedback is sufficient

            if (method === 'POST' && savedPlan.id) { // If new plan saved
                currentLoadedPlanId = savedPlan.id;
                currentLoadedPlanName = savedPlan.name;
                 if(planNameInput) planNameInput.value = currentLoadedPlanName;
            }
            updateSaveButtonText();
            loadUserPlans(); // Refresh the list of plans
        } catch (error) {
            console.error('Error saving plan:', error);
            alert(`Error saving plan: ${error.message}`);
            if (planSaveFeedbackDiv) planSaveFeedbackDiv.style.display = 'none';
        } finally {
            savePlanButton.disabled = false;
            savePlanButton.textContent = originalSaveButtonText;
            updateSaveButtonText(); // Ensure it reflects 'Update Plan' if a new plan was just saved
        }
    }

    async function loadUserPlans() {
        const userId = getUserId();
        if (!userId) {
            if(userPlansListElement) userPlansListElement.innerHTML = '<li>Login to see your plans.</li>';
            return;
        }

        if (!userPlansListElement) return;

        const originalLoadButtonText = loadPlansButton.textContent;
        loadPlansButton.disabled = true;
        loadPlansButton.innerHTML = '<span class="loader"></span> Loading Plans...';
        userPlansListElement.innerHTML = '<div class="loader-container"><span class="loader"></span> Loading plans...</div>';


        try {
            const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/plans`, {
                headers: getAuthHeaders()
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const plans = await response.json();
            renderUserPlans(plans); // This will clear the loader if successful
        } catch (error) {
            console.error('Error loading plans:', error);
            userPlansListElement.innerHTML = '<li>Failed to load plans. Please try again.</li>';
            // alert(`Error loading plans: ${error.message}`); // Alert might be too intrusive
        } finally {
            loadPlansButton.disabled = false;
            loadPlansButton.textContent = originalLoadButtonText;
        }
    }

    function renderUserPlans(plans) {
        if (!userPlansListElement) return;
        userPlansListElement.innerHTML = ''; // Clear previous

        if (!plans || plans.length === 0) {
            userPlansListElement.innerHTML = '<li>No saved plans found.</li>';
            return;
        }

        plans.forEach(plan => {
            const listItem = document.createElement('li');
            listItem.textContent = plan.name;

            const loadButtonElement = document.createElement('button');
            loadButtonElement.textContent = 'Load';
            loadButtonElement.onclick = (e) => {
                // Prevent multiple clicks while loading
                if (loadButtonElement.disabled) return;
                fetchAndLoadPlanDetails(plan.id, loadButtonElement);
            };
            listItem.appendChild(loadButtonElement);

            const deleteButtonElement = document.createElement('button');
            deleteButtonElement.textContent = 'Delete';
            deleteButtonElement.onclick = (e) => {
                 if (deleteButtonElement.disabled) return;
                deletePlan(plan.id, deleteButtonElement);
            };
            listItem.appendChild(deleteButtonElement);

            userPlansListElement.appendChild(listItem);
        });
    }

    async function fetchAndLoadPlanDetails(planId, buttonElement) {
        const userId = getUserId();
         if (!userId) {
            alert('User context lost. Please login again.');
            return;
        }
        console.log(`Fetching details for plan ID: ${planId}`);

        const originalButtonText = buttonElement ? buttonElement.textContent : '';
        if (buttonElement) {
            buttonElement.disabled = true;
            buttonElement.innerHTML = '<span class="loader"></span>';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/v1/plans/${planId}`, {
                headers: getAuthHeaders()
            });
            if (!response.ok) {
                 const errorData = await response.json().catch(() => ({ message: 'Failed to load plan details. Unknown error.' }));
                throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`);
            }
            const planDetails = await response.json();

            currentLoadedPlanId = planDetails.id;
            currentLoadedPlanName = planDetails.name;
            if(planNameInput) planNameInput.value = currentLoadedPlanName;

            // Assuming single day plan structure for now in the UI
            if (planDetails.days && planDetails.days.length > 0) {
                const firstDayExercises = planDetails.days[0].exercises.map(ex => {
                    // Need to map backend plan_exercise structure to frontend currentPlanExercises structure
                    // The backend's plan_exercise has exercise_id, order_index, sets, rep_range_low, etc.
                    // The frontend's availableExercises has id (UUID), name, type, muscleGroup.
                    const baseExercise = availableExercises.find(availEx => availEx.id === ex.exercise_id);
                    return {
                        id: ex.exercise_id,
                        name: ex.exercise_name || (baseExercise ? baseExercise.name : 'Unknown Exercise'),
                        type: baseExercise ? baseExercise.type : 'N/A', // Or fetch type if not in plan_exercise response
                        muscleGroup: baseExercise ? (baseExercise.main_target_muscle_group || baseExercise.muscleGroup) : 'N/A',
                        sets: ex.sets,
                        reps: ex.rep_range_high || ex.rep_range_low || ex.reps || '', // Prioritize ranges
                        // Potentially more fields if needed by renderPlan/calculatePlanDetails
                    };
                });
                currentPlanExercises = firstDayExercises;
            } else {
                currentPlanExercises = [];
            }
            renderPlan();
            calculatePlanDetails();
            updateSaveButtonText();
            alert(`Plan "${planDetails.name}" loaded.`);

        } catch (error) {
            console.error('Error fetching plan details:', error);
            alert(`Error loading plan details: ${error.message}`);
        } finally {
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.textContent = originalButtonText;
            }
        }
    }

    async function deletePlan(planId, buttonElement) {
        const userId = getUserId();
        if (!userId) {
            alert('User not logged in.');
            return;
        }
        if (!confirm('Are you sure you want to delete this plan?')) {
            return;
        }
        console.log(`Attempting to delete plan ID: ${planId}`);

        const originalButtonText = buttonElement ? buttonElement.textContent : '';
        if (buttonElement) {
            buttonElement.disabled = true;
            buttonElement.innerHTML = '<span class="loader"></span>';
        }

        try {
            const response = await fetch(`${API_BASE_URL}/v1/plans/${planId}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: 'Failed to delete plan. Unknown error.' }));
                throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`);
            }

            if (response.status === 204) { // Standard for successful DELETE with no content
                alert('Plan deleted successfully.');
                if (currentLoadedPlanId === planId) {
                    clearPlan();
                }
                loadUserPlans(); // Refresh list regardless
            } else { // Should not happen with a 204, but as a fallback
                const result = await response.json().catch(()=>null); // Try to parse, but don't fail if no content
                alert(result?.message || 'Plan deleted (status not 204).');
                console.log('Delete response (unexpected):', result);
                loadUserPlans();
            }
        } catch (error) {
            console.error('Error deleting plan:', error);
            alert(`Error deleting plan: ${error.message}`);
        } finally {
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.textContent = originalButtonText;
            }
        }
    }


    function clearPlan() {
        if (planSaveFeedbackDiv) {
            planSaveFeedbackDiv.style.display = 'none';
            if (feedbackTotalVolumeSpan) feedbackTotalVolumeSpan.textContent = 'N/A';
            if (feedbackFrequencyListUl) feedbackFrequencyListUl.innerHTML = '';
        }
        currentPlanExercises = [];
        currentLoadedPlanId = null;
        currentLoadedPlanName = "My New Plan";
        if(planNameInput) planNameInput.value = currentLoadedPlanName;
        renderPlan();
        calculatePlanDetails();
        updateSaveButtonText();
        if (dropZoneElement) {
            dropZoneElement.innerHTML = '<p>Drag and drop exercises here to build your day.</p>';
        }
        console.log('Clearing plan...');
    }

    // --- Event Listeners ---
    if (dropZoneElement) {
        dropZoneElement.addEventListener('dragover', handleDragOver);
        dropZoneElement.addEventListener('dragleave', handleDragLeave);
        dropZoneElement.addEventListener('drop', handleDrop);
    }
    if (savePlanButton) savePlanButton.addEventListener('click', savePlan);
    if (loadPlansButton) loadPlansButton.addEventListener('click', loadUserPlans);
    if (clearPlanButton) clearPlanButton.addEventListener('click', clearPlan);

    // Initial setup
    const exerciseListContainer = document.getElementById('exercise-list-container');
    exerciseListContainer.innerHTML = '<div class="loader-container"><span class="loader"></span> Loading exercises...</div>';
    fetchExercises().then(exercises => {
        availableExercises = exercises;
        if (exercises && exercises.length > 0) {
            displayExercises(exercises);
        } else if (exerciseListContainer.innerHTML.includes('loader-container')) { // Check if loader is still there
             exerciseListContainer.innerHTML = '<p>No exercises found or failed to load.</p>';
        }
    });
    // displayPlanTemplates(); // Removed
    renderPlan(); // To show the initial "Drag and drop" message or current plan
    calculatePlanDetails(); // Calculate details for the initial empty plan
});
