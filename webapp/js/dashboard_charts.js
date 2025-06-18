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
// let current1RMEvolutionData = {}; // Store all 1RM data fetched - REPLACED by on-demand fetching
let currentSelectedExercise1RMData = null; // Holds data for the currently displayed 1RM chart

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

    // Register chartjs-plugin-annotation globally if it's loaded
    if (window.Chart && window.ChartAnnotation) {
        Chart.register(window.ChartAnnotation);
        console.log('Chart.js Annotation plugin registered.');
    } else {
        console.warn('Chart.js Annotation plugin not found. MEV/MAV/MRV lines will not be displayed.');
    }
    // Register chartjs-chart-matrix components
    if (window.Chart && window.ChartMatrix) {
        Chart.register(ChartMatrix.MatrixController, ChartMatrix.MatrixElement);
        console.log('chartjs-chart-matrix plugin registered.');
    } else {
        console.warn('chartjs-chart-matrix plugin not found. Recovery Patterns Heatmap may not work.');
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
    initMTITrendsChart(); // Initialize the new MTI Trends Chart
    initStrengthGainsSummary(); // Initialize the new Strength Gains Summary
    initRecoveryPatternsHeatmap(); // Initialize the new Recovery Patterns Heatmap
});

// Store chart instances globally to manage their lifecycle
window.current1RMChart = null;
// window.currentStrengthCurveChart = null; // Deferred
window.currentVolumeChart = null;
window.currentMTIChart = null;
window.currentRecoveryHeatmap = null;

// --- Removed Mock Data ---
// const mock1RMEvolutionData = { ... };
// const mockStrengthCurveData = { ... };
// const mockWeeklyVolumeData = [ ... ];
// const mockKeyMetricsData = { ... };


function render1RMEvolutionChart(exerciseId, exerciseData) {
    console.log(`Rendering 1RM Evolution Chart for exercise ID: ${exerciseId} with new data.`);
    const canvas = document.getElementById('1rmEvolutionChart');
    const statusDiv = document.getElementById('chart1RMStatus');
    if (!canvas) { console.error('1rmEvolutionChart canvas element not found for rendering!'); return; }
    const ctx = canvas.getContext('2d');

    const selectedExercise = allExercises.find(ex => ex.id === exerciseId);
    const exerciseName = selectedExercise ? selectedExercise.name : `Exercise ID ${exerciseId}`;

    // This specific message is for when API call was successful but returned no records for this exercise
    if (!exerciseData || exerciseData.length === 0) {
        console.warn(`No 1RM data points found for exercise: ${exerciseName} (ID: ${exerciseId}) after successful fetch.`);
        if (window.current1RMChart) { window.current1RMChart.destroy(); window.current1RMChart = null; }

        if (statusDiv) {
            statusDiv.textContent = `No 1RM data yet for ${exerciseName}. Complete some workouts to see progress!`;
            statusDiv.style.display = 'flex'; // Show status
            canvas.style.display = 'none';   // Hide canvas
        } else { // Fallback to canvas text if statusDiv is not there
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText(`No 1RM data available for ${exerciseName}.`, canvas.width / 2, canvas.height / 2);
        }
        return;
    }

    // If we have data, ensure canvas is visible and status is hidden
    if (statusDiv) statusDiv.style.display = 'none';
    canvas.style.display = 'block';

    // Data mapping: adapt to actual API response structure. Assuming { date: 'YYYY-MM-DD', value: XXX } or { date: 'YYYY-MM-DD', estimated_1rm: XXX }
    const labels = exerciseData.map(dp => dp.date);
    const dataPoints = exerciseData.map(dp => dp.estimated_1rm !== undefined ? dp.estimated_1rm : dp.value);


    // Trendline calculation
    let trendlineData = [];
    if (dataPoints.length >= 2) {
        // Pass the correct structure to calculateTrendline, it expects {date, estimated_1rm}
        const dataForTrendline = exerciseData.map(dp => ({
            date: dp.date,
            estimated_1rm: dp.estimated_1rm !== undefined ? dp.estimated_1rm : dp.value
        }));
        trendlineData = calculateTrendline(dataForTrendline);
    }

    if (window.current1RMChart) { window.current1RMChart.destroy(); }
    try {
        const datasets = [{
            label: `${exerciseName} e1RM (kg)`,
            data: dataPoints,
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            tension: 0.1,
            fill: true
        }];

        if (trendlineData.length > 0) {
            datasets.push({
                label: 'Trendline',
                data: trendlineData,
                borderColor: 'rgb(255, 99, 132)',
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                tension: 0.1,
                fill: false,
                borderDash: [5, 5] // Dashed line for trendline
            });
        }

        window.current1RMChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: { // Options remain largely the same as they are styling/behavior related
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'month', tooltipFormat: 'MMM dd, yyyy', displayFormats: { month: 'MMM yyyy'}},
                        title: {
                            display: true,
                            text: 'Date',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d'
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef' // Lighter grid lines
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Estimated 1RM (kg)',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        beginAtZero: false,
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d',
                            padding: 5
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef' // Lighter grid lines
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: `1RM Evolution for ${exerciseName}`,
                        font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 16, weight: '600' },
                        color: '#343a40',
                        padding: { top: 10, bottom: 20 }
                    },
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#495057',
                            boxWidth: 20,
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        titleColor: '#343a40',
                        bodyColor: '#495057',
                        borderColor: '#dee2e6',
                        borderWidth: 1,
                        titleFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', weight: '600' },
                        bodyFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' },
                        padding: 10,
                        cornerRadius: 4,
                        displayColors: true
                    }
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

    // Populate the exercise selector using the global 'allExercises' list
    if (allExercises && allExercises.length > 0) {
        selector.innerHTML = ''; // Clear previous options
        allExercises.forEach(exercise => {
            const option = document.createElement('option');
            option.value = exercise.id;
            option.textContent = exercise.name;
            selector.appendChild(option);
        });

        // Add event listener to fetch data when selection changes
        selector.addEventListener('change', (event) => {
            fetchAndRender1RMEvolutionData(event.target.value);
        });

        // Initial load for the first exercise in the list
        if (allExercises.length > 0) {
            const initialExerciseId = allExercises[0].id;
            selector.value = initialExerciseId;
            fetchAndRender1RMEvolutionData(initialExerciseId);
        } else {
             // Handle case where allExercises is empty (though unlikely if fetched in DOMContentLoaded)
            const statusDiv = document.getElementById('chart1RMStatus');
            const canvas = document.getElementById('1rmEvolutionChart');
            if (statusDiv) {
                statusDiv.textContent = "Exercise list not available.";
                statusDiv.style.display = 'flex';
                if(canvas) canvas.style.display = 'none';
            }
            console.warn("No exercises available to populate 1RM chart selector.");
        }
    } else {
        const statusDiv = document.getElementById('chart1RMStatus');
        const canvas = document.getElementById('1rmEvolutionChart');
        if (statusDiv) {
            statusDiv.textContent = "Exercises not loaded. Cannot display 1RM chart.";
            statusDiv.style.display = 'flex';
            if(canvas) canvas.style.display = 'none';
        }
        console.error("allExercises is empty, cannot initialize 1RM Evolution Chart selector.");
    }
}

