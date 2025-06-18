document.addEventListener('DOMContentLoaded', () => {
    // --- Constants and Initial Setup ---
    const METRIC_PLATES = [25, 20, 15, 10, 5, 2.5, 1.25];
    const IMPERIAL_PLATES = [45, 35, 25, 10, 5, 2.5]; // Assuming common imperial plates

    const equipmentForm = document.getElementById('equipment-form');
    const plateSelectionDiv = document.getElementById('plate-selection');
    const dumbbellTypeSelect = document.getElementById('dumbbell-type');
    const fixedDumbbellsSection = document.getElementById('fixed-dumbbells-section');
    const adjustableDumbbellsSection = document.getElementById('adjustable-dumbbells-section');
    const barbellWeightInput = document.getElementById('barbell-weight-kg');
    const fixedDumbbellWeightsInput = document.getElementById('fixed-dumbbell-weights');
    const adjustableDumbbellMaxWeightInput = document.getElementById('adjustable-dumbbell-max-weight');
    const equipmentMessageDiv = document.getElementById('equipment-message');

    // Assumed to be globally available from app.js
    // const currentUserId = /* ... */;
    // const API_BASE_URL = /* ... */;
    // const getAuthHeaders = /* ... */;

    let currentUserProfileData = null; // To store fetched profile data for PATCH updates

    // --- Dynamic Plate Options Rendering ---
    function renderPlateOptions(plates, selectedPlates = []) {
        if (!plateSelectionDiv) {
            console.error('plateSelectionDiv not found');
            return;
        }
        plateSelectionDiv.innerHTML = ''; // Clear existing options
        plates.forEach(p => {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.name = 'plate';
            checkbox.value = p;
            if (selectedPlates.includes(p)) {
                checkbox.checked = true;
            }
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(` ${p}`));
            plateSelectionDiv.appendChild(label);
            plateSelectionDiv.appendChild(document.createElement('br')); // For better spacing
        });
    }

    // --- Dumbbell Type Visibility Toggle ---
    if (dumbbellTypeSelect) {
        dumbbellTypeSelect.addEventListener('change', () => {
            const type = dumbbellTypeSelect.value;
            if (fixedDumbbellsSection) fixedDumbbellsSection.style.display = type === 'fixed' ? 'block' : 'none';
            if (adjustableDumbbellsSection) adjustableDumbbellsSection.style.display = type === 'adjustable' ? 'block' : 'none';
        });
    } else {
        console.error('dumbbellTypeSelect not found');
    }

    // --- Fetch User Profile and Populate Form ---
    async function loadUserProfile() {
        if (!currentUserId) {
            displayMessage('User ID not found. Please log in.', true);
            return;
        }
        if (!API_BASE_URL || !getAuthHeaders) {
            displayMessage('API configuration missing.', true);
            console.error('API_BASE_URL or getAuthHeaders is not defined');
            return;
        }

        displayMessage('Loading profile...', false);

        try {
            const response = await fetch(`${API_BASE_URL}/v1/users/${currentUserId}/profile`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            const data = await response.json();

            if (response.ok) {
                currentUserProfileData = data; // Store for potential PATCH later
                const profileData = data; // Use 'data' directly for this function scope
                const unitSystem = profileData.unit_system || 'metric'; // Default to metric

                let platesToRender = METRIC_PLATES;
                let selectedPlatesKey = 'plates_kg';
                if (unitSystem === 'imperial') {
                    platesToRender = IMPERIAL_PLATES;
                    selectedPlatesKey = 'plates_lbs';
                }

                const availablePlatesData = profileData.available_plates || {};

                renderPlateOptions(platesToRender, availablePlatesData[selectedPlatesKey] || []);

                if (barbellWeightInput) {
                    barbellWeightInput.value = availablePlatesData.barbell_weight_kg || 20;
                }

                if (dumbbellTypeSelect) {
                    const dumbbellData = availablePlatesData.dumbbells || {};
                    dumbbellTypeSelect.value = dumbbellData.type || 'none';
                    // Trigger change to update visibility
                    dumbbellTypeSelect.dispatchEvent(new Event('change'));

                    if (fixedDumbbellWeightsInput && dumbbellData.type === 'fixed') {
                        fixedDumbbellWeightsInput.value = (dumbbellData.available_weights_kg || []).join(', ');
                    }
                    if (adjustableDumbbellMaxWeightInput && dumbbellData.type === 'adjustable') {
                        adjustableDumbbellMaxWeightInput.value = dumbbellData.max_weight_kg || '';
                    }
                }
                displayMessage('Profile loaded.', false, true); // Clear after a delay
            } else {
                displayMessage(data.error || 'Failed to load profile.', true);
            }
        } catch (error) {
            console.error('Error loading profile:', error);
            displayMessage('Error loading profile. Check console for details.', true);
        }
    }

    // --- Handle Form Submission (Save Equipment) ---
    if (equipmentForm) {
        equipmentForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (!currentUserId) {
                displayMessage('User ID not found. Cannot save.', true);
                return;
            }

            displayMessage('Saving equipment...', false);

            const selectedPlateElements = plateSelectionDiv.querySelectorAll('input[name="plate"]:checked');
            const selectedPlates = Array.from(selectedPlateElements).map(el => parseFloat(el.value));

            // For now, assume metric is used for saving. Unit system handling can be expanded.
            const availablePlates = {
                plate_units: 'kg', // Or determine from a user setting if available
                plates_kg: selectedPlates,
                barbell_weight_kg: parseFloat(barbellWeightInput.value) || 20,
                dumbbells: {
                    type: dumbbellTypeSelect.value,
                }
            };

            if (dumbbellTypeSelect.value === 'fixed') {
                availablePlates.dumbbells.available_weights_kg = fixedDumbbellWeightsInput.value
                    .split(',')
                    .map(s => s.trim())
                    .filter(s => s)
                    .map(s => parseFloat(s));
            } else if (dumbbellTypeSelect.value === 'adjustable') {
                availablePlates.dumbbells.max_weight_kg = parseFloat(adjustableDumbbellMaxWeightInput.value) || null;
            }

            // Constructing the update payload.
            // Option 1: Send only the 'available_plates' field (assuming backend handles partial PATCH or this specific structure)
            const profileUpdateData = { available_plates: availablePlates };

            // Option 2: Send the whole profile object back with 'available_plates' modified (safer for strict PUT/PATCH)
            // This requires `currentUserProfileData` to be populated from `loadUserProfile`.
            // let fullProfileUpdate = { ...currentUserProfileData, available_plates: availablePlates };
            // delete fullProfileUpdate.id; // Remove fields that shouldn't be sent back, like user_id or email if not allowed
            // delete fullProfileUpdate.email;
            // delete fullProfileUpdate.created_at;
            // delete fullProfileUpdate.updated_at;
            // const profileUpdateData = fullProfileUpdate;


            try {
                const response = await fetch(`${API_BASE_URL}/v1/users/${currentUserId}/profile`, {
                    method: 'PUT', // Or PATCH, depending on API design for partial updates
                    headers: getAuthHeaders(),
                    body: JSON.stringify(profileUpdateData)
                });

                const data = await response.json();

                if (response.ok) {
                    displayMessage('Equipment saved successfully!', false, true);
                    currentUserProfileData = data; // Update local cache of profile
                } else {
                    displayMessage(data.error || 'Failed to save equipment.', true);
                }
            } catch (error) {
                console.error('Error saving equipment:', error);
                displayMessage('Error saving equipment. Check console for details.', true);
            }
        });
    } else {
        console.error('equipmentForm not found');
    }

    // --- Helper to display messages ---
    function displayMessage(message, isError = false, autoClear = false) {
        if (!equipmentMessageDiv) return;
        equipmentMessageDiv.textContent = message;
        equipmentMessageDiv.style.color = isError ? 'red' : 'green';
        equipmentMessageDiv.style.display = 'block';

        if (autoClear) {
            setTimeout(() => {
                equipmentMessageDiv.style.display = 'none';
                equipmentMessageDiv.textContent = '';
            }, 3000);
        }
    }

    // --- Initial Load ---
    // Make sure currentUserId is available before loading.
    // This might require waiting for app.js to fully initialize currentUserId.
    // For simplicity, we assume it's available or will be shortly.
    // A more robust solution might use a custom event or a check loop.
    if (typeof currentUserId !== 'undefined' && currentUserId !== null) {
        loadUserProfile();
    } else {
        // Attempt to load after a short delay, in case app.js is still initializing
        setTimeout(() => {
            if (typeof currentUserId !== 'undefined' && currentUserId !== null) {
                loadUserProfile();
            } else {
                console.warn('currentUserId not available after delay. Profile will not be loaded automatically.');
                // displayMessage('Could not load user profile: User not identified.', true);
                // Optionally, hide the form or parts of it if user ID is essential
                 if (plateSelectionDiv) plateSelectionDiv.innerHTML = '<p>Please log in to manage your equipment.</p>';
            }
        }, 500);
    }
});
