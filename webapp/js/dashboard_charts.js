// Define API_BASE_URL and auth helper functions (similar to plan_builder.js)
const API_BASE_URL = 'http://localhost:5000';

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

// Global store for fetched data to avoid re-fetching for selectors
let allExercises = []; // To store exercise names and IDs
let current1RMEvolutionData = {}; // Store all 1RM data fetched

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Dashboard charts script loaded and DOM fully parsed.');

    // Fetch all exercises once for selectors
    try {
        const response = await fetch(`${API_BASE_URL}/v1/exercises`); // Assuming no auth needed
        if (!response.ok) throw new Error('Failed to fetch exercises for selectors');
        const exerciseData = await response.json();
        allExercises = exerciseData.data || [];
    } catch (error) {
        console.error("Could not fetch exercises for selectors:", error);
        // Proceed without exercises for selectors, charts might show limited functionality
    }

    init1RMEvolutionChart();
    // initStrengthCurveChart(); // Deferred
    const strengthCurveCanvas = document.getElementById('strengthCurveChart');
    if (strengthCurveCanvas) {
        const ctx = strengthCurveCanvas.getContext('2d');
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText("Strength Curve Chart data integration is deferred.", strengthCurveCanvas.width / 2, strengthCurveCanvas.height / 2);
    }


    initVolumeDistributionChart();
    displayKeyMetrics();
    initPlateauStatusDisplay(); // New function to be implemented
});

// Store chart instances globally to manage their lifecycle
window.current1RMChart = null;
// window.currentStrengthCurveChart = null; // Deferred
window.currentVolumeChart = null;

// --- Removed Mock Data ---
// const mock1RMEvolutionData = { ... };
// const mockStrengthCurveData = { ... };
// const mockWeeklyVolumeData = [ ... ];
// const mockKeyMetricsData = { ... };


function render1RMEvolutionChart(exerciseId) { // Changed to exerciseId (UUID)
    console.log(`Rendering 1RM Evolution Chart for exercise ID: ${exerciseId}`);
    const ctx = document.getElementById('1rmEvolutionChart').getContext('2d');
    if (!ctx) { console.error('1rmEvolutionChart canvas element not found for rendering!'); return; }

    const exerciseData = current1RMEvolutionData[exerciseId];
    const selectedExercise = allExercises.find(ex => ex.id === exerciseId);
    const exerciseName = selectedExercise ? selectedExercise.name : `Exercise ID ${exerciseId}`;

    if (!exerciseData || exerciseData.length === 0) {
        console.warn(`No 1RM data found for exercise: ${exerciseName} (ID: ${exerciseId})`);
        if (window.current1RMChart) { window.current1RMChart.destroy(); window.current1RMChart = null; }
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText(`No 1RM data available for ${exerciseName}.`, ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }
    const labels = exerciseData.map(dp => dp.date); // Dates should be in 'YYYY-MM-DD'
    const dataPoints = exerciseData.map(dp => dp.estimated_1rm);
    if (window.current1RMChart) { window.current1RMChart.destroy(); }
    try {
        window.current1RMChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: `${exerciseName} e1RM (kg)`,
                    data: dataPoints,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'month', tooltipFormat: 'MMM dd, yyyy', displayFormats: { month: 'MMM yyyy'}},
                        title: { display: true, text: 'Date' }
                    },
                    y: {
                        title: { display: true, text: 'Estimated 1RM (kg)' },
                        beginAtZero: false
                    }
                },
                plugins: {
                    title: { display: true, text: `1RM Evolution for ${exerciseName}` },
                    legend: { display: true, position: 'top' }
                }
            }
        });
        console.log(`1RM Evolution Chart for ${exerciseName} rendered successfully.`);
    } catch (error) { console.error(`Error rendering 1RM Evolution Chart for ${exerciseName}:`, error); }
}