async function fetchAndRender1RMEvolutionData(exerciseId) {
    const statusDiv = document.getElementById('chart1RMStatus');
    const canvas = document.getElementById('1rmEvolutionChart');
    const ctx = canvas.getContext('2d');

    if (statusDiv) {
        statusDiv.textContent = 'Loading 1RM data...';
        statusDiv.style.display = 'flex';
        canvas.style.display = 'none';
        if (window.current1RMChart) { // Destroy previous chart instance if exists
            window.current1RMChart.destroy();
            window.current1RMChart = null;
        }
    } else { // Fallback to canvas text
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
        ctx.fillText("Loading 1RM data...", canvas.width / 2, canvas.height / 2);
    }

    const userId = getUserId(); // Needed if your API is user-specific and not just exerciseId
    if (!userId && exerciseId) { // Assuming exerciseId implies a user context or public exercise data
        // If userId is strictly required by the new endpoint, handle this.
        // For now, proceeding as if endpoint only needs exerciseId or auth token handles user.
    }

    try {
        // const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/1rm-evolution`, { headers: getAuthHeaders() }); // OLD
        const response = await fetch(`${API_BASE_URL}/api/v1/analytics/progress/${exerciseId}`, { headers: getAuthHeaders() });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        const progressData = await response.json();
        // API is expected to return an array of { date: 'YYYY-MM-DD', value: XXX } or { date: 'YYYY-MM-DD', estimated_1rm: XXX }
        // The problem description implies the key is `estimated_1rm`. If it's `value`, `render1RMEvolutionChart` will adapt.
        currentSelectedExercise1RMData = progressData.data || progressData; // Adapt based on actual API response structure (e.g. if data is nested)

        if (!currentSelectedExercise1RMData || currentSelectedExercise1RMData.length === 0) {
             // Message handled by render1RMEvolutionChart for this specific case
            render1RMEvolutionChart(exerciseId, []);
        } else {
            render1RMEvolutionChart(exerciseId, currentSelectedExercise1RMData);
        }

    } catch (error) {
        console.error(`Failed to fetch 1RM data for exercise ${exerciseId}:`, error);
        if (statusDiv) {
            statusDiv.textContent = `Failed to load progress data: ${error.message}. Please try again.`;
            statusDiv.style.display = 'flex';
            canvas.style.display = 'none';
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText("Failed to load data.", canvas.width / 2, canvas.height / 2);
        }
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

    // Adapt to new API structure: week_start_date, muscle_group, total_volume
    // Sort data by week to ensure labels are chronological
    apiData.sort((a, b) => new Date(a.week_start_date) - new Date(b.week_start_date));

    const weekLabels = [...new Set(apiData.map(item => item.week_start_date))];
    const muscleGroups = [...new Set(apiData.map(item => item.muscle_group))];

    const datasets = muscleGroups.map(mg => {
        const dataForMuscleGroup = weekLabels.map(week => {
            const weekData = apiData.find(item => item.week_start_date === week && item.muscle_group === mg);
            return weekData ? weekData.total_volume : 0;
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

function renderVolumeDistributionChart(processedChartData, annotationCfg) {
    const canvas = document.getElementById('volumeDistributionChart');
    if (!canvas) { console.error('volumeDistributionChart canvas element not found!'); return; }
    const ctx = canvas.getContext('2d');
    const statusDiv = document.getElementById('chartVolumeStatus');

    if (window.currentVolumeChart) {
        window.currentVolumeChart.destroy();
        window.currentVolumeChart = null;
    }

    // Ensure canvas is visible and status is hidden when rendering actual chart
    if (statusDiv) statusDiv.style.display = 'none';
    canvas.style.display = 'block';

    window.currentVolumeChart = new Chart(ctx, {
        type: 'bar',
        data: processedChartData,
        options: { // Options remain largely the same
                responsive: true,
                maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: 'Weekly Volume by Muscle Group',
                    font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 16, weight: '600' },
                    color: '#343a40',
                    padding: { top: 10, bottom: 20 }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#ffffff',
                    titleColor: '#343a40',
                    bodyColor: '#495057',
                    borderColor: '#dee2e6',
                    borderWidth: 1,
                    titleFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', weight: '600' },
                    bodyFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' },
                    padding: 10,
                    cornerRadius: 4,
                    displayColors: true
                },
                legend: {
                    position: 'top',
                    labels: {
                        font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                        color: '#495057',
                        boxWidth: 20,
                        padding: 15
                    }
                },
                annotation: { // Annotation plugin configuration
                    annotations: annotationCfg // Pass the generated annotations
                }
            },
            scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Week (Start Date)',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        stacked: true, // Enable stacking
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d'
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Total Volume (Sets x Reps x Weight)', // Clarified Y-axis title
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        beginAtZero: true,
                        stacked: true, // Enable stacking
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d',
                            padding: 5
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef'
                        }
                    }
                }
            }
        });
        console.log('Volume Distribution Chart rendered successfully with new data.');
    // Error handling specific to chart rendering itself, if any, can be added here.
}

