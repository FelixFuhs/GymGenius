document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('rest-timer-canvas');
    if (canvas && typeof canvas.getContext === 'function') { // Check if canvas and getContext are available
        const ctx = canvas.getContext('2d');
        const radius = canvas.width / 2 - 10; // Radius, leaving some padding
        const lineWidth = 8; // Width of the circle line

        // Background circle (track)
        ctx.beginPath();
        ctx.arc(canvas.width / 2, canvas.height / 2, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = '#e9ecef'; // Light grey for the track
        ctx.lineWidth = lineWidth;
        ctx.stroke();

        // Example of a filled portion (e.g., timer progress for styling)
        // This represents roughly 1/4 progress. Adjust as needed for visual testing.
        // const startAngle = -0.5 * Math.PI; // Start at the top
        // const endAngle = 0 * Math.PI; // Progress to 1/4 way (0 is right, 0.5*PI is bottom, PI is left)
        // ctx.beginPath();
        // ctx.arc(canvas.width / 2, canvas.height / 2, radius, startAngle, endAngle);
        // ctx.strokeStyle = '#007bff'; // Primary color for progress
        // ctx.lineWidth = lineWidth;
        // ctx.stroke();

        console.log('Rest timer canvas placeholder drawn.');
    } else {
        console.warn('Rest timer canvas not found or not supported.');
    }
});
