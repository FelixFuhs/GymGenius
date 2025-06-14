// API Base URL - Assuming backend is served from the same origin
const API_BASE_URL = ''; // e.g., 'http://localhost:5000' if different

// Global state (simplified for P1)
let currentUserId = null;
let currentWorkoutId = null;

// --- JWT Helper Functions ---
function storeToken(token) {
    localStorage.setItem('jwtToken', token);
}

function getToken() {
    return localStorage.getItem('jwtToken');
}

function removeToken() {
    localStorage.removeItem('jwtToken');
    currentUserId = null; // Clear global userId on logout
    currentWorkoutId = null; // Clear global workoutId on logout
}

function getAuthHeaders() {
    const token = getToken();
    if (token) {
        return {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json' // Common for POST/PUT
        };
    }
    return { 'Content-Type': 'application/json' }; // Default content type
}

// Basic JWT decoding (use a library for production)
function decodeJWT(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        console.error("Error decoding JWT:", e);
        return null;
    }
}

// --- Navigation ---
const protectedRoutes = ['#workouts', '#logset', '#exercises', '#profile']; // Add other protected routes

document.addEventListener('DOMContentLoaded', () => {
    const appRoot = document.getElementById('app-root');
    const routes = {
        '#login': LoginPage,
        '#signup': SignupPage, // Added SignupPage
        '#workouts': WorkoutListPage,
        '#logset': LogSetPage,
        '#exercises': ExerciseListPage, // Added ExerciseListPage
        '#rir-weight-input': RirWeightInputPage,
        // '#profile': ProfilePage, // Example for later
    };

    function navigate() {
        let path = window.location.hash || '#login';
        const pathRoot = path.split('?')[0];

        if (protectedRoutes.includes(pathRoot) && !getToken()) {
            console.log(`Access to protected route ${pathRoot} denied. Redirecting to #login.`);
            window.location.hash = '#login'; // Redirect to login if trying to access protected route without token
            path = '#login'; // Update path to ensure login page is rendered
        }

        // If already logged in and trying to access #login or #signup, redirect to a default authenticated page (e.g., #workouts)
        if ((pathRoot === '#login' || pathRoot === '#signup') && getToken()) {
            console.log(`Already logged in. Redirecting from ${pathRoot} to #workouts.`);
            window.location.hash = '#workouts';
            path = '#workouts';
        }

        const pageFunction = routes[path.split('?')[0]] || NotFoundPage; // Use updated path
        appRoot.innerHTML = ''; // Clear previous content
        appRoot.appendChild(pageFunction());
        updateFooterNav(); // Update nav links based on auth state
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
        <div id="login-error" class="error-message" style="display:none;"></div>
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

    const errorDiv = page.querySelector('#login-error');
    page.querySelector('#login-form').addEventListener('submit', (e) => {
        e.preventDefault();
        errorDiv.style.display = 'none'; // Hide previous errors
        errorDiv.textContent = '';

        const email = e.target.email.value;
        const password = e.target.password.value;

        fetch(`${API_BASE_URL}/v1/auth/login`, {
            method: 'POST',
            headers: getAuthHeaders(), // Includes 'Content-Type': 'application/json'
            body: JSON.stringify({ email, password })
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 200 && body.access_token) {
                storeToken(body.access_token);
                const decodedToken = decodeJWT(body.access_token);
                if (decodedToken && decodedToken.user_id) {
                    currentUserId = decodedToken.user_id;
                    console.log('Login successful, user ID:', currentUserId);
                } else {
                    console.error('Login successful, but user_id not found in token.');
                    // Fallback or error handling if user_id is crucial immediately
                }
                window.location.hash = '#exercises'; // Navigate to exercises page on successful login
            } else {
                console.error('Login failed:', body.error || 'Unknown error');
                errorDiv.textContent = body.error || 'Login failed. Please check your credentials.';
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Login API call failed:', error);
            errorDiv.textContent = 'An error occurred during login. Please try again.';
            errorDiv.style.display = 'block';
        });
    });
    return page;
}

// --- Signup Page ---
function SignupPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = `
        <h2>Sign Up</h2>
        <div id="signup-message" class="message" style="display:none;"></div>
        <div id="signup-error" class="error-message" style="display:none;"></div>
        <form id="signup-form">
            <div>
                <label for="signup-email">Email:</label>
                <input type="email" id="signup-email" name="email" required>
            </div>
            <div>
                <label for="signup-password">Password:</label>
                <input type="password" id="signup-password" name="password" minlength="8" required>
            </div>
            <div>
                <label for="signup-confirm-password">Confirm Password:</label>
                <input type="password" id="signup-confirm-password" name="confirm_password" minlength="8" required>
            </div>
            <button type="submit">Sign Up</button>
        </form>
        <p>Already have an account? <a href="#login">Login</a></p>
    `;

    const errorDiv = page.querySelector('#signup-error');
    const messageDiv = page.querySelector('#signup-message');

    page.querySelector('#signup-form').addEventListener('submit', (e) => {
        e.preventDefault();
        errorDiv.style.display = 'none'; errorDiv.textContent = '';
        messageDiv.style.display = 'none'; messageDiv.textContent = '';

        const email = e.target.email.value;
        const password = e.target.password.value;
        const confirmPassword = e.target.confirm_password.value;

        if (password !== confirmPassword) {
            errorDiv.textContent = "Passwords do not match.";
            errorDiv.style.display = 'block';
            return;
        }

        fetch(`${API_BASE_URL}/v1/auth/register`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ email, password })
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 201) {
                messageDiv.textContent = 'Signup successful! Please login.';
                messageDiv.style.display = 'block';
                // Optionally redirect to login after a short delay or clear form
                e.target.reset(); // Clear form
                setTimeout(() => window.location.hash = '#login', 2000);
            } else {
                errorDiv.textContent = body.error || 'Signup failed. Please try again.';
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Signup API call failed:', error);
            errorDiv.textContent = 'An error occurred during signup. Please try again.';
            errorDiv.style.display = 'block';
        });
    });
    return page;
}


function WorkoutListPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.id = 'workout-list';
    page.innerHTML = `
        <h2>My Workouts</h2>
        <div id="workout-list-container">Loading workouts...</div>
        <div id="workout-list-error" class="error-message" style="display:none;"></div>
        <button onclick="window.location.hash='#exercises'">Start New Workout (Browse Exercises)</button>
    `;

    const container = page.querySelector('#workout-list-container');
    const errorDiv = page.querySelector('#workout-list-error');

    if (!currentUserId) {
        errorDiv.textContent = "User not identified. Please login again.";
        errorDiv.style.display = 'block';
        container.innerHTML = ''; // Clear loading message
        return page;
    }

    // Fetch user's workouts (P1-BE-011)
    fetch(`${API_BASE_URL}/v1/users/${currentUserId}/workouts?page=1&per_page=10`, { // Example pagination
        method: 'GET',
        headers: getAuthHeaders()
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(({ status, body }) => {
        if (status === 200) {
            if (body.data && body.data.length > 0) {
                let ul = '<ul>';
                body.data.forEach(workout => {
                    ul += `<li>
                        <strong>Workout started: ${new Date(workout.started_at).toLocaleString()}</strong>
                        (ID: ${workout.id.substring(0,8)})
                        <button onclick="resumeWorkout('${workout.id}')">View/Resume</button>
                    </li>`;
                });
                ul += '</ul>';
                container.innerHTML = ul;
            } else {
                container.innerHTML = '<p>No workouts found. Start one by logging an exercise!</p>';
            }
        } else {
            errorDiv.textContent = body.error || 'Failed to load workouts.';
            errorDiv.style.display = 'block';
            container.innerHTML = '';
        }
    })
    .catch(error => {
        console.error('Error fetching workouts:', error);
        errorDiv.textContent = 'An error occurred while fetching workouts.';
        errorDiv.style.display = 'block';
        container.innerHTML = '';
    });

    return page;
}

// --- Exercise List Page ---
function ExerciseListPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = `
        <h2>Browse Exercises</h2>
        <div id="exercise-list-container">Loading exercises...</div>
        <div id="exercise-list-error" class="error-message" style="display:none;"></div>
    `;

    const container = page.querySelector('#exercise-list-container');
    const errorDiv = page.querySelector('#exercise-list-error');

    fetch(`${API_BASE_URL}/v1/exercises?page=1&per_page=50`, { // Fetch more exercises
        method: 'GET',
        headers: getAuthHeaders() // Requires auth
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(({ status, body }) => {
        if (status === 200) {
            if (body.data && body.data.length > 0) {
                let listHTML = '<ul>';
                body.data.forEach(ex => {
                    listHTML += `<li>
                        <strong>${ex.name}</strong> (${ex.category} / ${ex.equipment || 'N/A'})
                        <button onclick="navigateToLogSet('${ex.id}', '${ex.name}')">Log this Exercise</button>
                    </li>`;
                });
                listHTML += '</ul>';
                container.innerHTML = listHTML;
            } else {
                container.innerHTML = '<p>No exercises found.</p>';
            }
        } else {
            errorDiv.textContent = body.error || 'Failed to load exercises.';
            errorDiv.style.display = 'block';
            container.innerHTML = '';
        }
    })
    .catch(error => {
        console.error('Error fetching exercises:', error);
        errorDiv.textContent = 'An error occurred while fetching exercises.';
        errorDiv.style.display = 'block';
        container.innerHTML = '';
    });

    return page;
}


function LogSetPage() {
    const page = document.createElement('div');
    page.className = 'page active';

    const params = new URLSearchParams(window.location.hash.split('?')[1]);
    const exerciseName = params.get('exerciseName') || 'Selected Exercise';
    // For a real app, exerciseId would be reliably passed.
    const exerciseIdFromParam = params.get('exerciseId');
    const exerciseId = exerciseIdFromParam; // Will be undefined if not passed, handle below.

    if (!exerciseId) {
        page.innerHTML = '<h2>Error: Exercise ID missing.</h2><p><a href="#exercises">Go back to exercises.</a></p>';
        return page;
    }
    if (!currentUserId) { // Should be set after login
        page.innerHTML = '<h2>Error: User not identified. Please login.</h2><p><a href="#login">Login</a></p>';
        return page;
    }

    page.innerHTML = `
        <h2>Log Set for ${exerciseName}</h2>
        <div id="logset-message" class="message" style="display:none;"></div>
        <div id="logset-error" class="error-message" style="display:none;"></div>

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
    // Ensure engine/app.py is running and accessible
    const apiUrl = `${API_BASE_URL}/v1/user/${currentUserId}/exercise/${exerciseId}/recommend-set-parameters`;
    console.log(`Fetching recommendation from: ${apiUrl}`);

    if (currentUserId && exerciseId) { // Only fetch if both IDs are available
        fetch(apiUrl, { headers: getAuthHeaders() }) // Add Auth headers
          .then(response => {
            if (!response.ok) {
              return response.json().then(errData => {
                throw new Error(errData.error || `HTTP error! Status: ${response.status}`);
              }).catch(() => {
                throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
              });
            }
            return response.json();
          })
          .then(data => {
            if (data.recommended_weight_kg !== undefined) {
              recWeightEl.textContent = data.recommended_weight_kg;
              recRepsEl.textContent = `${data.target_reps_low} - ${data.target_reps_high}`;
              recRirEl.textContent = data.target_rir;
              tooltipTriggerEl.title = data.explanation;
              recErrorEl.textContent = '';
              page.querySelector('#weight').value = data.recommended_weight_kg;
              page.querySelector('#reps').value = data.target_reps_high;
              page.querySelector('#rir').value = data.target_rir;
            } else {
              const errorMsg = data.error || 'Could not parse AI recommendation data.';
              recErrorEl.textContent = errorMsg;
              // Keep N/A or clear recommendation fields
            }
          })
          .catch(error => {
            console.error('Error fetching AI recommendation:', error);
            recErrorEl.textContent = `AI Rec Error: ${error.message}`;
            // Keep N/A or clear recommendation fields
          });
    } else {
        aiRecommendationDiv.innerHTML = '<p>AI Recommendations not available (missing user/exercise ID).</p>';
    }

    const messageDiv = page.querySelector('#logset-message');
    const formErrorDiv = page.querySelector('#logset-error');

    page.querySelector('#log-set-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        messageDiv.style.display = 'none'; messageDiv.textContent = '';
        formErrorDiv.style.display = 'none'; formErrorDiv.textContent = '';

        // Step 1: Ensure currentWorkoutId is set (Implicit Workout Creation)
        if (!currentWorkoutId) {
            try {
                console.log("No active workout ID, creating a new one for user:", currentUserId);
                const workoutResponse = await fetch(`${API_BASE_URL}/v1/users/${currentUserId}/workouts`, {
                    method: 'POST',
                    headers: getAuthHeaders(),
                    body: JSON.stringify({ notes: 'New workout session started via exercise logging.' })
                });
                const workoutData = await workoutResponse.json();
                if (!workoutResponse.ok) {
                    throw new Error(workoutData.error || 'Failed to create workout session.');
                }
                currentWorkoutId = workoutData.id;
                console.log('New workout session created:', currentWorkoutId);
            } catch (err) {
                console.error('Error creating workout session:', err);
                formErrorDiv.textContent = `Error starting workout: ${err.message}`;
                formErrorDiv.style.display = 'block';
                return;
            }
        }

        // Step 2: Log the set
        const setData = {
            exercise_id: exerciseId,
            set_number: 1, // Simplified: manage set_number properly in a real app
            actual_weight: parseFloat(e.target.weight.value),
            actual_reps: parseInt(e.target.reps.value),
            actual_rir: parseInt(e.target.rir.value),
            // completed_at: new Date().toISOString() // Backend defaults to NOW()
        };

        fetch(`${API_BASE_URL}/v1/workouts/${currentWorkoutId}/sets`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(setData)
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 201) {
                messageDiv.textContent = 'Set logged successfully!';
                messageDiv.style.display = 'block';
                e.target.reset(); // Clear form for next set
                // Optionally, keep recommended values or smart clear
                page.querySelector('#weight').value = setData.actual_weight; // Keep weight for next set
                page.querySelector('#reps').value = ''; // Clear reps
                page.querySelector('#rir').value = '';  // Clear RIR
            } else {
                formErrorDiv.textContent = body.error || 'Failed to log set.';
                formErrorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error logging set:', error);
            formErrorDiv.textContent = 'An error occurred while logging the set.';
            formErrorDiv.style.display = 'block';
        });
    });
    return page;
}

// --- Footer Navigation Update ---
function updateFooterNav() {
    const footerNav = document.querySelector('footer nav');
    if (getToken()) {
        footerNav.innerHTML = `
            <a href="#exercises">Exercises</a>
            <a href="#workouts">My Workouts</a>
            <a href="#rir-weight-input">RIR/Weight Calc</a>
            <a href="#" id="logout-link">Logout</a>
        `;
        footerNav.querySelector('#logout-link').addEventListener('click', (e) => {
            e.preventDefault();
            removeToken();
            window.location.hash = '#login'; // Triggers navigation and clears page
        });
    } else {
        footerNav.innerHTML = `
            <a href="#login">Login</a>
            <a href="#signup">Sign Up</a>
        `;
    }
}


function NotFoundPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = '<h2>404 - Page Not Found</h2>';
    return page;
}

// Helper to navigate to LogSetPage with params
function navigateToLogSet(exerciseId, exerciseName) {
    window.location.hash = `#logset?exerciseId=${exerciseId}&exerciseName=${encodeURIComponent(exerciseName)}`;
}

// Placeholder for resuming a workout - could navigate to a workout detail page or pre-fill log set
function resumeWorkout(workoutId) {
    currentWorkoutId = workoutId; // Set the current workout
    // For P1, maybe just go to exercise list to add more sets to this workout.
    // Or a dedicated workout detail page would be ideal.
    window.location.hash = '#exercises';
    alert(`Resuming workout ${workoutId.substring(0,8)}. Go to Exercises to add more sets.`);
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
            if (remainingWeightPerSide > 0.01) {
                breakdown += ` (+${remainingWeightPerSide.toFixed(2)}kg not loadable per side)`;
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

        console.log(`Using Weight for ${exercise}: ${finalWeight}kg, Target Reps: ${targetReps}, Target RIR: ${targetRir}`);
        alert(`Selected: ${finalWeight}kg for ${exercise}.`);
    });
    return page;
}