async function init1RMEvolutionChart() {
    console.log('Setting up 1RM Evolution Chart and Selector...');
    const selector = document.getElementById('exerciseSelector1RM');
    if (!selector) { console.error('exerciseSelector1RM element not found!'); return; }

    const userId = getUserId();
    if (!userId) {
        console.warn("User ID not found. Cannot load 1RM evolution data.");
        const ctx = document.getElementById('1rmEvolutionChart').getContext('2d');
        if (ctx) { ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); ctx.font = "16px Arial"; ctx.textAlign = "center"; ctx.fillText("Login to see 1RM evolution.", ctx.canvas.width / 2, ctx.canvas.height / 2); }
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/1rm-evolution`, { headers: getAuthHeaders() });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        current1RMEvolutionData = await response.json(); // Store globally for this page

        selector.innerHTML = ''; // Clear previous options
        const exerciseIdsWithData = Object.keys(current1RMEvolutionData);

        if (allExercises.length > 0 && exerciseIdsWithData.length > 0) {
            exerciseIdsWithData.forEach(exerciseId => {
                const exerciseDetails = allExercises.find(ex => ex.id === exerciseId);
                if (exerciseDetails) {
                    const option = document.createElement('option');
                    option.value = exerciseId; // Use ID as value
                    option.textContent = exerciseDetails.name;
                    selector.appendChild(option);
                }
            });

            selector.addEventListener('change', (event) => render1RMEvolutionChart(event.target.value));

            if (exerciseIdsWithData.length > 0) {
                const initialExerciseId = exerciseIdsWithData[0];
                selector.value = initialExerciseId;
                render1RMEvolutionChart(initialExerciseId);
            } else {
                 throw new Error("No 1RM evolution data returned from backend.");
            }
        } else {
             throw new Error("No exercises with 1RM data found, or exercise list not loaded.");
        }
    } catch (error) {
        console.error("Failed to initialize 1RM Evolution Chart:", error);
        const ctx = document.getElementById('1rmEvolutionChart').getContext('2d');
        if (ctx) { ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); ctx.font = "16px Arial"; ctx.textAlign = "center"; ctx.fillText("Could not load 1RM data.", ctx.canvas.width / 2, ctx.canvas.height / 2); }
    }
}

// --- Strength Curve Chart (Deferred) ---
// function calculateTheoreticalLoad(e1RM, reps) { ... }
// function renderStrengthCurveChart(exerciseName) { ... }
// function initStrengthCurveChart() { ... }


const muscleGroupColors = {
    "Legs": "rgba(255, 99, 132, 0.7)", "Chest": "rgba(54, 162, 235, 0.7)",
    "Back": "rgba(255, 206, 86, 0.7)", "Shoulders": "rgba(255, 159, 64, 0.7)",
    "Biceps": "rgba(153, 102, 255, 0.7)", "Triceps": "rgba(75, 192, 192, 0.7)",
    "Core": "rgba(100, 100, 100, 0.7)", "Other": "rgba(201, 203, 207, 0.7)",
    // Add more specific muscle groups if your backend provides them
};
let usedColorKeys = []; // To cycle through colors if more muscle groups than defined colors

function getMuscleGroupColor(muscleGroup) {
    if (muscleGroupColors[muscleGroup]) {
        return muscleGroupColors[muscleGroup];
    }
    // Cycle through defined colors if muscle group not explicitly defined
    const colorKeys = Object.keys(muscleGroupColors);
    if (usedColorKeys.length === colorKeys.length) usedColorKeys = []; // Reset if all used

    let nextColorKey = colorKeys.find(k => !usedColorKeys.includes(k));
    if (!nextColorKey) nextColorKey = "Other"; // Fallback

    usedColorKeys.push(nextColorKey);
    return muscleGroupColors[nextColorKey];
}


function processWeeklyVolumeData(heatmapData) {
    if (!heatmapData || heatmapData.length === 0) {
        return { labels: [], datasets: [] };
    }

    // Sort data by week to ensure labels are chronological
    heatmapData.sort((a, b) => new Date(a.week) - new Date(b.week));

    const weekLabels = [...new Set(heatmapData.map(item => item.week))];
    const muscleGroups = [...new Set(heatmapData.map(item => item.muscle_group))];

    const datasets = muscleGroups.map(mg => {
        const dataForMuscleGroup = weekLabels.map(week => {
            const weekData = heatmapData.find(item => item.week === week && item.muscle_group === mg);
            return weekData ? weekData.volume : 0;
        });
        return {
            label: mg,
            data: dataForMuscleGroup,
            backgroundColor: getMuscleGroupColor(mg),
            borderColor: getMuscleGroupColor(mg).replace('0.7', '1'),
            borderWidth: 1
        };
    });

    return { labels: weekLabels, datasets: datasets };
}

async function initVolumeDistributionChart() {
    console.log('Initializing Volume Distribution Chart...');
    const ctxElement = document.getElementById('volumeDistributionChart');
    if (!ctxElement) { console.error('volumeDistributionChart canvas element not found!'); return; }
    const ctx = ctxElement.getContext('2d');

    const userId = getUserId();
    if (!userId) {
        console.warn("User ID not found. Cannot load volume heatmap data.");
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText("Login to see volume distribution.", ctxElement.width / 2, ctxElement.height / 2);
        return;
    }

    if (window.currentVolumeChart) { window.currentVolumeChart.destroy(); }

    try {
        const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/volume-heatmap`, { headers: getAuthHeaders() });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const heatmapData = await response.json();
        const processedData = processWeeklyVolumeData(heatmapData);

        window.currentVolumeChart = new Chart(ctx, {
            type: 'bar',
            data: processedData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: { display: true, text: 'Weekly Volume by Muscle Group' },
                    tooltip: { mode: 'index', intersect: false },
                    legend: { position: 'top' }
                },
                scales: {
                    x: {
                        title: { display: true, text: 'Week (Start Date)' },
                        stacked: false // Set to true for stacked bar chart
                    },
                    y: {
                        title: { display: true, text: 'Total Volume (Weight * Reps)' },
                        beginAtZero: true,
                        stacked: false // Set to true for stacked bar chart
                        // ticks: { stepSize: 1 } // Might not be relevant for large volume numbers
                    }
                }
            }
        });
        console.log('Volume Distribution Chart initialized successfully with backend data.');
    } catch (error) {
        console.error('Error initializing Volume Distribution Chart:', error);
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText("Could not load volume data.", ctxElement.width / 2, ctxElement.height / 2);
        alert(`Could not load volume data: ${error.message}`);
    }
}