async function fetchAndRenderVolumeData() {
    const statusDiv = document.getElementById('chartVolumeStatus');
    const canvas = document.getElementById('volumeDistributionChart');

    if (!canvas) { // Should not happen if HTML is correct
        console.error("volumeDistributionChart canvas element not found!");
        if(statusDiv) statusDiv.textContent = "Chart canvas not found.";
        return;
    }
    const ctx = canvas.getContext('2d');

    if (statusDiv) {
        statusDiv.textContent = 'Loading volume data...';
        statusDiv.style.display = 'flex';
        canvas.style.display = 'none';
        if (window.currentVolumeChart) {
            window.currentVolumeChart.destroy();
            window.currentVolumeChart = null;
        }
    } else { // Fallback to canvas text
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
        ctx.fillText("Loading volume data...", canvas.width / 2, canvas.height / 2);
    }

    const userId = getUserId(); // Not strictly needed if API infers user from token
    if (!userId) { // Or if API requires it in URL, adjust fetch URL
        console.warn("User ID not found. Backend might infer from token.");
        // Potentially display message if user must be logged in and ID is missing
    }

    try {
        // const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/volume-heatmap`, { headers: getAuthHeaders() }); // OLD endpoint
        const response = await fetch(`${API_BASE_URL}/api/v1/analytics/volume`, { headers: getAuthHeaders() });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        const apiResult = await response.json();
        const volumeData = apiResult.data || apiResult; // Assuming data is in a 'data' property or is the direct response

        if (!volumeData || volumeData.length === 0) {
            if (statusDiv) {
                statusDiv.textContent = "No volume data available yet. Start logging workouts!";
                statusDiv.style.display = 'flex';
                canvas.style.display = 'none';
            } else {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
                ctx.fillText("No volume data available yet.", canvas.width / 2, canvas.height / 2);
            }
            return;
        }

        const processedData = processWeeklyVolumeData(volumeData);
        // For MEV/MAV/MRV, assuming they are not yet part of the new API response.
        // generateVolumeAnnotations will use its internal mock data.
        // When API provides this, pass the relevant part of 'volumeData' or 'apiResult' to generateVolumeAnnotations.
        console.info("Weekly Volume Chart: MEV/MAV/MRV lines are illustrative and use mock data. Update when API provides this.");
        const annotations = generateVolumeAnnotations(volumeData, processedData.labels); // Pass raw API data and labels for context

        renderVolumeDistributionChart(processedData, annotations);

    } catch (error) {
        console.error("Failed to fetch or render Weekly Volume chart:", error);
        if (statusDiv) {
            statusDiv.textContent = `Failed to load volume data: ${error.message}. Please try again.`;
            statusDiv.style.display = 'flex';
            canvas.style.display = 'none';
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText("Failed to load volume data.", canvas.width / 2, canvas.height / 2);
        }
    }
}

async function initVolumeDistributionChart() {
    console.log('Initializing Volume Distribution Chart with live data...');
    await fetchAndRenderVolumeData();
}


// Mock MEV/MAV/MRV data - REPLACE with backend data when available
const mockVolumeGuidelines = {
    "Legs": { MEV: 1000, MAV_min: 1500, MAV_max: 2500, MRV: 3000 },
    "Chest": { MEV: 800, MAV_min: 1200, MAV_max: 2000, MRV: 2500 },
    "Back": { MEV: 1200, MAV_min: 1800, MAV_max: 3000, MRV: 3500 },
    "Shoulders": { MEV: 600, MAV_min: 900, MAV_max: 1500, MRV: 2000 },
    "Biceps": { MEV: 400, MAV_min: 600, MAV_max: 1000, MRV: 1200 },
    "Triceps": { MEV: 500, MAV_min: 750, MAV_max: 1250, MRV: 1500 },
    "Core": { MEV: 300, MAV_min: 500, MAV_max: 800, MRV: 1000 },
    "Other": { MEV: 200, MAV_min: 300, MAV_max: 500, MRV: 700 }
};

