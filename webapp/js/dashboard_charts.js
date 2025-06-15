document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard charts script loaded and DOM fully parsed.');

    init1RMEvolutionChart();
    initStrengthCurveChart();
    initVolumeDistributionChart();
    displayKeyMetrics();
});

// Store chart instances globally to manage their lifecycle
window.current1RMChart = null;
window.currentStrengthCurveChart = null;
window.currentVolumeChart = null;

const mock1RMEvolutionData = {
    "Squat": [
        { date: "2023-01-01", e1RM: 100 }, { date: "2023-01-15", e1RM: 102 },
        { date: "2023-02-01", e1RM: 105 }, { date: "2023-02-15", e1RM: 107 },
        { date: "2023-03-01", e1RM: 110 }, { date: "2023-03-15", e1RM: 108 },
        { date: "2023-04-01", e1RM: 112 }
    ],
    "Bench Press": [
        { date: "2023-01-01", e1RM: 70 }, { date: "2023-01-15", e1RM: 72 },
        { date: "2023-02-01", e1RM: 73 }, { date: "2023-02-15", e1RM: 75 },
        { date: "2023-03-01", e1RM: 76 }, { date: "2023-03-15", e1RM: 75 },
        { date: "2023-04-01", e1RM: 78 }
    ],
    "Deadlift": [
        { date: "2023-01-01", e1RM: 120 }, { date: "2023-01-15", e1RM: 125 },
        { date: "2023-02-01", e1RM: 128 }, { date: "2023-02-15", e1RM: 130 },
        { date: "2023-03-01", e1RM: 132 }, { date: "2023-03-15", e1RM: 135 },
        { date: "2023-04-01", e1RM: 138 }
    ]
};

function render1RMEvolutionChart(exerciseName) {
    console.log(`Rendering 1RM Evolution Chart for: ${exerciseName}`);
    const ctx = document.getElementById('1rmEvolutionChart').getContext('2d');
    if (!ctx) { console.error('1rmEvolutionChart canvas element not found for rendering!'); return; }
    const exerciseData = mock1RMEvolutionData[exerciseName];
    if (!exerciseData) {
        console.error(`No data found for exercise: ${exerciseName}`);
        if (window.current1RMChart) { window.current1RMChart.destroy(); window.current1RMChart = null; }
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText(`No data available for ${exerciseName}.`, ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }
    const labels = exerciseData.map(dp => dp.date);
    const dataPoints = exerciseData.map(dp => dp.e1RM);
    if (window.current1RMChart) { window.current1RMChart.destroy(); }
    try {
        window.current1RMChart = new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: [{ label: `${exerciseName} e1RM (kg)`, data: dataPoints, borderColor: 'rgb(75, 192, 192)', backgroundColor: 'rgba(75, 192, 192, 0.2)', tension: 0.1, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { type: 'time', time: { unit: 'month', tooltipFormat: 'MMM dd, yyyy', displayFormats: { month: 'MMM yyyy'}}, title: { display: true, text: 'Date' }}, y: { title: { display: true, text: 'Estimated 1RM (kg)' }, beginAtZero: false }}, plugins: { title: { display: true, text: `1RM Evolution for ${exerciseName}` }, legend: { display: true, position: 'top' }}}
        });
        console.log(`1RM Evolution Chart for ${exerciseName} rendered successfully.`);
    } catch (error) { console.error(`Error rendering 1RM Evolution Chart for ${exerciseName}:`, error); }
}

function init1RMEvolutionChart() {
    console.log('Setting up 1RM Evolution Chart and Selector...');
    const selector = document.getElementById('exerciseSelector1RM');
    if (!selector) { console.error('exerciseSelector1RM element not found!'); return; }
    Object.keys(mock1RMEvolutionData).forEach(exerciseName => {
        const option = document.createElement('option');
        option.value = exerciseName; option.textContent = exerciseName;
        selector.appendChild(option);
    });
    selector.addEventListener('change', (event) => render1RMEvolutionChart(event.target.value));
    if (Object.keys(mock1RMEvolutionData).length > 0) {
        const initialExercise = Object.keys(mock1RMEvolutionData)[0];
        selector.value = initialExercise; render1RMEvolutionChart(initialExercise);
    } else {
        console.warn("mock1RMEvolutionData is empty. No chart to render initially.");
        const ctx = document.getElementById('1rmEvolutionChart').getContext('2d');
        if (ctx) { ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); ctx.font = "16px Arial"; ctx.textAlign = "center"; ctx.fillText("No 1RM data available.", ctx.canvas.width / 2, ctx.canvas.height / 2); }
    }
}

