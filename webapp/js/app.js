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
    // Also remove refresh token if stored separately
    localStorage.removeItem('refreshToken'); // Added for logout
    localStorage.removeItem('workoutFlowState'); // Clear any active workout state
    // Add any other specific app data stored in localStorage that needs clearing on logout
    // For a more thorough cleanup, consider iterating keys or using a prefix if applicable

    currentUserId = null; // Clear global userId on logout
    currentWorkoutId = null; // Clear global workoutId on logout
    // window.workoutFlowManager?._clearState(); // Also ensure workout flow manager state is cleared
}

// --- Logout Function ---
async function handleLogout() {
    console.log("Handling logout...");
    showGlobalLoader(); // Show loader during logout process

    const accessToken = getToken(); // Gets 'jwtToken'
    const refreshToken = localStorage.getItem('refreshToken'); // Assuming it's stored with this key

    // Regardless of API call success, clear local data and redirect.
    const cleanupAndRedirect = async () => {
        removeToken(); // Clears access token, refresh token, and other relevant app data

        // 3. Implement Service Worker Cache Clearing / Unregistration
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.getRegistration();
                if (registration) {
                    await registration.unregister();
                    console.log('Service worker unregistered successfully.');
                } else {
                    console.log('No active service worker registration found to unregister.');
                }
            } catch (error) {
                console.error('Error unregistering service worker:', error);
            }
        }

        // Clear caches explicitly - this is more aggressive
        if (window.caches) {
            try {
                const keys = await window.caches.keys();
                await Promise.all(keys.map(key => window.caches.delete(key)));
                console.log('All caches deleted successfully.');
            } catch (error) {
                console.error('Error deleting caches:', error);
            }
        }

        console.log("Tokens and local data cleared. Redirecting to login.");
        window.location.hash = '#login'; // Navigate to login page
        // The navigate() function in DOMContentLoaded should hide the loader
        // but if not, or if logout happens before full load:
        hideGlobalLoader();
    };

    if (accessToken && refreshToken) {
        try {
            const response = await fetch(`${API_BASE_URL}/v1/auth/logout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ refresh_token: refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Logout successful on server:', data.msg);
            } else {
                // Log error but proceed with client-side logout anyway
                const errorData = await response.json().catch(() => ({ error: "Logout failed, unknown server error" }));
                console.warn('Server logout failed or encountered an error:', response.status, errorData.error);
            }
        } catch (error) {
            // Log error but proceed with client-side logout anyway
            console.error('Error during logout API call:', error);
        }
    } else {
        console.log("No access or refresh token found, proceeding with client-side cleanup.");
    }

    await cleanupAndRedirect();
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

// --- Workout Flow Management ---
class WorkoutFlow {
    constructor() {
        this.currentWorkoutId = null;
        this.planDayId = null; // ID of the plan day being executed, if applicable
        this.exercises = []; // Array of exercise objects { id, name, ...other details }
        this.currentExerciseIndex = -1;
        // this.currentSetNumberPerExercise = {}; // Managed by workout_execution.js for now
        this.workoutStartTime = null;
        this.apiBaseUrl = ''; // Default, should be set or read from global config

        this._loadState(); // Load state from localStorage on initialization
    }

    _getApiBaseUrl() {
        // Prefer global API_BASE_URL if defined and not empty, else use internal or default
        return (typeof API_BASE_URL !== 'undefined' && API_BASE_URL) ? API_BASE_URL : (this.apiBaseUrl || 'http://localhost:5000');
    }

    _saveState() {
        const state = {
            currentWorkoutId: this.currentWorkoutId,
            planDayId: this.planDayId,
            exercises: this.exercises,
            currentExerciseIndex: this.currentExerciseIndex,
            workoutStartTime: this.workoutStartTime,
        };
        localStorage.setItem('workoutFlowState', JSON.stringify(state));
        console.log('WorkoutFlow state saved.');
    }

    _loadState() {
        const savedState = localStorage.getItem('workoutFlowState');
        if (savedState) {
            try {
                const state = JSON.parse(savedState);
                this.currentWorkoutId = state.currentWorkoutId;
                this.planDayId = state.planDayId;
                this.exercises = state.exercises || [];
                this.currentExerciseIndex = state.currentExerciseIndex !== undefined ? state.currentExerciseIndex : -1;
                this.workoutStartTime = state.workoutStartTime ? new Date(state.workoutStartTime) : null;
                console.log('WorkoutFlow state loaded:', this);
            } catch (e) {
                console.error("Error parsing workoutFlowState from localStorage:", e);
                this._clearState(); // Clear corrupted state
            }
        }
    }

    _clearState() {
        this.currentWorkoutId = null;
        this.planDayId = null;
        this.exercises = [];
        this.currentExerciseIndex = -1;
        this.workoutStartTime = null;
        localStorage.removeItem('workoutFlowState');
        console.log('WorkoutFlow state cleared.');
    }

    isWorkoutActive() {
        return !!this.currentWorkoutId && this.currentExerciseIndex >= 0;
    }

    async startWorkout(planOrExercises) {
        if (this.isWorkoutActive()) {
            // For simplicity in P1, we might just override. A real app would confirm.
            console.warn("An active workout is already in progress. Starting a new one will clear the previous state.");
            // Consider calling endWorkout or prompting user. For now, just clear.
            await this.endWorkout(false); // End silently without navigation
        }
        this._clearState(); // Ensure clean slate before starting

        if (!planOrExercises) {
            console.error("Cannot start workout: planOrExercises data is missing.");
            return false;
        }

        // Determine if it's a plan day object or a direct list of exercises
        if (planOrExercises.id && Array.isArray(planOrExercises.exercises)) { // Looks like a plan day
            this.planDayId = planOrExercises.id;
            this.exercises = planOrExercises.exercises.map(ex => ({ id: ex.exercise_id, name: ex.exercise_name, ...ex })); // Adapt structure
        } else if (Array.isArray(planOrExercises)) { // Direct list of exercises
             this.exercises = planOrExercises.map(ex => ({ id: ex.id, name: ex.name, ...ex })); // Ensure common structure
        } else {
            console.error("Invalid data provided to startWorkout. Expected plan day object or exercises array.");
            return false;
        }

        if (this.exercises.length === 0) {
            console.error("Cannot start workout: No exercises provided.");
            return false;
        }

        const userId = getUserId(); // Assumes getUserId() is globally available
        if (!userId) {
            console.error("User not logged in. Cannot start workout.");
            // alert("Please login to start a workout."); // Or redirect to login
            window.location.hash = '#login';
            return false;
        }

        try {
            const response = await fetch(`${this._getApiBaseUrl()}/v1/users/${userId}/workouts`, {
                method: 'POST',
                headers: getAuthHeaders(), // Assumes getAuthHeaders() is global
                body: JSON.stringify({
                    plan_day_id: this.planDayId, // Can be null
                    started_at: new Date().toISOString(),
                    notes: `Workout started with ${this.exercises.length} exercises.`
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to create workout session on backend.');
            }
            this.currentWorkoutId = data.id;
            this.workoutStartTime = new Date();
            this.currentExerciseIndex = 0;
            this._saveState();
            console.log('Workout started:', this);
            this.navigateToCurrentExercise();
            return true;
        } catch (error) {
            console.error('Error starting workout via API:', error);
            this._clearState(); // Clear any partial state
            alert(`Error starting workout: ${error.message}`);
            return false;
        }
    }

    async endWorkout(navigateToEndPage = true) {
        if (!this.isWorkoutActive()) {
            console.log("No active workout to end.");
            this._clearState(); // Ensure it's clean anyway
            if (navigateToEndPage) window.location.href = 'index.html'; // Or dashboard
            return;
        }

        // Optional: Prompt for Session RPE or other summary data
        // const sessionRPE = prompt("Enter overall session RPE (1-10):", "7");

        try {
            const response = await fetch(`${this._getApiBaseUrl()}/v1/workouts/${this.currentWorkoutId}`, { // Assuming a PUT or PATCH endpoint
                method: 'PUT', // Or PATCH
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    completed_at: new Date().toISOString(),
                    // session_rpe: sessionRPE ? parseInt(sessionRPE) : null
                }),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.error('Failed to mark workout as completed on backend:', errorData.error || response.status);
                // Don't throw, still clear local state
            }
        } catch (error) {
            console.error('Error ending workout via API:', error);
            // Don't throw, still clear local state
        }

        const endedWorkoutId = this.currentWorkoutId;
        this._clearState();
        console.log(`Workout ${endedWorkoutId} ended.`);
        if (navigateToEndPage) {
            alert("Workout Ended!"); // Placeholder for better UI
            window.location.href = 'index.html'; // Navigate to dashboard or summary page
        }
    }

    nextExercise() {
        if (!this.isWorkoutActive()) return;
        if (this.currentExerciseIndex < this.exercises.length - 1) {
            this.currentExerciseIndex++;
            this._saveState();
            this.navigateToCurrentExercise();
        } else {
            this.endWorkout(); // Ends workout and navigates
        }
    }

    previousExercise() {
        if (!this.isWorkoutActive() || this.currentExerciseIndex <= 0) return;
        this.currentExerciseIndex--;
        this._saveState();
        this.navigateToCurrentExercise();
    }

    navigateToCurrentExercise() {
        if (!this.isWorkoutActive()) return;
        const currentExercise = this.exercises[this.currentExerciseIndex];
        if (currentExercise && currentExercise.id && this.currentWorkoutId) {
            // workout_execution.html is a separate page, not hash-based SPA route
            window.location.href = `workout_execution.html?workoutId=${this.currentWorkoutId}&exerciseId=${currentExercise.id}`;
        } else {
            console.error("Cannot navigate: Missing current exercise, exercise ID, or workout ID.", currentExercise, this.currentWorkoutId);
            // Potentially end workout or redirect to error/dashboard
            this.endWorkout();
        }
    }

    getCurrentExerciseDetail() {
        if (!this.isWorkoutActive() || this.currentExerciseIndex < 0 || this.currentExerciseIndex >= this.exercises.length) {
            return null;
        }
        return this.exercises[this.currentExerciseIndex];
    }

    getCurrentWorkoutId() {
        return this.currentWorkoutId;
    }

    // Call this method from workout_execution.js after a set is successfully logged.
    // This is mainly for state tracking if WorkoutFlow needs to know about set counts.
    // For P1, primary set logging happens in workout_execution.js.
    // recordSetCompletion(exerciseId) {
    //     if (!this.isWorkoutActive()) return;
    //     // This is a simplified version. A more robust one might be needed if set counts influence flow.
    //     console.log(`Set completed for exercise ${exerciseId} in workout ${this.currentWorkoutId}`);
    //     this._saveState(); // Save if state needs to reflect this.
    // }
}

// Instantiate WorkoutFlow globally or make it accessible
window.workoutFlowManager = new WorkoutFlow();

// --- Global Loader Functions ---
function showGlobalLoader() {
    const loader = document.getElementById('global-loader');
    if (loader) {
        loader.classList.remove('hidden');
    }
}

function hideGlobalLoader() {
    const loader = document.getElementById('global-loader');
    if (loader) {
        loader.classList.add('hidden');
    }
}

// --- Navigation ---
const protectedRoutes = ['#workouts', '#logset', '#exercises', '#profile']; // Add other protected routes

document.addEventListener('DOMContentLoaded', () => {
    showGlobalLoader(); // Show loader as soon as DOM is ready
    const appRoot = document.getElementById('app-root');
    appRoot.innerHTML = ''; // Clear any static content like "Loading..." paragraph

    const routes = {
        '#login': LoginPage,
        '#signup': SignupPage, // Added SignupPage
        '#workouts': WorkoutListPage,
        '#logset': LogSetPage,
        '#exercises': ExerciseListPage, // Added ExerciseListPage
        '#rir-weight-input': RirWeightInputPage,
        '#profile': ProfilePage,
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
        try {
            appRoot.appendChild(pageFunction());
        } catch (e) {
            console.error("Error rendering page:", e);
            appRoot.appendChild(NotFoundPage()); // Fallback to NotFoundPage on error
        }
        updateFooterNav(); // Update nav links based on auth state
        hideGlobalLoader(); // Hide loader after page content is set
    }

    window.addEventListener('hashchange', () => {
        showGlobalLoader(); // Show loader on hash change
        navigate();
    });
    navigate(); // Initial navigation

    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => console.log('Service Worker registered successfully:', registration))
            .catch(error => console.log('Service Worker registration failed:', error));
    }
    if (window.QuickStart) {
        window.QuickStart.checkFirstTime();
    }

    // Hamburger menu functionality
    const hamburgerMenu = document.querySelector('.hamburger-menu');
    const navLinks = document.querySelector('.nav-links');

    if (hamburgerMenu && navLinks) {
        hamburgerMenu.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
    }

    // Stale Tab Protection
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            const currentToken = getToken(); // Checks for 'jwtToken'
            const currentRefreshToken = localStorage.getItem('refreshToken');
            const nonAuthPages = ['#login', '#signup']; // Pages accessible without login
            const currentPathRoot = window.location.hash.split('?')[0] || '#login';

            if (!currentToken || !currentRefreshToken) {
                // If tokens are missing and we are not on a non-auth page
                if (!nonAuthPages.includes(currentPathRoot)) {
                    console.log('Tokens missing on visible tab. Likely logged out in another tab. Redirecting to login.');
                    alert('You have been logged out. Please log in again.'); // Optional user message

                    // Clear any potentially remaining local state just in case
                    removeToken(); // Ensures all local auth-related items are cleared
                    window.location.hash = '#login';
                    // The navigate() function will handle rendering the login page
                    // and also calling updateFooterNav()
                }
            }
        }
    });
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
    const loginForm = page.querySelector('#login-form');
    const submitButton = loginForm.querySelector('button[type="submit"]');

    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        errorDiv.style.display = 'none'; // Hide previous errors
        errorDiv.textContent = '';
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="loader"></span> Logging in...';

        const email = e.target.email.value;
        const password = e.target.password.value;

        fetch(`${API_BASE_URL}/v1/auth/login`, {
            method: 'POST',
            headers: getAuthHeaders(), // Includes 'Content-Type': 'application/json'
            body: JSON.stringify({ email, password })
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(async ({ status, body }) => { // Made async
            if (status === 200 && body.access_token && body.refresh_token) { // Ensure refresh_token is present
                storeToken(body.access_token); // Stores access_token as 'jwtToken'
                localStorage.setItem('refreshToken', body.refresh_token); // Store refresh_token

                const decodedToken = decodeJWT(body.access_token);
                if (decodedToken && decodedToken.user_id) {
                    currentUserId = decodedToken.user_id;
                    console.log('Login successful, user ID:', currentUserId);

                    // Attempt to load user profile after login to get preferences like unit_system
                    // This assumes ProfileManager and loadUserProfile are defined elsewhere and globally accessible
                    if (window.ProfileManager && typeof window.ProfileManager.loadUserProfile === 'function') {
                        try {
                            await window.ProfileManager.loadUserProfile(currentUserId);
                            console.log("User profile loaded after login.");
                        } catch (profileError) {
                            console.warn("Failed to load user profile immediately after login:", profileError);
                            // Non-critical, app can proceed. Profile might be loaded later.
                        }
                    }

                } else {
                    console.error('Login successful, but user_id not found in token.');
                }
                window.location.hash = '#exercises'; // Navigate to exercises page on successful login
            } else {
                if (status === 200 && !body.refresh_token) {
                    console.error('Login successful, but refresh_token missing in response.');
                }
                console.error('Login failed:', body.error || 'Unknown error or missing tokens');
                errorDiv.textContent = body.error || 'Login failed. Please check your credentials.';
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Login API call failed:', error);
            errorDiv.textContent = 'An error occurred during login. Please try again.';
            errorDiv.style.display = 'block';
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
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
    const signupForm = page.querySelector('#signup-form');
    const submitButton = signupForm.querySelector('button[type="submit"]');

    signupForm.addEventListener('submit', (e) => {
        e.preventDefault();
        errorDiv.style.display = 'none'; errorDiv.textContent = '';
        messageDiv.style.display = 'none'; messageDiv.textContent = '';
        const originalButtonText = submitButton.textContent;
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="loader"></span> Signing up...';

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
        })
        .finally(() => {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
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
        <div id="workout-list-container"><div class="loader-container"><span class="loader"></span> Loading workouts...</div></div>
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
        <div id="exercise-list-container"><div class="loader-container"><span class="loader"></span> Loading exercises...</div></div>
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
    const exerciseIdFromParam = params.get('exerciseId');
    const exerciseId = exerciseIdFromParam;

    if (!exerciseId) {
        page.innerHTML = '<h2>Error: Exercise ID missing.</h2><p><a href="#exercises">Go back to exercises.</a></p>';
        return page;
    }
    if (!currentUserId) { // Should be set after login
        page.innerHTML = '<h2>Error: User not identified. Please login.</h2><p><a href="#login">Login</a></p>';
        return page;
    }

    let currentSetNumber = 1;
    const localExerciseId = exerciseId; // To avoid issues with 'exerciseId' in nested scopes

    function updateSetNumberDisplay(setNum) {
        const displayElement = page.querySelector('#current-set-number-display');
        if (displayElement) {
            displayElement.textContent = setNum;
        }
    }

    page.innerHTML = `
        <h2>Log Set <span id="current-set-number-display">1</span> for ${exerciseName}</h2>
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
    const messageDiv = page.querySelector('#logset-message');
    const formErrorDiv = page.querySelector('#logset-error');
    const logSetForm = page.querySelector('#log-set-form');
    const submitSetButton = logSetForm.querySelector('button[type="submit"]');


    updateSetNumberDisplay(currentSetNumber); // Initial display

    // Fetch AI Recommendation
    const apiUrl = `${API_BASE_URL}/v1/user/${currentUserId}/exercise/${localExerciseId}/recommend-set-parameters`;
    console.log(`Fetching recommendation from: ${apiUrl}`);

    if (currentUserId && localExerciseId) {
        fetch(apiUrl, { headers: getAuthHeaders() })
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
              recErrorEl.textContent = data.error || 'Could not parse AI recommendation data.';
            }
          })
          .catch(error => {
            console.error('Error fetching AI recommendation:', error);
            recErrorEl.textContent = `AI Rec Error: ${error.message}`;
          });
    } else {
        aiRecommendationDiv.innerHTML = '<p>AI Recommendations not available (missing user/exercise ID).</p>';
    }

    // Fetch existing sets to determine currentSetNumber
    if (currentWorkoutId && localExerciseId) {
        fetch(`${API_BASE_URL}/v1/workouts/${currentWorkoutId}/sets?exercise_id=${localExerciseId}`, {
            method: 'GET',
            headers: getAuthHeaders()
        })
        .then(response => {
            if (!response.ok) {
                console.error('Failed to fetch existing sets for exercise:', response.status);
                return { data: [] }; // Default to no existing sets on error
            }
            return response.json();
        })
        .then(existingSetsResult => {
            if (existingSetsResult && existingSetsResult.data && existingSetsResult.data.length > 0) {
                currentSetNumber = existingSetsResult.data.length + 1;
            } else {
                currentSetNumber = 1; // Default if no sets or error during fetch
            }
            updateSetNumberDisplay(currentSetNumber);
        })
        .catch(error => {
            console.error('Error fetching existing sets:', error);
            currentSetNumber = 1; // Default on network error
            updateSetNumberDisplay(currentSetNumber);
        });
    } else {
        // If no currentWorkoutId, it's effectively set 1 for a new workout
        updateSetNumberDisplay(currentSetNumber); // Ensure display is 1
    }


    logSetForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        messageDiv.style.display = 'none'; messageDiv.textContent = '';
        formErrorDiv.style.display = 'none'; formErrorDiv.textContent = '';
        const originalButtonText = submitSetButton.textContent;
        submitSetButton.disabled = true;
        submitSetButton.innerHTML = '<span class="loader"></span> Logging Set...';

        let workoutJustCreated = false;
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
                workoutJustCreated = true; // Mark that a workout was just created
                console.log('New workout session created:', currentWorkoutId);
            } catch (err) {
                console.error('Error creating workout session:', err);
                formErrorDiv.textContent = `Error starting workout: ${err.message}`;
                formErrorDiv.style.display = 'block';
                submitSetButton.disabled = false;
                submitSetButton.textContent = originalButtonText;
                return;
            }
        }

        const setData = {
            exercise_id: localExerciseId, // Use localExerciseId
            set_number: currentSetNumber, // Use dynamic set number
            actual_weight: parseFloat(e.target.weight.value),
            actual_reps: parseInt(e.target.reps.value),
            actual_rir: parseInt(e.target.rir.value),
        };

        fetch(`${API_BASE_URL}/v1/workouts/${currentWorkoutId}/sets`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(setData)
        })
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 201) {
                messageDiv.textContent = `Set ${currentSetNumber} logged successfully!`;
                messageDiv.style.display = 'block';
                currentSetNumber++; // Increment for the next set
                updateSetNumberDisplay(currentSetNumber); // Update display

                e.target.reset(); // Clear form for next set
                page.querySelector('#weight').value = setData.actual_weight;
                page.querySelector('#reps').value = '';
                page.querySelector('#rir').value = '';
            } else {
                formErrorDiv.textContent = body.error || 'Failed to log set.';
                formErrorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            console.error('Error logging set:', error);
            formErrorDiv.textContent = 'An error occurred while logging the set.';
            formErrorDiv.style.display = 'block';
            if (workoutJustCreated) { // If workout was created in this attempt but set log failed
                // Consider if you want to "rollback" or delete the empty workout.
                // For now, we'll leave it, but this is a point for future improvement.
                console.warn(`Workout ${currentWorkoutId} was created, but the first set failed to log. The workout remains.`);
            }
        })
        .finally(() => {
            submitSetButton.disabled = false;
            submitSetButton.textContent = originalButtonText;
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
            <a href="#profile">Profile</a>
            <a href="#rir-weight-input">RIR/Weight Calc</a>
            <a id="feedback-link" target="_blank">Beta Feedback</a>
            <a href="#" id="logout-link">Logout</a>
        `;
        // Attach the new handleLogout function
        const logoutLink = footerNav.querySelector('#logout-link');
        if (logoutLink) {
            logoutLink.addEventListener('click', async (e) => {
                e.preventDefault();
                await handleLogout();
            });
        }
    } else {
        footerNav.innerHTML = `
            <a href="#login">Login</a>
            <a href="#signup">Sign Up</a>
            <a id="feedback-link" target="_blank">Beta Feedback</a>
        `;
    }
    const feedbackAnchor = footerNav.querySelector('#feedback-link');
    if (feedbackAnchor) {
        feedbackAnchor.href = typeof SURVEY_URL !== 'undefined' ? SURVEY_URL : '#';
    }
}


function NotFoundPage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = '<h2>404 - Page Not Found</h2>';
    return page;
}

// --- Profile Page ---
function ProfilePage() {
    const page = document.createElement('div');
    page.className = 'page active';
    page.innerHTML = `
        <h2>User Profile</h2>
        <section id="equipment-management">
            <h3>My Equipment</h3>
            <div id="equipment-message" style="display:none;"></div>
            <form id="equipment-form">
                <h4>Weight Plates</h4>
                <div id="plate-selection">
                    <!-- Plate toggles/checkboxes will be dynamically added here by profile.js -->
                    <p>Loading plate options...</p>
                </div>
                <p>Default Barbell Weight (kg): <input type="number" id="barbell-weight-kg" value="20" step="0.5"></p>

                <h4>Dumbbells</h4>
                <div>
                    <label for="dumbbell-type">Type:</label>
                    <select id="dumbbell-type">
                        <option value="none">None</option>
                        <option value="fixed">Fixed Weight</option>
                        <option value="adjustable">Adjustable</option>
                    </select>
                </div>
                <div id="fixed-dumbbells-section" style="display:none;">
                    <label for="fixed-dumbbell-weights">Available Fixed Dumbbell Weights (kg, comma-separated):</label>
                    <input type="text" id="fixed-dumbbell-weights" placeholder="e.g., 5, 7.5, 10, 12.5, 15">
                </div>
                <div id="adjustable-dumbbells-section" style="display:none;">
                    <label for="adjustable-dumbbell-max-weight">Max Weight per Adjustable Dumbbell (kg):</label>
                    <input type="number" id="adjustable-dumbbell-max-weight" step="0.5">
                </div>

                <button type="submit">Save Equipment</button>
            </form>
        </section>
    `;
    return page;
}

// Helper to navigate to LogSetPage with params
async function navigateToLogSet(exerciseId, exerciseName) { // Made async
    // This function now starts a new workout with a single exercise.
    console.log(`Attempting to start workout with single exercise: ${exerciseName} (ID: ${exerciseId})`);
    if (window.workoutFlowManager) {
        const singleExercise = [{ id: exerciseId, name: exerciseName }]; // WorkoutFlow expects an array
        await window.workoutFlowManager.startWorkout(singleExercise);
        // startWorkout will handle navigation to workout_execution.html
    } else {
        console.error("workoutFlowManager not available.");
        // Fallback or error message
        alert("Workout flow manager is not initialized. Cannot start workout.");
    }
    // Original navigation to #logset is removed as WorkoutFlow now handles navigation.
    // window.location.hash = `#logset?exerciseId=${exerciseId}&exerciseName=${encodeURIComponent(exerciseName)}`;
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
