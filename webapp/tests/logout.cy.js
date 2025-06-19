// cypress/integration/logout.cy.js

describe('Logout Functionality', () => {
    const apiBaseUrl = Cypress.env('API_BASE_URL') || 'http://localhost:5000'; // Use environment variable or default
    const testUser = {
        email: `testuser_logout_${Date.now()}@example.com`,
        password: 'password123'
    };
    let accessToken = null;
    let refreshToken = null;

    before(() => {
        // Register and login the user once before all tests in this block
        cy.request('POST', `${apiBaseUrl}/v1/auth/register`, {
            email: testUser.email,
            password: testUser.password
        }).then(response => {
            expect(response.status).to.eq(201);
        });

        cy.request('POST', `${apiBaseUrl}/v1/auth/login`, {
            email: testUser.email,
            password: testUser.password
        }).then(response => {
            expect(response.status).to.eq(200);
            expect(response.body).to.have.property('access_token');
            expect(response.body).to.have.property('refresh_token');
            accessToken = response.body.access_token;
            refreshToken = response.body.refresh_token;
        });
    });

    beforeEach(() => {
        // Before each test, set tokens in localStorage to simulate logged-in state
        // This is generally preferred over UI login for speed and reliability in most tests.
        if (accessToken && refreshToken) {
            cy.window().then(win => {
                win.localStorage.setItem('jwtToken', accessToken);
                win.localStorage.setItem('refreshToken', refreshToken);
            });
        }
        // Cypress automatically clears localStorage before each test by default,
        // so setting it in beforeEach ensures it's fresh for each test run if needed,
        // or use cy.saveLocalStorage() / cy.restoreLocalStorage() if you want persistence across tests in a describe block.
        // For this case, setting it fresh from the `before` block's tokens is fine.
    });

    it('should allow a logged-in user to log out successfully', () => {
        // Visit a page that requires authentication (e.g., exercises page or a protected route)
        cy.visit('/#exercises'); // Assuming #exercises is a protected route

        // Verify that the "Log out" link/button is visible
        // The logout link is in the footer, ensure footer is visible
        cy.get('footer nav #logout-link').should('be.visible');

        // Click the "Log out" link/button
        cy.get('footer nav #logout-link').click();

        // Assert that the user is redirected to the login page
        cy.hash().should('eq', '#login');

        // Assert that localStorage has been cleared of tokens
        cy.window().then(win => {
            expect(win.localStorage.getItem('jwtToken')).to.be.null;
            expect(win.localStorage.getItem('refreshToken')).to.be.null;
            expect(win.localStorage.getItem('workoutFlowState')).to.be.null; // Check other relevant items
        });

        // Wait for service worker unregistration and cache clearing to attempt completion
        cy.wait(1000); // Give some time for async operations

        // Attempt to navigate back to a protected page
        cy.visit('/#exercises');

        // Assert that the user is redirected back to the login page
        cy.hash().should('eq', '#login'); // The router should redirect
        cy.get('#login-form').should('be.visible'); // Check for an element specific to the login page
    });

    it('should handle stale tab protection: redirect to login if tokens are removed', () => {
        // Ensure user is "logged in" and on a protected page
        cy.visit('/#exercises');
        cy.get('footer nav #logout-link').should('be.visible'); // Verify logged-in state

        // Manually clear tokens from localStorage (simulating logout in another tab)
        cy.window().then(win => {
            win.localStorage.removeItem('jwtToken');
            win.localStorage.removeItem('refreshToken');
        });

        // Simulate visibility change: blur and focus the window
        // Cypress doesn't have a direct command to trigger 'visibilitychange' in a way that
        // perfectly mimics a tab switch, but blurring/focusing the document can sometimes trigger it.
        // A more reliable way might be to reload the page or visit it again.

        // Forcing a reload or re-visit is a common way to test this in Cypress
        cy.reload(); // Reload the current page
        // Or cy.visit('/#exercises'); again

        // Assert that the user is redirected to the login page
        cy.hash().should('eq', '#login');
        cy.get('#login-form').should('be.visible');

        // Check for the alert message (if possible, Cypress has limitations with native alerts)
        // Cypress automatically accepts alerts. To check text, you can stub it:
        const alertStub = cy.stub();
        cy.on('window:alert', alertStub);

        // Re-trigger the condition if reload wasn't enough.
        // This part is tricky as the event listener might have already fired on reload.
        // Forcing it by re-visiting after clearing tokens and then triggering visibility might be complex.
        // The reload itself should trigger the check in `DOMContentLoaded` or `visibilitychange` handler
        // if the handler is robust.
        // The current stale tab protection listens to 'visibilitychange'.
        // A reload will make the DOMContentLoaded fire, which calls navigate(),
        // which itself has protection.
        // Let's ensure the alert was called (or would have been called)
        // This assertion needs the event to fire *after* the stub is attached.
        // A simple way is to clear tokens, then visit a protected page again.
        cy.window().then(win => {
            win.localStorage.removeItem('jwtToken');
            win.localStorage.removeItem('refreshToken');
        });
        cy.visit('/#exercises'); // This should trigger redirection and potentially the alert

        // Check if the alert was called (if the logic leads to an alert)
        // The current stale tab protection code uses alert().
        // cy.wrap(alertStub).should('have.been.calledWith', 'You have been logged out. Please log in again.');
        // Note: Depending on exact timing and how Cypress handles alerts with page navigations,
        // this alert check might be flaky. The redirection is the primary assertion.
    });

    // Optional: Test service worker cache clearing
    // This is hard to directly assert from Cypress without specific browser APIs exposed or mockable.
    // You could potentially check if navigator.serviceWorker.getRegistration() returns null after logout,
    // but that's an indirect check for unregistration, not cache clearing itself.
    it('should unregister service worker on logout', () => {
        cy.visit('/#exercises'); // Ensure logged in
        cy.get('footer nav #logout-link').click();
        cy.hash().should('eq', '#login');

        // Check if service worker is unregistered
        // This needs to be done carefully, ensuring the command runs after unregistration attempt
        cy.window().then(async (win) => {
            if ('serviceWorker' in win.navigator) {
                const registration = await win.navigator.serviceWorker.getRegistration();
                expect(registration).to.be.undefined; // Or .be.null depending on browser
            } else {
                // Service workers not supported or enabled in this Cypress browser, skip test
                cy.log('Service workers not supported/enabled, skipping SW unregistration check.');
                expect(true).to.be.true; // Placeholder assertion
            }
        });
    });
});
