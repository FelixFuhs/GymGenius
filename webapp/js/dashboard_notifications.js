// --- Plateau Event Notifications ---

// Helper function to get the currently logged-in user's ID
// Assumes JWT is stored in localStorage and contains user_id payload
function getCurrentUserId() {
    const token = getAuthToken();
    if (token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            return payload.user_id;
        } catch (e) {
            console.error("Error decoding JWT or user_id not found:", e);
            return null;
        }
    }
    return null;
}

// Helper function to get the auth token
function getAuthToken() {
    return localStorage.getItem('jwtToken');
}

// Helper function for API calls
async function fetchAPI(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    const authToken = getAuthToken();
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const response = await fetch(url, { ...options, headers });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Request failed with status ' + response.status }));
        throw new Error(errorData.error || `HTTP error ${response.status}`);
    }
    if (response.status === 204) { // No Content
        return null;
    }
    return response.json();
}

// Function to fetch plateau notifications
async function fetchPlateauNotifications() {
    const userId = getCurrentUserId();
    if (!userId) {
        console.log("User ID not found, cannot fetch notifications.");
        return;
    }

    try {
        const notifications = await fetchAPI(`/v1/users/${userId}/plateau-notifications`);
        if (notifications && notifications.length > 0) {
            displayPlateauNotifications(notifications);
        } else {
            // console.log("No new plateau notifications.");
            // Optionally clear the container or display a "no notifications" message
            const container = document.getElementById('notifications-container');
            if (container) container.innerHTML = ''; // Clear old notifications
        }
    } catch (error) {
        console.error("Error fetching plateau notifications:", error);
        // Optionally display an error message to the user in the notifications container
        const container = document.getElementById('notifications-container');
        if (container) {
            container.innerHTML = `<div class="plateau-notification error">Failed to load notifications.</div>`;
        }
    }
}

// Function to display plateau notifications
function displayPlateauNotifications(notifications) {
    let container = document.getElementById('notifications-container');
    if (!container) {
        console.error("Notification container not found!");
        // As a fallback, create and prepend it to the main dashboard area if not found
        container = document.createElement('div');
        container.id = 'notifications-container';
        const mainDashboard = document.getElementById('dashboard-main');
        if (mainDashboard) {
            mainDashboard.prepend(container);
        } else {
            document.body.prepend(container); // Fallback to body
        }
    }
    container.innerHTML = ''; // Clear previous notifications

    notifications.forEach(notification => {
        const notificationDiv = document.createElement('div');
        notificationDiv.className = 'plateau-notification';
        notificationDiv.id = `plateau-event-${notification.event_id}`;

        const detectedDate = new Date(notification.detected_at).toLocaleDateString('en-CA', {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });

        notificationDiv.innerHTML = `
            <p><strong>Plateau Alert for ${notification.exercise_name}</strong></p>
            <p>Details: ${notification.details || 'N/A'}</p>
            <p><small>Detected: ${detectedDate}</small></p>
            <p><small>Protocol Applied: ${notification.protocol_applied || 'N/A'}</small></p>
            <button class="acknowledge-btn" data-event-id="${notification.event_id}">Got it!</button>
        `;

        container.appendChild(notificationDiv);
    });

    // Add event listeners to all acknowledge buttons
    container.querySelectorAll('.acknowledge-btn').forEach(button => {
        button.addEventListener('click', async (event) => {
            const eventId = event.target.dataset.eventId;
            try {
                await acknowledgePlateauNotification(eventId);
                const notificationElement = document.getElementById(`plateau-event-${eventId}`);
                if (notificationElement) {
                    notificationElement.remove();
                }
                // Check if container is empty and remove or add "no notifications" message
                if (container.children.length === 0) {
                    // container.innerHTML = '<p>No new notifications.</p>'; // Optional
                }
            } catch (error) {
                // Error already logged by acknowledgePlateauNotification
                // Optionally, display an error message on the specific notification
                const notificationElement = document.getElementById(`plateau-event-${eventId}`);
                if (notificationElement) {
                    let errorMsgElem = notificationElement.querySelector('.ack-error');
                    if (!errorMsgElem) {
                        errorMsgElem = document.createElement('p');
                        errorMsgElem.style.color = 'red';
                        errorMsgElem.className = 'ack-error';
                        notificationElement.appendChild(errorMsgElem);
                    }
                    errorMsgElem.textContent = 'Failed to acknowledge. Please try again.';
                }
            }
        });
    });
}

// Function to acknowledge a plateau notification
async function acknowledgePlateauNotification(eventId) {
    if (!eventId) {
        console.error("Event ID is missing, cannot acknowledge notification.");
        throw new Error("Event ID missing.");
    }

    try {
        await fetchAPI(`/v1/plateau-events/${eventId}/acknowledge`, { method: 'POST' });
        console.log(`Notification ${eventId} acknowledged successfully.`);
    } catch (error) {
        console.error(`Error acknowledging plateau notification ${eventId}:`, error);
        throw error; // Re-throw to be caught by the caller for UI update
    }
}

// Fetch notifications when the dashboard page loads
document.addEventListener('DOMContentLoaded', () => {
    // Check if we are on the analytics dashboard page before fetching.
    // This is a simple check; a more robust solution might involve specific body ID or class.
    if (document.getElementById('dashboard-main') || window.location.pathname.includes('analytics_dashboard.html')) {
        fetchPlateauNotifications();
    }
});