const mockStrengthCurveData = { /* ... (data as before, kept for brevity) ... */
    "Squat": [ { date: "2023-02-01", load: 90, reps_achieved: 5 }, { date: "2023-02-01", load: 80, reps_achieved: 8 }, { date: "2023-02-08", load: 92.5, reps_achieved: 4 }, { date: "2023-02-08", load: 82.5, reps_achieved: 7 }, { date: "2023-03-01", load: 100, reps_achieved: 3 }, { date: "2023-03-01", load: 85, reps_achieved: 6 }, { date: "2023-04-01", load: 105, reps_achieved: 2 } ], "Bench Press": [ { date: "2023-02-01", load: 60, reps_achieved: 5 }, { date: "2023-02-01", load: 50, reps_achieved: 8 }, { date: "2023-02-15", load: 62.5, reps_achieved: 4 }, { date: "2023-03-01", load: 65, reps_achieved: 3 } ], "Deadlift": [ { date: "2023-02-01", load: 110, reps_achieved: 5 }, { date: "2023-03-01", load: 120, reps_achieved: 3 }, { date: "2023-04-01", load: 125, reps_achieved: 2 } ]};

function calculateTheoreticalLoad(e1RM, reps) { if (reps === 0) return e1RM; if (reps > 30) return 0; return e1RM * (1 - 0.025 * reps); }

function renderStrengthCurveChart(exerciseName) {
    console.log(`Rendering Strength Curve Chart for: ${exerciseName}`);
    const ctx = document.getElementById('strengthCurveChart').getContext('2d');
    if (!ctx) { console.error('strengthCurveChart canvas element not found!'); return; }
    const achievedSetsData = mockStrengthCurveData[exerciseName];
    if (!achievedSetsData || achievedSetsData.length === 0) {
        console.warn(`No strength curve data found for exercise: ${exerciseName}`);
        if (window.currentStrengthCurveChart) { window.currentStrengthCurveChart.destroy(); window.currentStrengthCurveChart = null; }
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); ctx.font = "16px Arial"; ctx.textAlign = "center";
        ctx.fillText(`No strength curve data for ${exerciseName}.`, ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }
    const scatterData = achievedSetsData.map(set => ({ x: set.load, y: set.reps_achieved, date: set.date }));
    const datasets = [{ label: 'Achieved Sets', data: scatterData, backgroundColor: 'rgba(75, 192, 192, 0.7)', pointRadius: 5, pointHoverRadius: 7 }];
    const e1RMEvolution = mock1RMEvolutionData[exerciseName];
    if (e1RMEvolution && e1RMEvolution.length > 0) {
        const latestE1RMEntry = e1RMEvolution.reduce((latest, current) => new Date(current.date) > new Date(latest.date) ? current : latest);
        const latestE1RM = latestE1RMEntry.e1RM;
        if (latestE1RM > 0) {
            const theoreticalCurveData = [];
            for (let reps = 1; reps <= 15; reps++) { const load = calculateTheoreticalLoad(latestE1RM, reps); if (load > 0) theoreticalCurveData.push({ x: load, y: reps }); }
            theoreticalCurveData.sort((a, b) => a.x - b.x);
            datasets.push({ label: `Theoretical Curve (e1RM: ${latestE1RM.toFixed(1)}kg)`, data: theoreticalCurveData, type: 'line', borderColor: 'rgba(255, 99, 132, 1)', backgroundColor: 'rgba(255, 99, 132, 0.2)', fill: false, tension: 0.1, pointRadius: 0 });
        }
    }
    if (window.currentStrengthCurveChart) { window.currentStrengthCurveChart.destroy(); }
    try {
        window.currentStrengthCurveChart = new Chart(ctx, {
            type: 'scatter', data: { datasets: datasets },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { title: { display: true, text: 'Load (kg)' }, beginAtZero: false, type: 'linear', position: 'bottom' }, y: { title: { display: true, text: 'Reps Achieved' }, beginAtZero: true }}, plugins: { title: { display: true, text: `Strength Curve for ${exerciseName}` }, tooltip: { callbacks: { label: function(context) { let label = context.dataset.label || ''; if (label) { label += ': '; } if (context.parsed.y !== null) label += `${context.parsed.y} reps at ${context.parsed.x.toFixed(1)} kg`; if (context.dataset.label === 'Achieved Sets' && scatterData[context.dataIndex]) label += ` (on ${scatterData[context.dataIndex].date})`; return label; }}}, legend: { position: 'top' }}}
        });
        console.log(`Strength Curve Chart for ${exerciseName} rendered successfully.`);
    } catch (error) { console.error(`Error rendering Strength Curve Chart for ${exerciseName}:`, error); }
}