function generateVolumeAnnotations(heatmapData, weekLabels) {
    if (!window.ChartAnnotation) return {}; // Plugin not loaded

    const annotations = {};
    let annotationIndex = 0;

    // For simplicity, these lines will span across all weeks.
    // A more complex implementation might have different MEV/MAV/MRV per week or per muscle group.
    // This example uses a single guideline for each muscle group across all time.
    // To make it per muscle group, we would need to adjust yMin/yMax based on the bar segment.
    // However, the annotation plugin typically draws lines across the entire chart width at a given y-value.
    // So, we'll create general MEV/MAV/MRV lines. Users can compare their *total* weekly volume for a muscle group.

    // This example assumes you want general lines for overall volume levels rather than per-muscle group lines
    // on a stacked chart, which can become very cluttered.
    // If per-muscle group lines are needed, a different chart type or approach might be better.
    // For now, let's add example lines for overall total volume ranges.
    // These are illustrative and would need to be tied to actual user data or more specific logic.

    const generalGuidelines = {
        "Min Recommended Volume (Illustrative)": { value: 5000, color: 'rgba(0, 255, 0, 0.5)', label: "Min Rec. Volume" },
        "Max Productive Volume (Illustrative)": { value: 15000, color: 'rgba(255, 0, 0, 0.5)', label: "Max Prod. Volume" }
    };
    // Note: The above are placeholders. Real MEV/MAV/MRV are per muscle group, per week.
    // Drawing these accurately on a stacked bar chart where Y axis is total volume for *all* muscle groups
    // is complex. The current `heatmapData` is structured for volume per muscle group.
    // The most straightforward way with annotations on a stacked chart is to have lines representing
    // *total* volume thresholds if such general guidelines exist, or to pick one muscle group to highlight.

    // For this example, we'll stick to the simpler interpretation of general lines.
    // A more advanced version would require significant data restructuring or a different chart representation
    // to show MEV/MAV/MRV per muscle group on the same chart.

    Object.entries(generalGuidelines).forEach(([key, config]) => {
        annotations[`line${annotationIndex++}`] = {
            type: 'line',
            yMin: config.value,
            yMax: config.value,
            borderColor: config.color,
            borderWidth: 2,
            borderDash: [6, 6],
            label: {
                content: config.label,
                enabled: true,
                position: 'end',
                backgroundColor: 'rgba(0,0,0,0.7)',
                font: { style: 'italic', size: 10, family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' },
                color: 'white',
                padding: { x: 6, y:3 },
                cornerRadius: 3
            }
        };
    });

    // IMPORTANT: The above is a simplified example for overall volume.
    // To show MEV/MAV/MRV per muscle group on this stacked chart, one would typically:
    // 1. NOT use stacked bars, but grouped bars (one group per week, bars within group are muscle groups).
    // 2. Or, have separate charts per muscle group.
    // 3. Or, if backend can provide cumulative MEV/MAV/MRV thresholds (e.g. MEV for Legs + MEV for Chest),
    //    then lines could represent those cumulative thresholds.
    // Given the current data structure (volume per muscle group, stacked), directly plotting individual
    // MEV/MAV/MRV lines for each muscle group on the stack is not straightforward with chartjs-plugin-annotation
    // as lines span the whole chart width.

    console.warn("MEV/MAV/MRV annotation lines are illustrative general guidelines due to stacked chart complexity. For per-muscle-group guidelines, data structure or chart type might need adjustment or backend should provide specific values for annotation that align with the stacked total.");
    return annotations;
}

// --- MTI Trends Chart (New) ---

// window.currentMTIChart = null; // Already defined in global section

function renderMTITrendsChart(mtiData) {
    const canvas = document.getElementById('mtiTrendsChart');
    const statusDiv = document.getElementById('chartMTIStatus');
    if (!canvas) { console.error('mtiTrendsChart canvas element not found!'); return; }
    const ctx = canvas.getContext('2d');

    // This specific message is for when API call was successful but returned no records
    if (!mtiData || mtiData.length === 0) {
        console.warn('No MTI data points found after successful fetch.');
        if (window.currentMTIChart) { window.currentMTIChart.destroy(); window.currentMTIChart = null; }

        if (statusDiv) {
            statusDiv.textContent = 'No MTI data available yet. Keep up the good work!';
            statusDiv.style.display = 'flex'; // Show status
            canvas.style.display = 'none';   // Hide canvas
        } else { // Fallback to canvas text
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText("No MTI data available.", canvas.width / 2, canvas.height / 2);
        }
        return;
    }

    // If we have data, ensure canvas is visible and status is hidden
    if (statusDiv) statusDiv.style.display = 'none';
    canvas.style.display = 'block';

    const labels = mtiData.map(dp => dp.date);
    const dataPoints = mtiData.map(dp => dp.mti_score); // Assuming API returns 'mti_score'

    if (window.currentMTIChart) { window.currentMTIChart.destroy(); window.currentMTIChart = null;}

    try {
        window.currentMTIChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'MTI Score',
                    data: dataPoints,
                    borderColor: 'rgb(153, 102, 255)',
                    backgroundColor: 'rgba(153, 102, 255, 0.3)',
                    tension: 0.2,
                    fill: true
                }]
            },
            options: { // Options remain largely the same
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'time',
                        time: { unit: 'week', tooltipFormat: 'MMM dd, yyyy', displayFormats: { week: 'MMM dd' } },
                        title: {
                            display: true,
                            text: 'Date',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d'
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'MTI Score',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' },
                            color: '#495057'
                        },
                        beginAtZero: false, // Or true if MTI score starts from 0
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#6c757d',
                            padding: 5
                        },
                        grid: {
                            borderColor: '#dee2e6',
                            color: '#e9ecef'
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Mechanical Tension Index (MTI) Trends',
                        font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 16, weight: '600' },
                        color: '#343a40',
                        padding: { top: 10, bottom: 20 }
                    },
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 },
                            color: '#495057',
                            boxWidth: 20,
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        titleColor: '#343a40',
                        bodyColor: '#495057',
                        borderColor: '#dee2e6',
                        borderWidth: 1,
                        titleFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', weight: '600' },
                        bodyFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' },
                        padding: 10,
                        cornerRadius: 4,
                        displayColors: true
                    }
                }
            }
        });
        console.log('MTI Trends Chart rendered successfully with mock data.');
    } catch (error) {
        console.error('Error rendering MTI Trends Chart:', error);
        const ctxElementOnError = document.getElementById('mtiTrendsChart');
        if (ctxElementOnError) {
            const ctxError = ctxElementOnError.getContext('2d');
            ctxError.clearRect(0, 0, ctxError.canvas.width, ctxError.canvas.height);
            ctxError.font = "16px Arial"; ctxError.textAlign = "center";
            ctxError.fillText("Could not render MTI chart.", ctxError.canvas.width / 2, ctxError.canvas.height / 2);
        }
    }
}