async function displayKeyMetrics() {
    console.log('Displaying Key Metrics...');
    const metricsListElement = document.getElementById('metrics-list');
    if (!metricsListElement) { console.error('metrics-list element not found!'); return; }

    const userId = getUserId();
    if (!userId) {
        metricsListElement.innerHTML = '<li>Login to see your key metrics.</li>';
        return;
    }
    metricsListElement.innerHTML = '<li>Loading metrics...</li>';

    try {
        const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/key-metrics`, { headers: getAuthHeaders() });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const metricsData = await response.json();
        metricsListElement.innerHTML = ''; // Clear loading/previous metrics

        const metricsToDisplay = {
            total_workouts: "Total Workouts",
            total_volume: "Total Volume Lifted",
            avg_session_rpe: "Avg. Session RPE",
            most_frequent_exercise: "Most Frequent Exercise"
        };

        for (const key in metricsToDisplay) {
            const li = document.createElement('li');
            const metricNameSpan = document.createElement('span');
            metricNameSpan.classList.add('metric-name');
            metricNameSpan.textContent = metricsToDisplay[key] + ': ';
            li.appendChild(metricNameSpan);

            const metricValueSpan = document.createElement('span');
            metricValueSpan.classList.add('metric-value');

            if (key === "most_frequent_exercise") {
                if (metricsData[key] && metricsData[key].name) {
                    metricValueSpan.textContent = `${metricsData[key].name} (${metricsData[key].frequency} times)`;
                } else {
                    metricValueSpan.textContent = "N/A";
                }
            } else {
                 metricValueSpan.textContent = metricsData[key] !== undefined ? metricsData[key] : "N/A";
            }
            li.appendChild(metricValueSpan);
            metricsListElement.appendChild(li);
        }

    } catch (error) {
        console.error('Error fetching key metrics:', error);
        metricsListElement.innerHTML = '<li>Could not load key metrics.</li>';
        alert(`Error fetching key metrics: ${error.message}`);
    }
}

// --- Plateau Status Display (New) ---
async function initPlateauStatusDisplay() {
    const plateauExerciseSelector = document.getElementById('plateauExerciseSelector');
    const plateauStatusDisplay = document.getElementById('plateauStatusDisplay');

    if (!plateauExerciseSelector || !plateauStatusDisplay) {
        console.warn('Plateau status display elements not found.');
        return;
    }

    // Populate exercise selector
    if (allExercises.length > 0) {
        allExercises.forEach(exercise => {
            const option = document.createElement('option');
            option.value = exercise.id; // Use ID
            option.textContent = exercise.name;
            plateauExerciseSelector.appendChild(option);
        });
        // Add event listener if exercises were populated
        plateauExerciseSelector.addEventListener('change', fetchAndDisplayPlateauStatus);
        // Optionally, load status for the first exercise
        if (allExercises.length > 0) {
             fetchAndDisplayPlateauStatus({ target: { value: allExercises[0].id } }); // Simulate event
        }
    } else {
        plateauExerciseSelector.innerHTML = '<option value="">No exercises loaded</option>';
        plateauStatusDisplay.innerHTML = '<p>Load exercises to see plateau status.</p>';
    }
}

async function fetchAndDisplayPlateauStatus(event) {
    const exerciseId = event.target.value;
    const plateauStatusDisplay = document.getElementById('plateauStatusDisplay');
    if (!plateauStatusDisplay) return;

    const userId = getUserId();
    if (!userId) {
        plateauStatusDisplay.innerHTML = '<p>Please login to view plateau status.</p>';
        return;
    }
    if (!exerciseId) {
        plateauStatusDisplay.innerHTML = '<p>Select an exercise to see its plateau status.</p>';
        return;
    }

    plateauStatusDisplay.innerHTML = `<p>Loading plateau status for exercise ID ${exerciseId}...</p>`;

    try {
        const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/exercises/${exerciseId}/plateau-analysis`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: 'Unknown error fetching plateau status.' }));
            throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        let htmlContent = `<h4>Plateau Analysis for ${data.exercise_name || 'Selected Exercise'}</h4>`;
        htmlContent += `<p><strong>Summary:</strong> ${data.summary_message || 'N/A'}</p>`;
        if (data.plateau_analysis) {
            htmlContent += `<p><strong>Status:</strong> ${data.plateau_analysis.status || 'N/A'}</p>`;
            if (data.plateau_analysis.plateauing) {
                 htmlContent += `<p><strong>Details:</strong> Detected for ${data.plateau_analysis.duration} data points with a slope of ${data.plateau_analysis.slope ? data.plateau_analysis.slope.toFixed(4) : 'N/A'}.</p>`;
            }
        }
        htmlContent += `<p><strong>Current Fatigue Score:</strong> ${data.current_fatigue_score !== null ? data.current_fatigue_score : 'N/A'}</p>`;
        htmlContent += `<p><strong>Deload Suggested:</strong> ${data.deload_suggested ? 'Yes' : 'No'}</p>`;
        if (data.deload_suggested && data.deload_protocol) {
            htmlContent += `<h5>Deload Protocol:</h5>`;
            htmlContent += `<ul>`;
            for (const key in data.deload_protocol) {
                htmlContent += `<li><strong>${key.replace(/_/g, ' ')}:</strong> ${data.deload_protocol[key]}</li>`;
            }
            htmlContent += `</ul>`;
        }
        plateauStatusDisplay.innerHTML = htmlContent;

    } catch (error) {
        console.error('Error fetching plateau status:', error);
        plateauStatusDisplay.innerHTML = `<p>Error loading plateau status: ${error.message}</p>`;
        alert(`Error fetching plateau status: ${error.message}`);
    }
}