function initStrengthCurveChart() {
    console.log('Setting up Strength Curve Chart and Selector...');
    const selector = document.getElementById('exerciseSelectorStrengthCurve');
    if (!selector) { console.error('exerciseSelectorStrengthCurve element not found!'); return; }
    Object.keys(mockStrengthCurveData).forEach(exerciseName => {
        const option = document.createElement('option');
        option.value = exerciseName; option.textContent = exerciseName;
        selector.appendChild(option);
    });
    selector.addEventListener('change', (event) => renderStrengthCurveChart(event.target.value));
    if (Object.keys(mockStrengthCurveData).length > 0) {
        const initialExercise = Object.keys(mockStrengthCurveData)[0];
        selector.value = initialExercise; renderStrengthCurveChart(initialExercise);
    } else {
        console.warn("mockStrengthCurveData is empty. No chart to render initially.");
        const ctx = document.getElementById('strengthCurveChart').getContext('2d');
        if (ctx) { ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height); ctx.font = "16px Arial"; ctx.textAlign = "center"; ctx.fillText("No strength curve data available.", ctx.canvas.width / 2, ctx.canvas.height / 2); }
    }
}

const mockWeeklyVolumeData = [ { date: "2023-03-06", exerciseName: "Squat", sets: 4, muscleGroup: "Legs" }, { date: "2023-03-06", exerciseName: "Leg Press", sets: 3, muscleGroup: "Legs" }, { date: "2023-03-07", exerciseName: "Bench Press", sets: 4, muscleGroup: "Chest" }, { date: "2023-03-07", exerciseName: "Flyes", sets: 3, muscleGroup: "Chest" }, { date: "2023-03-07", exerciseName: "Tricep Pushdown", sets: 3, muscleGroup: "Triceps" }, { date: "2023-03-08", exerciseName: "Deadlift", sets: 2, muscleGroup: "Back" }, { date: "2023-03-08", exerciseName: "Rows", sets: 4, muscleGroup: "Back" }, { date: "2023-03-08", exerciseName: "Bicep Curl", sets: 3, muscleGroup: "Biceps" }, { date: "2023-03-09", exerciseName: "Overhead Press", sets: 4, muscleGroup: "Shoulders" }, { date: "2023-03-10", exerciseName: "Squat", sets: 5, muscleGroup: "Legs" }, { date: "2023-03-10", exerciseName: "Hamstring Curl", sets: 3, muscleGroup: "Legs" }, { date: "2023-03-11", exerciseName: "Pull-ups", sets: 4, muscleGroup: "Back" }];
const muscleGroupColors = { "Legs": "rgba(255, 99, 132, 0.7)", "Chest": "rgba(54, 162, 235, 0.7)", "Triceps": "rgba(75, 192, 192, 0.7)", "Back": "rgba(255, 206, 86, 0.7)", "Biceps": "rgba(153, 102, 255, 0.7)", "Shoulders": "rgba(255, 159, 64, 0.7)", "Core": "rgba(100, 100, 100, 0.7)", "Default": "rgba(201, 203, 207, 0.7)" };
let _colorIndex = 0; const _availableColors = Object.values(muscleGroupColors);
function getMuscleGroupColor(muscleGroup) { if (muscleGroupColors[muscleGroup]) return muscleGroupColors[muscleGroup]; const color = _availableColors[_colorIndex % _availableColors.length]; _colorIndex++; muscleGroupColors[muscleGroup] = color; return color; }

function processVolumeData(workouts) {
    const daysOfWeek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const volumeByDayAndMuscleGroup = {};
    workouts.forEach(workout => {
        const dayIndex = new Date(workout.date).getDay();
        const muscleGroup = workout.muscleGroup; const sets = workout.sets;
        if (!volumeByDayAndMuscleGroup[muscleGroup]) { volumeByDayAndMuscleGroup[muscleGroup] = Array(7).fill(0); }
        volumeByDayAndMuscleGroup[muscleGroup][dayIndex] += sets;
    });
    return { labels: daysOfWeek, datasets: Object.keys(volumeByDayAndMuscleGroup).map(muscleGroup => ({ label: muscleGroup, data: volumeByDayAndMuscleGroup[muscleGroup], backgroundColor: getMuscleGroupColor(muscleGroup), borderColor: getMuscleGroupColor(muscleGroup).replace('0.7', '1'), borderWidth: 1 })) };
}