async function initMTITrendsChart() {
    console.log('Initializing MTI Trends Chart...');
    const userId = getUserId();
    // if (!userId) {
    //     console.warn("User ID not found. Cannot load MTI trends data.");
    //     renderMTITrendsChart([]); // Render empty state
    //     return;
    // }

    // TODO: Replace with actual API call
    // try {
    //     const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/mti-trends`, { headers: getAuthHeaders() });
    //     if (!response.ok) {
    //         throw new Error(`HTTP error! status: ${response.status}`);
    //     }
    //     const mtiData = await response.json();
    //     renderMTITrendsChart(mtiData.data || []); // Assuming data is in a 'data' property
    // } catch (error) {
    //     console.error("Failed to fetch MTI trends data:", error);
    //     renderMTITrendsChart([]); // Render empty state on error
    // }

    // Using mock data for now:
    console.log("Using mock data for MTI Trends Chart.");
    renderMTITrendsChart(mockMTITrendsData);
}

// --- Strength Gains Summary (New) ---

// Mock data for Strength Gains has been removed as it will be fetched from API.
// Expected API structure: Array of objects like:
// { exerciseName: string, improvementPercentage: number, period: string, e1RMHistory?: {previous: number, current: number} }

function renderStrengthGainsCards(strengthGainsData) {
    const container = document.getElementById('strength-gains-cards-container');
    const statusDiv = document.getElementById('strengthGainsStatus');

    if (!container) {
        console.error('strength-gains-cards-container element not found!');
        if (statusDiv) statusDiv.textContent = 'Display container not found.';
        return;
    }
    container.innerHTML = ''; // Clear previous cards

    // This message is for when API call was successful but returned no records
    if (!strengthGainsData || strengthGainsData.length === 0) {
        if (statusDiv) {
            statusDiv.textContent = 'No strength gains data to display yet. Keep training!';
            statusDiv.style.display = 'flex'; // Show status
        } else { // Fallback if statusDiv is missing
            container.innerHTML = '<p>No strength gains data to display yet.</p>';
        }
        return;
    }

    // If we have data, ensure status is hidden
    if (statusDiv) statusDiv.style.display = 'none';

    strengthGainsData.forEach(gain => {
        const card = document.createElement('div');
        card.classList.add('info-card', 'strength-gain-card');

        const exerciseNameEl = document.createElement('h4');
        exerciseNameEl.textContent = gain.exerciseName;

        const percentageGainEl = document.createElement('p');
        percentageGainEl.classList.add('percentage-gain');
        const sign = gain.improvementPercentage >= 0 ? '+' : '';
        percentageGainEl.textContent = `${sign}${gain.improvementPercentage.toFixed(1)}%`;
        if (gain.improvementPercentage < 0) {
            percentageGainEl.classList.add('negative');
        }

        const periodEl = document.createElement('p');
        periodEl.classList.add('period');
        periodEl.textContent = gain.period;

        card.appendChild(exerciseNameEl);
        card.appendChild(percentageGainEl);
        card.appendChild(periodEl);

        // Optional: Add e1RM history if available
        if (gain.e1RMHistory && gain.e1RMHistory.previous !== undefined && gain.e1RMHistory.current !== undefined) {
            const historyEl = document.createElement('p');
            historyEl.classList.add('e1rm-history');
            historyEl.style.fontSize = '0.8em';
            historyEl.style.color = '#888'; // Consider moving to CSS
            historyEl.textContent = `(e1RM: ${gain.e1RMHistory.previous}kg → ${gain.e1RMHistory.current}kg)`;
            card.appendChild(historyEl);
        }

        container.appendChild(card);
    });
}

async function initStrengthGainsSummary() {
    console.log('Initializing Strength Gains Summary...');
    const userId = getUserId();
    // if (!userId) {
    //     console.warn("User ID not found. Cannot load strength gains data.");
    //     renderStrengthGainsCards([]); // Render empty state
    //     return;
    // }

    // TODO: Replace with actual API call
    // try {
    //     const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/analytics/strength-gains`, { headers: getAuthHeaders() });
    //     if (!response.ok) {
    //         throw new Error(`HTTP error! status: ${response.status}`);
    //     }
    //     const gainsData = await response.json();
    //     renderStrengthGainsCards(gainsData.data || []); // Assuming data is in a 'data' property
    // } catch (error) {
    //     console.error("Failed to fetch strength gains data:", error);
    //     renderStrengthGainsCards([]); // Render empty state on error
    // }

    // Using mock data for now:
    console.log("Using mock data for Strength Gains Summary.");
    renderStrengthGainsCards(mockStrengthGainsData);
}

