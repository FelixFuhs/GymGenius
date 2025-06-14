document.addEventListener('DOMContentLoaded', () => {
    const appRoot = document.getElementById('app-root');
    const routes = {
        '#login': LoginPage,
        '#workouts': WorkoutListPage,
        '#logset': LogSetPage, // Example: /#logset?exerciseId=1
        '#rir-weight-input': RirWeightInputPage // New page
    };

    function navigate() {
        const path = window.location.hash || '#login';
        const pageFunction = routes[path.split('?')[0]] || NotFoundPage;
        appRoot.innerHTML = ''; // Clear previous content
        appRoot.appendChild(pageFunction());
    }

    window.addEventListener('hashchange', navigate);
    navigate(); // Initial navigation

    // Register service worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => console.log('Service Worker registered successfully:', registration))
            .catch(error => console.log('Service Worker registration failed:', error));
    }
});

function LoginPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = `
        <h2>Login</h2>
        <form id="login-form">
            <div>
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            <div>
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <p>Don't have an account? <a href="#signup">Sign Up</a></p>
    `;
    // Add event listeners for form submission, etc.
    page.querySelector('#login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        console.log('Login submitted');
        // Mock login:
        window.location.hash = '#workouts';
    });
    return page;
}

function WorkoutListPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.id = 'workout-list';
    page.innerHTML = `
        <h2>My Workouts</h2>
        <ul>
            <li>
                <strong>Workout A: Full Body</strong> - Last done: 2024-07-28
                <button onclick="logWorkoutSet('Workout A')">Log Set</button>
            </li>
            <li>
                <strong>Workout B: Upper Body</strong> - Last done: 2024-07-26
                <button onclick="logWorkoutSet('Workout B')">Log Set</button>
            </li>
            <!-- More workouts -->
        </ul>
        <button onclick="window.location.hash='#new-workout'">Create New Workout</button>
    `;
    return page;
}

function LogSetPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    // Basic example, in reality, you'd fetch exercise details based on params
    const params = new URLSearchParams(window.location.hash.split('?')[1]);
    const exerciseName = params.get('exerciseName') || 'Selected Exercise';

    page.innerHTML = `
        <h2>Log Set for ${exerciseName}</h2>
        <form id="log-set-form">
            <div>
                <label for="weight">Weight (kg):</label>
                <input type="number" id="weight" name="weight" step="0.5" required>
            </div>
            <div>
                <label for="reps">Reps:</label>
                <input type="number" id="reps" name="reps" required>
            </div>
            <div>
                <label for="rir">RIR (Reps In Reserve):</label>
                <input type="number" id="rir" name="rir" min="0" max="5">
            </div>
            <button type="submit">Log Set</button>
        </form>
        <button onclick="window.location.hash='#workouts'">Back to Workouts</button>
    `;
     page.querySelector('#log-set-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const weight = e.target.weight.value;
        const reps = e.target.reps.value;
        const rir = e.target.rir.value;
        console.log(\`Set Logged for ${exerciseName}: Weight: \${weight}, Reps: \${reps}, RIR: \${rir}\`);
        // Here you would typically send this data to a backend
        alert('Set logged!');
        window.location.hash = '#workouts'; // Navigate back
    });
    return page;
}

function NotFoundPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = '<h2>404 - Page Not Found</h2>';
    return page;
}

// Dummy functions for buttons in workout list for now
function logWorkoutSet(workoutName) {
    // For now, just navigate to a generic log set page
    // In a real app, you'd pass exercise IDs or details
    window.location.hash = \`#logset?exerciseName=\${encodeURIComponent(workoutName + ' - Main Lift')}\`;
}

// Placeholder for images directory and icons (referenced in manifest.json)
// Create webapp/images directory
// Add dummy icon-192x192.png and icon-512x512.png if possible, or just create empty files.
// If creating actual image files is not possible, the manifest references might cause console errors
// but the PWA structure will be in place.

function RirWeightInputPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.id = 'rir-weight-input-page';
    page.innerHTML = `
        <h2>RIR & Weight Input (w/ Plate Rounding)</h2>
        <form id="rir-weight-form">
            <div>
                <label for="exercise-name">Exercise:</label>
                <input type="text" id="exercise-name" name="exercise-name" value="Squat" required>
            </div>
            <div>
                <label for="target-reps">Target Reps:</label>
                <input type="number" id="target-reps" name="target-reps" value="5" required>
            </div>
            <div>
                <label for="target-rir">Target RIR (Reps In Reserve):</label>
                <input type="number" id="target-rir" name="target-rir" min="0" max="5" value="2" required>
            </div>
            <div>
                <label for="calculated-weight">Calculated Target Weight (kg):</label>
                <input type="number" id="calculated-weight" name="calculated-weight" step="0.1" value="100" required>
                <button type="button" id="round-weight-btn">Round to Nearest Plate</button>
            </div>
            <div>
                <label for="rounded-weight">Rounded Weight (kg):</label>
                <input type="text" id="rounded-weight" name="rounded-weight" readonly>
            </div>
            <p id="plate-breakdown"></p>
            <button type="submit">Use This Weight</button>
        </form>
        <button onclick="window.location.hash='#workouts'">Back to Workouts</button>
    `;

    const form = page.querySelector('#rir-weight-form');
    const calculatedWeightInput = form.querySelector('#calculated-weight');
    const roundedWeightInput = form.querySelector('#rounded-weight');
    const roundButton = form.querySelector('#round-weight-btn');
    const plateBreakdownP = form.querySelector('#plate-breakdown');

    roundButton.addEventListener('click', () => {
        const targetWeight = parseFloat(calculatedWeightInput.value);
        if (isNaN(targetWeight) || targetWeight <= 0) {
            roundedWeightInput.value = 'Invalid input';
            plateBreakdownP.textContent = '';
            return;
        }
        // Simple rounding to nearest 2.5kg for example
        // Assumes a 20kg barbell. Smallest plate increment 2.5kg (1.25kg per side)
        const barWeight = 20;
        const smallestIncrement = 2.5; // Total smallest increment (e.g. two 1.25kg plates)

        let weightOnBar = targetWeight - barWeight;
        if (weightOnBar < 0) weightOnBar = 0; // Cannot have less than bar weight

        let roundedWeightOnBar = Math.round(weightOnBar / smallestIncrement) * smallestIncrement;
        let finalRoundedWeight = barWeight + roundedWeightOnBar;

        // Ensure final weight is not less than bar weight if target is very low
        if (targetWeight < barWeight && targetWeight > 0) {
             // If target is less than bar, but positive, what should it round to?
             // Option 1: Round to bar weight if below bar + smallest increment
             // Option 2: Or allow rounding to just bar if target is low enough
             // For now, if target is < bar, but > 0, round to bar + smallest possible addition or just bar
             if (targetWeight < barWeight + smallestIncrement && targetWeight > barWeight/2) { // Heuristic
                finalRoundedWeight = barWeight;
                roundedWeightOnBar = 0;
             } else if (targetWeight <= barWeight/2) { // Arbitrary threshold for "too light"
                finalRoundedWeight = 0; // Or some minimum practical weight
                roundedWeightOnBar = -barWeight; // To show no plates
             }
        }


        roundedWeightInput.value = finalRoundedWeight.toFixed(2);

        // Basic plate breakdown (example for KG plates)
        // Plates: 25, 20, 15, 10, 5, 2.5, 1.25 (per side)
        const platesAvailable = [25, 20, 15, 10, 5, 2.5, 1.25];
        let weightPerSide = roundedWeightOnBar / 2;
        let breakdown = 'Plates per side: ';
        let remainingWeightPerSide = weightPerSide;

        if (finalRoundedWeight === 0) {
            breakdown = "No weight/bar selected.";
        } else if (roundedWeightOnBar < 0) {
             breakdown = "Target weight too low for standard bar.";
        } else if (finalRoundedWeight === barWeight) {
            breakdown = "Use barbell only (20kg).";
        } else if (roundedWeightOnBar < smallestIncrement && roundedWeightOnBar > 0) {
            breakdown = `Use barbell (20kg). Cannot make ${finalRoundedWeight.toFixed(2)}kg with available plates.`;
        }
        else {
            for (const plate of platesAvailable) {
                if (remainingWeightPerSide >= plate) {
                    const numPlates = Math.floor(remainingWeightPerSide / plate);
                    breakdown += `${numPlates}x${plate}kg, `;
                    remainingWeightPerSide -= numPlates * plate;
                }
            }
            if (remainingWeightPerSide > 0.01) { // Check for small remainder due to precision
                breakdown += ` (+${remainingWeightPerSide.toFixed(2)}kg not loadable per side)`;
            }
            if (breakdown === 'Plates per side: ') {
                 breakdown = "Use barbell only (20kg).";
            } else {
                breakdown = breakdown.slice(0, -2); // Remove trailing comma and space
            }
        }
        plateBreakdownP.textContent = breakdown;

    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const exercise = e.target['exercise-name'].value;
        const targetReps = e.target['target-reps'].value;
        const targetRir = e.target['target-rir'].value;
        const finalWeight = roundedWeightInput.value || calculatedWeightInput.value; // Use rounded if available

        console.log(`Using Weight for ${exercise}: ${finalWeight}kg, Target Reps: ${targetReps}, Target RIR: ${targetRir}`);
        alert(`Selected: ${finalWeight}kg for ${exercise}.`);
        // Potentially navigate or use this data
        // window.location.hash = '#logset?exerciseName=...&weight=...';
    });

    return page;
}

// Make sure the initial navigation considers the new route if someone directly lands on it
// (though current setup defaults to #login, which is fine)

// Add a link to this new page in the footer nav for testing, if desired
// (This part is optional for the task, but good for testing)
// Modify the `index.html` or the footer in `app.js` if you want a direct link.
// For now, can be accessed by manually changing hash to #rir-weight-input
