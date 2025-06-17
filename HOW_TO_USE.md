# How to Use GymGenius

This guide provides step-by-step instructions on how to set up, run, and use the GymGenius application locally for development and testing.

## 1. Prerequisites

Ensure you have the following software installed on your system:

*   **Git:** For cloning the repository.
*   **Docker:** Version 24 or higher.
*   **Docker Compose:** Usually included with Docker.
*   **Python:** Version 3.11 (primarily for any direct script execution, though most operations are containerized).
*   **Make:** GNU Make (for using the `Makefile` shortcuts).
*   **Redis:** A running Redis instance is required for the background worker functionality. The `docker-compose.yml` includes a Redis service.

## 2. Setup and Installation

Follow these steps to get the application running:

**2.1. Clone the Repository**
```bash
git clone https://github.com/your-org/gymgenius.git
cd gymgenius
```
*(Replace `https://github.com/your-org/gymgenius.git` with the actual repository URL if different.)*

**2.2. Configure Environment Variables**
The application requires backend configurations, such as a JWT secret key and database connection details.
```bash
cp .env.example .env
```
Now, edit the newly created `.env` file and fill in the required values:
*   `JWT_SECRET_KEY`: Set this to a long, random, and secret string.
*   `DATABASE_URL`: This is optional if you are using the default Docker Compose setup. If you leave it blank, the application will use the `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_PORT` variables. The `docker-compose.yml` file pre-configures the `db` service with default credentials (`gymgenius_dev`, `gymgenius`, `secret`), which the `engine` service will use by default if `DATABASE_URL` isn't set.

**2.3. Start the Application Stack**
This command builds the Docker images (if they don't exist or if code has changed) and starts all services (web frontend, backend engine, database, Redis).
```bash
make dev
```
Wait for the services to build and start. You will see logs from Docker Compose in your terminal.

**2.4. Set Up the Database**
Once the `db` service is running (you'll see logs like `database system is ready to accept connections`), you need to create the database schema and populate it with initial data (like the exercise list).

Open a **new terminal window/tab**, navigate to the project directory (`gymgenius`), and run the following commands:

```bash
docker compose exec engine python database/create_schema.py
```
Wait for it to complete (you should see "Schema created successfully" or similar). Then run:
```bash
docker compose exec engine python database/seed_data.py
```
Wait for it to complete (you should see "Seed data inserted successfully" or similar).

**2.5. Run the Background Worker (Optional but Recommended for Full Functionality)**
The background worker processes tasks like updating user analytics or handling asynchronous operations. It relies on the Redis service started by `make dev`.

In **another new terminal window/tab** (or after the previous commands), navigate to the project directory and run:
```bash
docker compose exec engine python -m engine.worker
```
You should see logs from the RQ worker indicating it's ready to process jobs.

## 3. Accessing the Application

Once all services are running and the database is set up, you can access the GymGenius web application by opening your web browser and navigating to:

[http://localhost:8000](http://localhost:8000)

## 4. Basic Usage

**4.1. User Registration**
*   If you are a new user, click on the "Sign Up" link on the login page.
*   Fill in your email and password, then confirm your password.
*   Click "Sign Up". You should see a success message and then be redirected to the login page.

**4.2. User Login**
*   Enter your registered email and password.
*   Click "Login". You should be redirected to the main application area (e.g., the Exercises page).

**4.3. Navigating the UI**
*   **Exercises:** Browse available exercises. You can select an exercise from this page to start logging sets.
*   **My Workouts:** View your past workout sessions.
*   **RIR/Weight Calc:** A utility to help with weight calculations.
*   **Logout:** Click the "Logout" link in the footer navigation to end your session.

**4.4. Logging a Workout Set**
This is a core feature of GymGenius.
1.  **Select an Exercise:** Go to the "Exercises" page and click the "Log this Exercise" button next to your chosen exercise.
2.  **Log Set Page:** You'll be taken to a page dedicated to logging sets for that exercise.
    *   **AI Recommendation:** The application may display an AI-recommended weight, reps, and RIR. This is based on your history and exercise science principles. You can use these values or enter your own.
    *   **Enter Actuals:** Fill in the "Weight (kg)", "Reps", and "RIR (Reps In Reserve)" fields with what you actually performed (or plan to perform).
    *   **Log Set:** Click the "Log Set" button.
3.  **Feedback:**
    *   You'll see a message indicating if the set was logged successfully (e.g., "Set 1 logged successfully!").
    *   The form will reset some fields, allowing you to easily log your next set for the same exercise. The "Set #" display in the title will update.
4.  **Logging Subsequent Sets:** Simply update the weight/reps/RIR for your next set and click "Log Set" again. The set number will automatically increment.

## 5. Stopping the Application

To stop all running services (web, engine, db, redis), go to the terminal where you ran `make dev` and press `Ctrl+C`.
Alternatively, or if you ran it in detached mode, you can run:
```bash
make down
```
This will stop and remove the containers. Your data in the database and Redis (if persistence is configured and working) should remain in the Docker volumes (`postgres_data`, `redis_data`).

## 6. Troubleshooting

*   **Port Conflicts:** If `localhost:8000`, `localhost:5000`, `localhost:5432`, or `localhost:6379` are already in use on your machine, the services may fail to start. Stop any applications using these ports.
*   **`.env` file not configured:** Ensure `JWT_SECRET_KEY` is set in `.env`.
*   **Database connection errors in `engine` logs:**
    *   Ensure the `db` service is running.
    *   Verify the database credentials in your `.env` file match those used by the `db` service (defaults are usually fine).
    *   Make sure you have run `docker compose exec engine python database/create_schema.py`.
*   **Worker errors / Redis connection issues:**
    *   Ensure the `redis` service is running (started by `make dev`).
    *   Check worker logs for specific Redis connection errors.
*   **API calls failing (404s from frontend):**
    *   Ensure the Nginx configuration (`webapp/default.conf`) is correctly mounted in `docker-compose.yml` and that Nginx is proxying `/v1/` requests to the `engine` service. This guide assumes the fix for this is in place.

For further issues, please check the project's GitHub Issues page.