// --- Recovery Patterns Heatmap (New) ---

// Mock data for Recovery Patterns has been removed.
// API is expected to return an array for a given exercise, e.g.:
// [{ day_of_week_numeric: 1, rest_days_prior: 2, performance_metric: 8.5, session_count: 10 }, ...]

const dayOfWeekLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
// restDaysLabels will be generated dynamically based on fetched data.

function processRecoveryDataForMatrix(apiData) {
    if (!apiData || apiData.length === 0) {
        return [];
    }
    // Assuming apiData is an array of objects like:
    // { day_of_week_numeric: 1, rest_days_prior: 2, performance_metric: 8.5, session_count: 10 }
    return apiData.map(item => ({
        x: dayOfWeekLabels[item.day_of_week_numeric], // Ensure day_of_week_numeric is 0-6
        y: item.rest_days_prior,
        v: item.performance_metric, // This is the value for coloring
        count: item.session_count
    }));
}

function getPerformanceColor(value, minValue = 1, maxValue = 10) { // Assuming performance_metric is 1-10
    // Ensure value is within min/max for ratio calculation
    if (value === null || value === undefined) return 'rgba(230, 230, 230, 0.5)'; // Grey for undefined/null data
    // Ensure value is within min/max for ratio calculation
    const clampedValue = Math.max(minValue, Math.min(value, maxValue));
    const ratio = (maxValue - minValue === 0) ? 0.5 : (clampedValue - minValue) / (maxValue - minValue);


    // Simplified Green (high performance) to Red (low performance)
    // Green: (0, 255, 0), Yellow: (255, 255, 0), Red: (255, 0, 0)
    let r, g;
    if (ratio < 0.5) { // Red to Yellow
        r = 255;
        g = Math.round(255 * (ratio * 2));
    } else { // Yellow to Green
        r = Math.round(255 * ((1 - ratio) * 2));
        g = 255;
    }
    return `rgba(${r}, ${g}, 0, 0.75)`; // Opacity 0.75
}

