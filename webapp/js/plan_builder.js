// Plan Builder specific JavaScript

document.addEventListener('DOMContentLoaded', () => {
    console.log('Plan Builder script loaded');

    // Mock list of exercises
    const mockExercises = [
        { id: 1, name: 'Push-ups', type: 'Strength', muscleGroup: 'Chest' },
        { id: 2, name: 'Squats', type: 'Strength', muscleGroup: 'Legs' },
        { id: 3, name: 'Jumping Jacks', type: 'Cardio', muscleGroup: 'Full Body' }, // Could contribute to overall activity but not specific muscle volume
        { id: 4, name: 'Plank', type: 'Core', muscleGroup: 'Core' }, // Standardized to 'Core'
        { id: 5, name: 'Bicep Curls', type: 'Strength', muscleGroup: 'Arms' }, // Could be 'Biceps' or 'Arms'
        { id: 6, name: 'Lunges', type: 'Strength', muscleGroup: 'Legs' },
        { id: 7, name: 'Bent Over Rows', type: 'Strength', muscleGroup: 'Back' },
        { id: 8, name: 'Overhead Press', type: 'Strength', muscleGroup: 'Shoulders' },
        { id: 9, name: 'Tricep Dips', type: 'Strength', muscleGroup: 'Arms' }, // Could be 'Triceps' or 'Arms'
    ];

    const exerciseListElement = document.getElementById('exercise-list');
    const dropZoneElement = document.getElementById('drop-zone');
    // const planVolumeElement = document.getElementById('plan-volume'); // Replaced by volume-list
    // const planFrequencyElement = document.getElementById('plan-frequency'); // Replaced by frequency-list
    const volumeListElement = document.getElementById('volume-list');
    const frequencyListElement = document.getElementById('frequency-list');
    const savePlanButton = document.getElementById('save-plan');
    const loadPlanButton = document.getElementById('load-plan');
    const clearPlanButton = document.getElementById('clear-plan');
    const planTemplatesListElement = document.getElementById('plan-templates-list');

    let currentPlan = []; // Will now store exercises with potential sets/reps

    // --- Predefined Plan Templates ---
    const planTemplates = [
        {
            id: "template-fb-strength",
            name: "Full Body Strength",
            exercises: [
                { id: 2, name: 'Squats', type: 'Strength', muscleGroup: 'Legs', sets: 3, reps: 5 },
                { id: 'template-bench', name: 'Bench Press', type: 'Strength', muscleGroup: 'Chest', sets: 3, reps: 5 },
                { id: 4, name: 'Plank', type: 'Core', muscleGroup: 'Core', sets: 3, reps: '60s' } // Standardized to 'Core'
            ]
        },
        {
            id: "template-push-day",
            name: "Push Day",
            exercises: [
                { id: 1, name: 'Push-ups', type: 'Strength', muscleGroup: 'Chest', sets: 3, reps: 15 },
                { id: 8, name: 'Overhead Press', type: 'Strength', muscleGroup: 'Shoulders', sets: 3, reps: 8 },
                { id: 9, name: 'Tricep Dips', type: 'Strength', muscleGroup: 'Arms', sets: 3, reps: 12 } // Assuming Tricep Dips use general 'Arms'
            ]
        },
        {
            id: "template-pull-day",
            name: "Pull Day",
            exercises: [
                { id: 7, name: 'Bent Over Rows', type: 'Strength', muscleGroup: 'Back', sets: 4, reps: 8 },
                { id: 5, name: 'Bicep Curls', type: 'Strength', muscleGroup: 'Arms', sets: 3, reps: 10 },
                { id: 'template-pullups', name: 'Pull-ups', type: 'Strength', muscleGroup: 'Back', sets: 3, reps: 'AMRAP' } // As Many Reps As Possible
            ]
        }
    ];

    // Function to display exercises from mockExercises
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

        const exerciseFromMock = mockExercises.find(ex => ex.id.toString() === exerciseId);
        if (exerciseFromMock) {
            // Add default sets/reps when adding from mock list
            const exerciseToAdd = {
                ...exerciseFromMock,
                sets: 3, // Default sets
                reps: 10 // Default reps
            };
            addExerciseToPlan(exerciseToAdd);
        }
    }

    // --- Plan Management Functions ---
    function addExerciseToPlan(exercise) { // exercise object now may include sets/reps
        currentPlan.push(exercise);
        renderPlan();
        calculatePlanDetails();
        console.log('Current plan:', currentPlan);
    }

    function removeExerciseFromPlan(exerciseIdToRemove) { // exerciseId can be number or string from template
        // Ensure exerciseIdToRemove is treated as a number if IDs are numbers
        const idToRemove = parseInt(exerciseIdToRemove, 10);
        currentPlan = currentPlan.filter(ex => ex.id !== idToRemove);
        renderPlan();
        calculatePlanDetails();
    }

    function renderPlan() {
        if (!dropZoneElement) return;
        dropZoneElement.innerHTML = ''; // Clear previous content

        if (currentPlan.length === 0) {
            const p = document.createElement('p');
            p.textContent = 'Drag and drop exercises here';
            dropZoneElement.appendChild(p);
            return;
        }

        const ul = document.createElement('ul');
        ul.id = 'plan-exercise-list'; // Add ID for specific styling
        currentPlan.forEach(exercise => { // exercise object might have sets/reps
            const li = document.createElement('li');
            let exerciseText = `${exercise.name} (${exercise.type})`;
            if (exercise.sets !== undefined && exercise.reps !== undefined) {
                exerciseText += ` - ${exercise.sets} sets x ${exercise.reps} reps`;
            }
            li.textContent = exerciseText;
            li.setAttribute('data-plan-item-id', exercise.id); // Use original ID for removal

            // Add a remove button for each exercise in the plan
            const removeBtn = document.createElement('button');
            removeBtn.textContent = 'Remove';
            removeBtn.classList.add('remove-exercise-btn'); // Add class for styling
            removeBtn.onclick = () => removeExerciseFromPlan(exercise.id);

            li.appendChild(removeBtn);
            ul.appendChild(li);
        });
        dropZoneElement.appendChild(ul);
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

    function savePlan() {
        // Placeholder for saving plan (e.g., to localStorage or backend)
        localStorage.setItem('userPlan', JSON.stringify(currentPlan));
        alert('Plan saved!');
        console.log('Saving plan:', currentPlan);
    }

    function loadPlan() {
        // Placeholder for loading plan
        const savedPlan = localStorage.getItem('userPlan');
        if (savedPlan) {
            currentPlan = JSON.parse(savedPlan);
            renderPlan();
            calculatePlanDetails();
            alert('Plan loaded!');
        } else {
            alert('No saved plan found.');
        }
        console.log('Loading plan...');
    }

    function clearPlan() {
        currentPlan = [];
        renderPlan();
        calculatePlanDetails();
        if (dropZoneElement) {
            dropZoneElement.innerHTML = '<p>Drag and drop exercises here</p>';
        }
        console.log('Clearing plan...');
    }

    // --- Template Functions ---
    function displayPlanTemplates() {
        if (!planTemplatesListElement) return;
        planTemplatesListElement.innerHTML = ''; // Clear existing templates

        planTemplates.forEach(template => {
            const listItem = document.createElement('li');
            listItem.textContent = template.name;

            const loadButton = document.createElement('button');
            loadButton.textContent = 'Load';
            loadButton.setAttribute('data-template-id', template.id);
            loadButton.classList.add('load-template-btn'); // For styling
            loadButton.addEventListener('click', (event) => {
                loadPlanTemplate(event.target.getAttribute('data-template-id'));
            });

            listItem.appendChild(loadButton);
            planTemplatesListElement.appendChild(listItem);
        });
    }

    function loadPlanTemplate(templateId) {
        const template = planTemplates.find(t => t.id === templateId);
        if (!template) {
            console.error('Template not found:', templateId);
            return;
        }
        // Create a deep copy of exercises to avoid modifying the template
        currentPlan = JSON.parse(JSON.stringify(template.exercises));
        renderPlan();
        calculatePlanDetails();
        alert(`Plan "${template.name}" loaded!`);
        console.log('Loaded plan from template:', currentPlan);
    }

    // --- Event Listeners ---
    if (dropZoneElement) {
        dropZoneElement.addEventListener('dragover', handleDragOver);
        dropZoneElement.addEventListener('dragleave', handleDragLeave);
        dropZoneElement.addEventListener('drop', handleDrop);
    }
    if (savePlanButton) savePlanButton.addEventListener('click', savePlan);
    if (loadPlanButton) loadPlanButton.addEventListener('click', loadPlan);
    if (clearPlanButton) clearPlanButton.addEventListener('click', clearPlan);

    // Initial setup
    displayExercises(mockExercises);
    displayPlanTemplates(); // Display templates on load
    renderPlan(); // To show the initial "Drag and drop" message
    calculatePlanDetails();
});
