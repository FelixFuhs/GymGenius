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

    // Trendline calculation
    let trendlineData = [];
    if (dataPoints.length >= 2) {
        trendlineData = calculateTrendline(exerciseData);
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
            options: {
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
                        annotations: generateVolumeAnnotations(heatmapData, processedData.labels)
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
        console.log('Volume Distribution Chart initialized successfully with backend data.');
    } catch (error) {
        console.error('Error initializing Volume Distribution Chart:', error);
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText("Could not load volume data.", ctxElement.width / 2, ctxElement.height / 2);
        alert(`Could not load volume data: ${error.message}`);
    }
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

// Mock data for MTI Trends - Replace with API call when backend endpoint is available
// Expected structure: [{ date: 'YYYY-MM-DD', mti_score: value }, ...]
const mockMTITrendsData = [
    { date: '2023-01-01', mti_score: 1500 }, { date: '2023-01-08', mti_score: 1550 },
    { date: '2023-01-15', mti_score: 1600 }, { date: '2023-01-22', mti_score: 1520 },
    { date: '2023-01-29', mti_score: 1650 }, { date: '2023-02-05', mti_score: 1700 },
    { date: '2023-02-12', mti_score: 1680 }, { date: '2023-02-19', mti_score: 1750 },
    { date: '2023-02-26', mti_score: 1800 }, { date: '2023-03-05', mti_score: 1780 },
    { date: '2023-03-12', mti_score: 1850 }, { date: '2023-03-19', mti_score: 1900 }
];

window.currentMTIChart = null;

function renderMTITrendsChart(mtiData) {
    const ctxElement = document.getElementById('mtiTrendsChart');
    if (!ctxElement) { console.error('mtiTrendsChart canvas element not found!'); return; }
    const ctx = ctxElement.getContext('2d');

    if (!mtiData || mtiData.length === 0) {
        console.warn('No MTI data available to render.');
        if (window.currentMTIChart) { window.currentMTIChart.destroy(); window.currentMTIChart = null; }
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText("No MTI data available.", ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    const labels = mtiData.map(dp => dp.date);
    const dataPoints = mtiData.map(dp => dp.mti_score);

    if (window.currentMTIChart) { window.currentMTIChart.destroy(); }

    try {
        window.currentMTIChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'MTI Score',
                    data: dataPoints,
                    borderColor: 'rgb(153, 102, 255)', // Purple
                    backgroundColor: 'rgba(153, 102, 255, 0.3)', // Lighter purple for area fill
                    tension: 0.2, // Slight curve
                    fill: true // Essential for area chart
                }]
            },
            options: {
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

// Mock data for Strength Gains - Replace with API call when backend endpoint is available
// Expected structure: [{ exerciseName: string, improvementPercentage: number, period: string, e1RMHistory?: {previous: number, current: number} }, ...]
const mockStrengthGainsData = [
    { exerciseName: 'Squat', improvementPercentage: 15.5, period: 'Last 3 Months', e1RMHistory: { previous: 100, current: 115.5 } },
    { exerciseName: 'Bench Press', improvementPercentage: 10.2, period: 'Last 3 Months' },
    { exerciseName: 'Deadlift', improvementPercentage: 8.0, period: 'Last 3 Months' },
    { exerciseName: 'Overhead Press', improvementPercentage: 12.1, period: 'Last 6 Weeks' },
    { exerciseName: 'Overall Strength', improvementPercentage: 12.0, period: 'Last 3 Months' },
    { exerciseName: 'Bicep Curl', improvementPercentage: -2.5, period: 'Last Month' } // Example of a decrease
];

function renderStrengthGainsCards(strengthGainsData) {
    const container = document.getElementById('strength-gains-cards-container');
    if (!container) {
        console.error('strength-gains-cards-container element not found!');
        return;
    }
    container.innerHTML = ''; // Clear previous content

    if (!strengthGainsData || strengthGainsData.length === 0) {
        container.innerHTML = '<p>No strength gains data available at the moment.</p>';
        return;
    }

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
        if (gain.e1RMHistory) {
            const historyEl = document.createElement('p');
            historyEl.classList.add('e1rm-history'); // Add a class for potential styling
            historyEl.style.fontSize = '0.8em'; // Basic styling
            historyEl.style.color = '#888';
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

// Mock data for Recovery Patterns - Replace with API call
const mockRecoveryPatternsData = {
    // Data could be per exercise, this is a simplified global example or for a pre-selected exercise
    exerciseName: 'Squat', // Example, could be dynamic based on selector
    // x: Day of Week (0=Sun, 1=Mon,... 6=Sat), y: Rest Days Prior, v: Performance Score (1-10)
    data: [
        { dayOfWeek: 1, restDays: 1, performanceScore: 7, count: 5 }, // Mon, 1 rest day, score 7, 5 sessions
        { dayOfWeek: 1, restDays: 2, performanceScore: 8, count: 3 },
        { dayOfWeek: 1, restDays: 3, performanceScore: 7, count: 1 },
        { dayOfWeek: 2, restDays: 1, performanceScore: 6, count: 2 }, // Tue
        { dayOfWeek: 3, restDays: 1, performanceScore: 6, count: 4 }, // Wed
        { dayOfWeek: 3, restDays: 2, performanceScore: 9, count: 6 },
        { dayOfWeek: 3, restDays: 3, performanceScore: 8, count: 2 },
        { dayOfWeek: 4, restDays: 1, performanceScore: 5, count: 1 }, // Thu
        { dayOfWeek: 5, restDays: 1, performanceScore: 7, count: 2 }, // Fri
        { dayOfWeek: 5, restDays: 2, performanceScore: 8, count: 4 },
        { dayOfWeek: 5, restDays: 4, performanceScore: 9, count: 1 },
        { dayOfWeek: 0, restDays: 1, performanceScore: 7, count: 3 }, // Sun
        { dayOfWeek: 0, restDays: 2, performanceScore: 8, count: 2 },
    ]
};

const dayOfWeekLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
// Determine max rest days from data for Y-axis labels dynamically
// Initialize with a default in case data is empty, though mock data ensures it's not.
let maxRestDays = 0;
if (mockRecoveryPatternsData.data && mockRecoveryPatternsData.data.length > 0) {
    maxRestDays = mockRecoveryPatternsData.data.reduce((max, item) => Math.max(max, item.restDays), 0);
}
const restDaysLabels = Array.from({ length: maxRestDays + 1 }, (_, i) => i); // [0, 1, 2, ..., maxRestDays]


function processRecoveryDataForMatrix(recoveryDataRaw, selectedExerciseName) {
    // This function assumes recoveryDataRaw is an object like mockRecoveryPatternsData
    // and selectedExerciseName is used to pick which part of the data to process if it's structured per exercise.
    // For the current mockRecoveryPatternsData, selectedExerciseName isn't strictly used for filtering
    // as it only contains one exercise's data directly under the 'data' key.
    // If mockRecoveryPatternsData was an array of objects, each for an exercise, filtering would be needed here.
    const exerciseData = recoveryDataRaw.data;

    return exerciseData.map(item => ({
        x: dayOfWeekLabels[item.dayOfWeek],
        y: item.restDays,
        v: item.performanceScore,
        count: item.count
    }));
}

function getPerformanceColor(value, minValue = 1, maxValue = 10) {
    // Ensure value is within min/max for ratio calculation
    const clampedValue = Math.max(minValue, Math.min(value, maxValue));
    const ratio = (clampedValue - minValue) / (maxValue - minValue);

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


function renderRecoveryPatternsHeatmap(exerciseName) {
    const ctxElement = document.getElementById('recoveryPatternsHeatmap');
    if (!ctxElement) { console.error('recoveryPatternsHeatmap canvas element not found!'); return; }
    const ctx = ctxElement.getContext('2d');

    // In a real app, you'd fetch or filter data for the given exerciseName.
    // For now, we use the global mock data and assume it matches the exerciseName or is generic.
    // The 'exerciseName' parameter is used for the chart title.
    const processedData = processRecoveryDataForMatrix(mockRecoveryPatternsData, exerciseName);

    // Dynamically generate Y-axis labels based on the actual max rest days in the *processed* data for the exercise.
    // This ensures labels match the data being displayed if it changes per exercise.
    let currentMaxRestDays = 0;
    if (processedData && processedData.length > 0) {
        currentMaxRestDays = processedData.reduce((max, item) => Math.max(max, item.y), 0);
    }
    const currentYLabels = Array.from({ length: currentMaxRestDays + 1 }, (_, i) => i);


    if (window.currentRecoveryHeatmap) { window.currentRecoveryHeatmap.destroy(); }

    try {
        window.currentRecoveryHeatmap = new Chart(ctx, {
            type: 'matrix',
            data: {
                datasets: [{
                    label: `Performance Score (Exercise: ${exerciseName})`,
                    data: processedData,
                    backgroundColor: (c) => {
                        const val = c.dataset.data[c.dataIndex]?.v;
                        return val !== undefined ? getPerformanceColor(val) : 'rgba(230, 230, 230, 0.5)'; // Grey for undefined
                    },
                    borderColor: 'rgba(180, 180, 180, 0.7)',
                    borderWidth: 1,
                    width: (c) => (c.chart.chartArea.width / dayOfWeekLabels.length) * 0.92,
                    height: (c) => (c.chart.chartArea.height / currentYLabels.length) * 0.92,
                }]
            },
            options: {
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
                                let label = `Avg. Performance: ${item.v}/10`;
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
        console.log(`Recovery Patterns Heatmap for ${exerciseName} rendered successfully.`);
    } catch (error) {
        console.error(`Error rendering Recovery Patterns Heatmap for ${exerciseName}:`, error);
        const ctxError = ctxElement.getContext('2d');
        ctxError.clearRect(0, 0, ctxError.canvas.width, ctxError.canvas.height);
        ctxError.font = "16px Arial"; ctxError.textAlign = "center";
        ctxError.fillText("Could not render Recovery Heatmap.", ctxError.canvas.width / 2, ctxError.canvas.height / 2);
    }
}


async function initRecoveryPatternsHeatmap() {
    console.log('Initializing Recovery Patterns Heatmap...');
    const selector = document.getElementById('exerciseSelectorRecovery');
    if (!selector) { console.error('exerciseSelectorRecovery element not found!'); return; }

    if (allExercises && allExercises.length > 0) {
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

// Mock data for Mesocycle Indicator - Replace with API call
const mockMesocycleData = {
    currentPhaseName: 'Intensification',
    currentWeekInPhase: 2,
    totalWeeksInPhase: 4,
    phaseOrder: ['Accumulation', 'Intensification', 'Realization', 'Deload'],
    currentMesocycleWeek: 6,
    totalMesocycleWeeks: 12
};

function renderMesocycleIndicator(mesocycleData) {
    const container = document.getElementById('mesocycle-indicator-container');
    if (!container) {
        console.error('mesocycle-indicator-container element not found!');
        return;
    }
    container.innerHTML = ''; // Clear previous content

    if (!mesocycleData) {
        container.innerHTML = '<p>Mesocycle data is currently unavailable.</p>';
        return;
    }

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
    const phaseProgressPercent = (mesocycleData.currentWeekInPhase / mesocycleData.totalWeeksInPhase) * 100;
    progressBarFill.style.width = `${Math.min(phaseProgressPercent, 100)}%`;
    // progressBarFill.textContent = `${Math.round(phaseProgressPercent)}%`; // Optional: text inside bar
    progressBarContainer.appendChild(progressBarFill);
    container.appendChild(progressBarContainer);

    // Overall Mesocycle Context (Phase List)
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

    // Overall Mesocycle Week (Optional Text)
    const overviewText = document.createElement('p');
    overviewText.classList.add('mesocycle-overview');
    overviewText.textContent = `Overall: Week ${mesocycleData.currentMesocycleWeek} of ${mesocycleData.totalMesocycleWeeks} in the mesocycle.`;
    container.appendChild(overviewText);
}

async function initMesocycleIndicator() {
    console.log('Initializing Mesocycle Phase Indicator...');
    const userId = getUserId();
    // if (!userId) {
    //     console.warn("User ID not found. Cannot load mesocycle data.");
    //     renderMesocycleIndicator(null);
    //     return;
    // }

    // TODO: Replace with actual API call to /v1/users/{userId}/mesocycle/current
    // try {
    //     const response = await fetch(`${API_BASE_URL}/v1/users/${userId}/mesocycle/current`, { headers: getAuthHeaders() });
    //     if (!response.ok) {
    //         throw new Error(`HTTP error! status: ${response.status}`);
    //     }
    //     const mesoData = await response.json();
    //     renderMesocycleIndicator(mesoData.data || null); // Assuming data is in a 'data' property
    // } catch (error) {
    //     console.error("Failed to fetch mesocycle data:", error);
    //     renderMesocycleIndicator(null);
    // }

    // Using mock data for now:
    console.log("Using mock data for Mesocycle Phase Indicator.");
    renderMesocycleIndicator(mockMesocycleData);
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