function renderRecoveryPatternsHeatmap(exerciseName, processedMatrixData) {
    const canvas = document.getElementById('recoveryPatternsHeatmap');
    const statusDiv = document.getElementById('chartRecoveryHeatmapStatus');
    if (!canvas) { console.error('recoveryPatternsHeatmap canvas element not found!'); return; }
    const ctx = canvas.getContext('2d');

    if (!processedMatrixData || processedMatrixData.length === 0) {
        console.warn(`No processed data to render heatmap for ${exerciseName}.`);
        if (statusDiv) {
            statusDiv.textContent = `No recovery pattern data available for ${exerciseName}.`;
            statusDiv.style.display = 'flex';
            canvas.style.display = 'none';
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText(`No data for ${exerciseName}.`, canvas.width / 2, canvas.height / 2);
        }
        if (window.currentRecoveryHeatmap) { window.currentRecoveryHeatmap.destroy(); window.currentRecoveryHeatmap = null; }
        return;
    }

    if (statusDiv) statusDiv.style.display = 'none';
    canvas.style.display = 'block';

    let currentMaxRestDays = 0;
    if (processedMatrixData && processedMatrixData.length > 0) {
        currentMaxRestDays = processedMatrixData.reduce((max, item) => Math.max(max, item.y), 0);
    }
    const currentYLabels = Array.from({ length: currentMaxRestDays + 1 }, (_, i) => i);

    if (window.currentRecoveryHeatmap) { window.currentRecoveryHeatmap.destroy(); window.currentRecoveryHeatmap = null; }

    try {
        window.currentRecoveryHeatmap = new Chart(ctx, {
            type: 'matrix',
            data: {
                datasets: [{
                    label: `Performance Score (Exercise: ${exerciseName})`,
                    data: processedMatrixData,
                    backgroundColor: (c) => {
                        const val = c.dataset.data[c.dataIndex]?.v;
                        // Dynamically determine min/max from the dataset for more accurate coloring
                        const allValues = c.dataset.data.map(d => d.v).filter(v => v !== null && v !== undefined);
                        const minValue = Math.min(...allValues);
                        const maxValue = Math.max(...allValues);
                        return getPerformanceColor(val, minValue, maxValue);
                    },
                    borderColor: 'rgba(180, 180, 180, 0.7)',
                    borderWidth: 1,
                    width: (c) => (c.chart.chartArea.width / dayOfWeekLabels.length) * 0.92, // dayOfWeekLabels is global
                    height: (c) => (c.chart.chartArea.height / currentYLabels.length) * 0.92,
                }]
            },
            options: { // Options remain largely the same
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        type: 'category',
                        labels: dayOfWeekLabels,
                        title: {
                            display: true, text: 'Day of Week of Session',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' }, color: '#495057'
                        },
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 }, color: '#6c757d',
                        },
                        grid: { display: false }
                    },
                    y: {
                        type: 'category',
                        labels: currentYLabels,
                        offset: true,
                        title: {
                            display: true, text: 'Rest Days Prior to Session',
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 14, weight: '500' }, color: '#495057'
                        },
                        ticks: {
                            font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 12 }, color: '#6c757d',
                        },
                        grid: { display: false }
                    }
                },
                plugins: {
                    title: {
                        display: true, text: `Recovery Patterns: Performance by Rest Days (${exerciseName})`,
                        font: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', size: 16, weight: '600' }, color: '#343a40',
                        padding: { top: 10, bottom: 20 }
                    },
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#ffffff',
                        titleColor: '#343a40', bodyColor: '#495057', borderColor: '#dee2e6', borderWidth: 1,
                        titleFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif', weight: '600' },
                        bodyFont: { family: '"Segoe UI", Roboto, Helvetica, Arial, sans-serif' },
                        padding: 10, cornerRadius: 4, displayColors: false,
                        callbacks: {
                            title: function(tooltipItems) {
                                const item = tooltipItems[0].raw;
                                return `Day: ${item.x}, Rest: ${item.y} days`;
                            },
                            label: function(tooltipItem) {
                                const item = tooltipItem.raw;
                                let label = `Avg. Performance: ${item.v ? item.v.toFixed(1) : 'N/A'}`; // Assuming v is performance_metric
                                if (item.count) {
                                    label += ` (${item.count} sessions)`;
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
        console.log(`Recovery Patterns Heatmap for ${exerciseName} rendered successfully with live data.`);
    } catch (error) {
        console.error(`Error rendering Recovery Patterns Heatmap for ${exerciseName}:`, error);
        if (statusDiv && statusDiv.style.display === 'none') {
            statusDiv.textContent = 'Error rendering Recovery Heatmap.';
            statusDiv.style.display = 'flex';
            canvas.style.display = 'none';
        } else if (!statusDiv) {
            const ctxError = canvas.getContext('2d');
            ctxError.clearRect(0, 0, ctxError.canvas.width, ctxError.canvas.height);
            ctxError.font = "16px Segoe UI"; ctxError.textAlign = "center";
            ctxError.fillText("Could not render Recovery Heatmap.", ctxError.canvas.width / 2, ctxError.canvas.height / 2);
        }
    }
}

async function fetchAndRenderRecoveryHeatmapData(exerciseId, exerciseName) {
    const statusDiv = document.getElementById('chartRecoveryHeatmapStatus');
    const canvas = document.getElementById('recoveryPatternsHeatmap');
    if (!canvas) { console.error("recoveryPatternsHeatmap canvas element not found!"); return; }
    const ctx = canvas.getContext('2d');

    if (statusDiv) {
        statusDiv.textContent = `Loading recovery patterns for ${exerciseName}...`;
        statusDiv.style.display = 'flex';
        canvas.style.display = 'none';
        if (window.currentRecoveryHeatmap) {
            window.currentRecoveryHeatmap.destroy();
            window.currentRecoveryHeatmap = null;
        }
    } else {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
        ctx.fillText("Loading recovery patterns...", canvas.width / 2, canvas.height / 2);
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/analytics/recovery-patterns/${exerciseId}`, { headers: getAuthHeaders() });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        const apiResult = await response.json();
        const recoveryData = apiResult.data || apiResult; // Assuming data is in 'data' or is the direct response

        if (!recoveryData || recoveryData.length === 0) {
            renderRecoveryPatternsHeatmap(exerciseName, []); // Let render function handle empty message
        } else {
            const processedData = processRecoveryDataForMatrix(recoveryData);
            renderRecoveryPatternsHeatmap(exerciseName, processedData);
        }

    } catch (error) {
        console.error(`Failed to fetch recovery patterns for ${exerciseName} (ID: ${exerciseId}):`, error);
        if (statusDiv) {
            statusDiv.textContent = `Failed to load recovery data for ${exerciseName}: ${error.message}.`;
            statusDiv.style.display = 'flex';
            canvas.style.display = 'none';
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.font = "16px Segoe UI"; ctx.textAlign = "center";
            ctx.fillText("Failed to load recovery data.", canvas.width / 2, canvas.height / 2);
        }
    }
}

async function initRecoveryPatternsHeatmap() {
    console.log('Initializing Recovery Patterns Heatmap with live data...');
    const selector = document.getElementById('exerciseSelectorRecovery');
    if (!selector) { console.error('exerciseSelectorRecovery element not found!'); return; }

    if (allExercises && allExercises.length > 0) {
        selector.innerHTML = ''; // Clear previous options
        allExercises.forEach(exercise => {
            const option = document.createElement('option');
            option.value = exercise.id;
            option.textContent = exercise.name;
            selector.appendChild(option);
        });

        const initialExerciseName = allExercises[0].name;
        selector.value = allExercises[0].id;
        renderRecoveryPatternsHeatmap(initialExerciseName);

        selector.addEventListener('change', (event) => {
            const selectedExercise = allExercises.find(ex => ex.id === event.target.value);
            renderRecoveryPatternsHeatmap(selectedExercise ? selectedExercise.name : "Selected Exercise");
        });
    } else {
        console.warn("Exercise list for selector not available. Using default for Recovery Heatmap.");
        // Use the exerciseName from mock data if no exercises in selector
        renderRecoveryPatternsHeatmap(mockRecoveryPatternsData.exerciseName || "Default Exercise");
        selector.innerHTML = '<option value="">No exercises loaded</option>';
    }
    // TODO: API call logic here
}

// --- Current Mesocycle Phase Indicator (New) ---

// Mock data for Mesocycle Indicator has been removed.
// Expected API structure from /api/v1/mesocycles/current:
// { current_phase_name: "Intensification", current_week_in_phase: 2, total_weeks_in_phase: 4,
//   phase_order: ["Accumulation", "Intensification", "Realization", "Deload"],
//   current_mesocycle_week: 6, total_mesocycle_weeks: 12 }

function renderMesocycleIndicator(mesocycleData) { // mesocycleData expected to be camelCase here
    const container = document.getElementById('mesocycle-indicator-container');
    const statusDiv = document.getElementById('mesocycleIndicatorStatus');

    if (!container) {
        console.error('mesocycle-indicator-container element not found!');
        if (statusDiv) statusDiv.textContent = 'Display container not found for mesocycle data.';
        return;
    }
    container.innerHTML = ''; // Clear previous content

    // This message is for when API call was successful but returned no active mesocycle
    if (!mesocycleData || !mesocycleData.currentPhaseName) { // Check for a key field
        if (statusDiv) {
            statusDiv.textContent = 'No active mesocycle found or data is incomplete.';
            statusDiv.style.display = 'flex'; // Show status
        } else { // Fallback if statusDiv is missing
            container.innerHTML = '<p>No active mesocycle found.</p>';
        }
        return;
    }

    // If we have data, ensure status is hidden
    if (statusDiv) statusDiv.style.display = 'none';

    // Phase Name
    const phaseNameEl = document.createElement('h3');
    phaseNameEl.classList.add('phase-name');
    phaseNameEl.textContent = mesocycleData.currentPhaseName || 'N/A';
    container.appendChild(phaseNameEl);

    // Week Progress Text
    const weekProgressEl = document.createElement('p');
    weekProgressEl.classList.add('phase-week-progress');
    weekProgressEl.textContent = `Week ${mesocycleData.currentWeekInPhase} of ${mesocycleData.totalWeeksInPhase}`;
    container.appendChild(weekProgressEl);

    // Progress Bar for Phase
    const progressBarContainer = document.createElement('div');
    progressBarContainer.classList.add('progress-bar-container');
    const progressBarFill = document.createElement('div');
    progressBarFill.classList.add('progress-bar-fill');

    // Ensure totalWeeksInPhase is positive to avoid division by zero or negative percentages
    const totalWeeks = mesocycleData.totalWeeksInPhase > 0 ? mesocycleData.totalWeeksInPhase : 1;
    const currentWeek = mesocycleData.currentWeekInPhase >= 0 ? mesocycleData.currentWeekInPhase : 0;
    const phaseProgressPercent = (currentWeek / totalWeeks) * 100;

    progressBarFill.style.width = `${Math.min(phaseProgressPercent, 100)}%`;
    progressBarContainer.appendChild(progressBarFill);
    container.appendChild(progressBarContainer);

    if (mesocycleData.phaseOrder && mesocycleData.phaseOrder.length > 0) {
        const phaseListEl = document.createElement('ul');
        phaseListEl.classList.add('phase-list');
        mesocycleData.phaseOrder.forEach(phase => {
            const listItem = document.createElement('li');
            listItem.classList.add('phase-list-item');
            if (phase === mesocycleData.currentPhaseName) {
                listItem.classList.add('current');
            }
            listItem.textContent = phase;
            phaseListEl.appendChild(listItem);
        });
        container.appendChild(phaseListEl);
    }

    const overviewText = document.createElement('p');
    overviewText.classList.add('mesocycle-overview');
    overviewText.textContent = `Overall: Week ${mesocycleData.currentMesocycleWeek} of ${mesocycleData.totalMesocycleWeeks} in the mesocycle.`;
    container.appendChild(overviewText);
}

async function fetchAndRenderMesocycleData() {
    const statusDiv = document.getElementById('mesocycleIndicatorStatus');
    const container = document.getElementById('mesocycle-indicator-container');

    if (statusDiv) {
        statusDiv.textContent = 'Loading mesocycle data...';
        statusDiv.style.display = 'flex';
    }
    if (container) container.innerHTML = ''; // Clear old content

    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/mesocycles/current`, { headers: getAuthHeaders() });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        const apiResult = await response.json();
        // API is expected to return an object with snake_case keys. Convert to camelCase for renderMesocycleIndicator.
        // Example: { "current_phase_name": "Intensification", ... }
        const mesocycleData = apiResult.data || apiResult;

        if (!mesocycleData || Object.keys(mesocycleData).length === 0) {
            renderMesocycleIndicator(null); // Let render function handle specific empty message
        } else {
            // Convert snake_case to camelCase
            const formattedData = {
                currentPhaseName: mesocycleData.current_phase_name,
                currentWeekInPhase: mesocycleData.current_week_in_phase,
                totalWeeksInPhase: mesocycleData.total_weeks_in_phase,
                phaseOrder: mesocycleData.phase_order,
                currentMesocycleWeek: mesocycleData.current_mesocycle_week,
                totalMesocycleWeeks: mesocycleData.total_mesocycle_weeks
            };
            renderMesocycleIndicator(formattedData);
        }

    } catch (error) {
        console.error("Failed to fetch Mesocycle data:", error);
        if (statusDiv) {
            statusDiv.textContent = `Failed to load mesocycle data: ${error.message}.`;
            statusDiv.style.display = 'flex';
        } else if (container) {
            container.innerHTML = `<p>Failed to load mesocycle data: ${error.message}</p>`;
        }
    }
}

async function initMesocycleIndicator() {
    console.log('Initializing Mesocycle Phase Indicator with live data...');
    await fetchAndRenderMesocycleData();
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

// Helper function to calculate linear regression for trendline
function calculateTrendline(data) {
    const n = data.length;
    if (n < 2) return [];

    // Convert dates to numerical values (e.g., days since first data point)
    const firstDate = new Date(data[0].date).getTime();
    const x = data.map(dp => (new Date(dp.date).getTime() - firstDate) / (1000 * 60 * 60 * 24)); // Days
    const y = data.map(dp => dp.estimated_1rm);

    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    for (let i = 0; i < n; i++) {
        sumX += x[i];
        sumY += y[i];
        sumXY += x[i] * y[i];
        sumXX += x[i] * x[i];
    }

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    return x.map(val => slope * val + intercept);
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