function initVolumeDistributionChart() {
    console.log('Initializing Volume Distribution Chart...');
    const ctxElement = document.getElementById('volumeDistributionChart');
    if (!ctxElement) { console.error('volumeDistributionChart canvas element not found!'); return; }
    const ctx = ctxElement.getContext('2d');
    const processedData = processVolumeData(mockWeeklyVolumeData);
    if (window.currentVolumeChart) { window.currentVolumeChart.destroy(); }
    try {
        window.currentVolumeChart = new Chart(ctx, {
            type: 'bar', data: processedData,
            options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Weekly Volume Distribution (Total Sets by Muscle Group)' }, tooltip: { mode: 'index', intersect: false }, legend: { position: 'top' }}, scales: { x: { title: { display: true, text: 'Day of Week' } }, y: { title: { display: true, text: 'Total Sets' }, beginAtZero: true, ticks: { stepSize: 1 }}}}
        });
        console.log('Volume Distribution Chart initialized successfully.');
    } catch (error) { console.error('Error initializing Volume Distribution Chart:', error); }
}

const mockKeyMetricsData = {
    "avgSessionDuration": { current: 45, previous: 50, unit: "min", name: "Avg Session Duration" },
    "weeklyTotalVolume": { current: 120, previous: 110, unit: "sets", name: "Weekly Total Volume" },
    "trainingFrequency": { current: 4, previous: 3, unit: "days/week", name: "Training Frequency" },
    "bodyWeight": { current: 75, previous: 74.5, unit: "kg", name: "Body Weight" },
    "failedSetsRatio": { current: 0.05, previous: 0.08, unit: "%", name: "Failed Sets Ratio" } // Example for a metric that's better if lower
};

function displayKeyMetrics() {
    console.log('Displaying Key Metrics...');
    const metricsListElement = document.getElementById('metrics-list');
    if (!metricsListElement) { console.error('metrics-list element not found!'); return; }
    metricsListElement.innerHTML = ''; // Clear existing metrics

    for (const key in mockKeyMetricsData) {
        const metric = mockKeyMetricsData[key];
        const li = document.createElement('li');

        let percentageChange = 0;
        if (metric.previous !== 0) {
            percentageChange = ((metric.current - metric.previous) / metric.previous) * 100;
        } else if (metric.current > 0) {
            percentageChange = 100; // Or handle as "new" or infinite increase
        }

        let trendIndicator = '●';
        let trendClass = 'trend-neutral';
        // For 'failedSetsRatio', lower is better.
        const lowerIsBetterMetrics = ['failedSetsRatio'];
        const isLowerBetter = lowerIsBetterMetrics.includes(key);

        if (percentageChange > 1) { // Use a threshold to ignore tiny changes
            trendIndicator = isLowerBetter ? '▼' : '▲';
            trendClass = isLowerBetter ? 'trend-up' : 'trend-up'; // Green for positive change (good or bad based on metric)
        } else if (percentageChange < -1) {
            trendIndicator = isLowerBetter ? '▲' : '▼';
            trendClass = isLowerBetter ? 'trend-down' : 'trend-down'; // Red for negative change
        }
         // Correcting trend class based on good/bad
        if (trendIndicator === '▲' && !isLowerBetter || trendIndicator === '▼' && isLowerBetter) {
            trendClass = 'trend-up'; // Good trend
        } else if (trendIndicator === '▼' && !isLowerBetter || trendIndicator === '▲' && isLowerBetter) {
            trendClass = 'trend-down'; // Bad trend
        }


        const metricNameSpan = document.createElement('span');
        metricNameSpan.classList.add('metric-name');
        metricNameSpan.textContent = metric.name + ': ';

        const metricValueSpan = document.createElement('span');
        metricValueSpan.classList.add('metric-value');
        metricValueSpan.textContent = `${metric.current} ${metric.unit}`;

        const trendSpan = document.createElement('span');
        trendSpan.classList.add('trend-indicator', trendClass);
        trendSpan.textContent = `${trendIndicator} ${percentageChange.toFixed(2)}%`;

        if (metric.previous === 0 && metric.current > 0) {
             trendSpan.textContent = `${trendIndicator} New`;
        } else if (metric.previous === 0 && metric.current === 0) {
             trendSpan.textContent = `● N/A`;
        }


        li.appendChild(metricNameSpan);
        li.appendChild(metricValueSpan);
        li.appendChild(trendSpan);
        metricsListElement.appendChild(li);
    }
}
