document.addEventListener('DOMContentLoaded', () => {
    const appRoot = document.getElementById('app-root');
    const routes = {
        '#login': LoginPage,
        '#workouts': WorkoutListPage,
        '#logset': LogSetPage,
        '#rir-weight-input': RirWeightInputPage
    };

    function navigate() {
        const path = window.location.hash || '#login';
        const pageFunction = routes[path.split('?')[0]] || NotFoundPage;
        appRoot.innerHTML = '';
        appRoot.appendChild(pageFunction());
    }

    window.addEventListener('hashchange', navigate);
    navigate();

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
    page.querySelector('#login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        console.log('Login submitted');
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
                <button onclick="logWorkoutSet('Workout A', 'a1b2c3d4-e5f6-7890-1234-567890abcdef0')">Log Set</button>
            </li>
            <li>
                <strong>Workout B: Upper Body</strong> - Last done: 2024-07-26
                <button onclick="logWorkoutSet('Workout B', 'b1c2d3e4-f5g6-7890-1234-567890abcdef1')">Log Set</button>
            </li>
        </ul>
        <button onclick="window.location.hash='#new-workout'">Create New Workout</button>
    `;
    return page;
}

function LogSetPage() {
    const page = document.createElement('div');
    page.className = 'page active';

    const params = new URLSearchParams(window.location.hash.split('?')[1]);
    const exerciseName = params.get('exerciseName') || 'Selected Exercise';
    // For a real app, exerciseId would be reliably passed, e.g. from the workout list.
    // Using a hardcoded one for now if not in params, or a specific one for testing.
    const exerciseIdFromParam = params.get('exerciseId');
    const exerciseId = exerciseIdFromParam || 'a1b2c3d4-e5f6-7890-1234-567890abcdef0'; // Default test UUID for "Barbell Bench Press" or similar.
    const userId = '123e4567-e89b-12d3-a456-426614174000'; // Hardcoded test User UUID

    page.innerHTML = `
        <h2>Log Set for ${exerciseName}</h2>

        <div id="ai-recommendation" style="border: 1px solid #eee; padding: 10px; margin-bottom: 15px; background-color: #f9f9f9;">
            <h4>AI Recommendation:</h4>
            <p>
                Weight: <strong id="rec-weight" style="font-size: 1.1em;">Loading...</strong> kg
                <span id="rec-tooltip-trigger" title="Loading explanation..." style="cursor: help; border-bottom: 1px dotted #000;">&#9432;</span>
            </p>
            <p>Reps: <strong id="rec-reps" style="font-size: 1.1em;">Loading...</strong></p>
            <p>RIR: <strong id="rec-rir" style="font-size: 1.1em;">Loading...</strong></p>
            <small id="rec-error" style="color: red;"></small>
        </div>

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

    const recWeightEl = page.querySelector('#rec-weight');
    const recRepsEl = page.querySelector('#rec-reps');
    const recRirEl = page.querySelector('#rec-rir');
    const tooltipTriggerEl = page.querySelector('#rec-tooltip-trigger');
    const recErrorEl = page.querySelector('#rec-error');
    const aiRecommendationDiv = page.querySelector('#ai-recommendation');

    // Fetch AI Recommendation
    // Ensure engine/app.py is running and accessible at http://localhost:5000 (or configured host)
    const apiUrl = \`/v1/user/\${userId}/exercise/\${exerciseId}/recommend-set-parameters\`;
    console.log(\`Fetching recommendation from: \${apiUrl}\`);

    fetch(apiUrl)
      .then(response => {
        if (!response.ok) {
          // Try to parse error JSON if available, otherwise use statusText
          return response.json().then(errData => {
            throw new Error(errData.error || \`HTTP error! Status: \${response.status}\`);
          }).catch(() => { // Fallback if error response is not JSON
            throw new Error(\`HTTP error! Status: \${response.status} \${response.statusText}\`);
          });
        }
        return response.json();
      })
      .then(data => {
        if (data.recommended_weight_kg !== undefined) {
          recWeightEl.textContent = data.recommended_weight_kg;
          recRepsEl.textContent = \`\${data.target_reps_low} - \${data.target_reps_high}\`;
          recRirEl.textContent = data.target_rir;
          tooltipTriggerEl.title = data.explanation; // Set title attribute for browser tooltip
          recErrorEl.textContent = ''; // Clear previous errors

          // Populate form fields with recommended values as placeholders/starting points
          page.querySelector('#weight').value = data.recommended_weight_kg;
          page.querySelector('#reps').value = data.target_reps_high; // Default to high end of rep range
          page.querySelector('#rir').value = data.target_rir;

        } else {
          const errorMsg = data.error || 'Could not parse AI recommendation data.';
          console.error('Error in recommendation data:', data);
          recErrorEl.textContent = errorMsg;
          recWeightEl.textContent = 'N/A';
          recRepsEl.textContent = 'N/A';
          recRirEl.textContent = 'N/A';
        }
      })
      .catch(error => {
        console.error('Error fetching AI recommendation:', error);
        recErrorEl.textContent = \`Error: \${error.message}\`;
        recWeightEl.textContent = 'N/A';
        recRepsEl.textContent = 'N/A';
        recRirEl.textContent = 'N/A';
        tooltipTriggerEl.title = 'Could not load explanation.';
      });

    page.querySelector('#log-set-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const weight = e.target.weight.value;
        const reps = e.target.reps.value;
        const rir = e.target.rir.value;
        console.log(\`Set Logged for \${exerciseName} (ID: \${exerciseId}): Weight: \${weight}, Reps: \${reps}, RIR: \${rir}\`);
        alert('Set logged!');
        window.location.hash = '#workouts';
    });
    return page;
}

function NotFoundPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = '<h2>404 - Page Not Found</h2>';
    return page;
}

function logWorkoutSet(workoutName, exerciseId) { // Modified to accept exerciseId
    // For now, just navigate to a generic log set page
    // In a real app, you'd pass exercise IDs or details
    window.location.hash = \`#logset?exerciseName=\${encodeURIComponent(workoutName + ' - Main Lift')}&exerciseId=\${exerciseId}\`;
}


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
        const barWeight = 20;
        const smallestIncrement = 2.5;

        let weightOnBar = targetWeight - barWeight;
        if (weightOnBar < 0) weightOnBar = 0;

        let roundedWeightOnBar = Math.round(weightOnBar / smallestIncrement) * smallestIncrement;
        let finalRoundedWeight = barWeight + roundedWeightOnBar;

        if (targetWeight < barWeight && targetWeight > 0) {
             if (targetWeight < barWeight + smallestIncrement && targetWeight > barWeight/2) {
                finalRoundedWeight = barWeight;
                roundedWeightOnBar = 0;
             } else if (targetWeight <= barWeight/2) {
                finalRoundedWeight = 0;
                roundedWeightOnBar = -barWeight;
             }
        }
        roundedWeightInput.value = finalRoundedWeight.toFixed(2);

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
            breakdown = \`Use barbell (20kg). Cannot make \${finalRoundedWeight.toFixed(2)}kg with available plates.\`;
        }
        else {
            for (const plate of platesAvailable) {
                if (remainingWeightPerSide >= plate) {
                    const numPlates = Math.floor(remainingWeightPerSide / plate);
                    breakdown += \`\${numPlates}x\${plate}kg, \`;
                    remainingWeightPerSide -= numPlates * plate;
                }
            }
            if (remainingWeightPerSide > 0.01) {
                breakdown += \` (+\${remainingWeightPerSide.toFixed(2)}kg not loadable per side)\`;
            }
            if (breakdown === 'Plates per side: ') { // Should not happen if logic is correct for roundedWeightOnBar > 0
                 breakdown = "Use barbell only (20kg).";
            } else {
                breakdown = breakdown.slice(0, -2);
            }
        }
        plateBreakdownP.textContent = breakdown;
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const exercise = e.target['exercise-name'].value;
        const targetReps = e.target['target-reps'].value;
        const targetRir = e.target['target-rir'].value;
        const finalWeight = roundedWeightInput.value || calculatedWeightInput.value;

        console.log(\`Using Weight for \${exercise}: \${finalWeight}kg, Target Reps: \${targetReps}, Target RIR: \${targetRir}\`);
        alert(\`Selected: \${finalWeight}kg for \${exercise}.\`);
    });
    return page;
}
```
