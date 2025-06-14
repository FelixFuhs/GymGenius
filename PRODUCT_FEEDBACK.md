# GymGenius Beta Feedback & KPI Dashboard Outline

This document outlines the structure for collecting beta user feedback and the Key Performance Indicators (KPIs) for monitoring the success and health of the GymGenius application during the beta phase and beyond.

## Part 1: Beta Feedback Survey

This survey aims to gather qualitative and quantitative feedback from beta users to identify areas for improvement, bugs, and overall user satisfaction.

### Section A: User Profile & Habits
*(Helps contextualize feedback)*

1.  **How would you describe your current primary fitness goal?**
    *   Building Muscle (Hypertrophy)
    *   Increasing Strength
    *   General Fitness / Staying Active
    *   Weight Loss
    *   Other (Please specify): _________

2.  **How many years of experience do you have with structured weight training?**
    *   Less than 1 year
    *   1-3 years
    *   3-5 years
    *   5+ years

3.  **On average, how many days per week do you currently train with weights?**
    *   1-2 days
    *   3-4 days
    *   5+ days

4.  **What devices did you primarily use to access GymGenius?** (Select all that apply)
    *   Smartphone (iOS)
    *   Smartphone (Android)
    *   Tablet
    *   Web browser on a computer

### Section B: Onboarding & Setup
*(Assesses initial user experience)*

5.  **How easy or difficult was it to sign up and set up your initial profile?** (Scale: 1=Very Difficult, 5=Very Easy)
    *   1 - 2 - 3 - 4 - 5
    *   Comments: _________

6.  **Were you able to easily input your available gym equipment (e.g., plates)?**
    *   Yes
    *   No
    *   Somewhat
    *   Comments: _________

### Section C: AI Weight & Rep Recommendations
*(Core feature assessment)*

7.  **How appropriate did you find the AI's weight recommendations for your main exercises?** (Scale: 1=Too Light/Easy, 3=Just Right, 5=Too Heavy/Hard)
    *   1 - 2 - 3 - 4 - 5
    *   Comments on specific exercises if applicable: _________

8.  **How appropriate did you find the AI's rep and RIR (Reps In Reserve) targets?** (Scale: 1=Not Appropriate, 5=Very Appropriate)
    *   1 - 2 - 3 - 4 - 5
    *   Comments: _________

9.  **Did you understand the "Why this weight?" explanation for the AI's suggestions?**
    *   Yes, it was clear.
    *   Somewhat, but it could be clearer.
    *   No, I didn't understand it.
    *   I didn't notice this feature.
    *   Comments: _________

10. **Over the course of the beta period, did you feel the AI recommendations adapted to your performance?**
    *   Yes, significantly
    *   Yes, somewhat
    *   No, not really
    *   I'm not sure
    *   Comments: _________

### Section D: Workout Logging & User Interface
*(Usability of daily tasks)*

11. **How easy or difficult was it to log your sets, reps, and RIR during a workout?** (Scale: 1=Very Difficult, 5=Very Easy)
    *   1 - 2 - 3 - 4 - 5
    *   Comments: _________

12. **What is your overall impression of the app's design and user interface?** (Scale: 1=Poor, 5=Excellent)
    *   1 - 2 - 3 - 4 - 5
    *   What did you like or dislike most about the UI? _________

13. **Did you encounter any technical issues or bugs? If so, please describe them.**
    *   _________________________

### Section E: Overall Experience & Suggestions

14. **Overall, how satisfied are you with your experience using GymGenius during the beta?** (Scale: 1=Very Dissatisfied, 5=Very Satisfied)
    *   1 - 2 - 3 - 4 - 5

15. **How likely are you to continue using GymGenius after the beta period?** (Scale: 1=Not at all Likely, 5=Very Likely)
    *   1 - 2 - 3 - 4 - 5

16. **What is the single most important feature GymGenius could add or improve?**
    *   _________________________

17. **Do you have any other comments, suggestions, or feedback?**
    *   _________________________

---

## Part 2: KPI Dashboard Outline

This outlines the Key Performance Indicators (KPIs) to track the success, engagement, and health of the GymGenius platform. These should be monitored regularly, ideally through an analytics platform like Mixpanel (as per ProjectVISION.md) and internal database queries.

### I. User Engagement & Retention
*   **Daily Active Users (DAU)**: Number of unique users interacting with the app daily.
*   **Monthly Active Users (MAU)**: Number of unique users interacting with the app monthly.
*   **DAU/MAU Ratio (Stickiness)**: `DAU / MAU`. Target >20% for good engagement, >50% for excellent (as per ProjectVISION).
*   **Session Length**: Average duration of a user session. Target: 15-30 minutes.
*   **Workouts Logged per User per Week**: Average number of workouts a user completes. Target: 3-4 for active users.
*   **User Retention Rate**:
    *   **Day 1, Day 7, Day 30 Retention**: Percentage of new users returning on these days.
    *   **Month-over-Month (MoM) Retention**: Percentage of users active in one month who return the next. Target: 80% M1, 60% M3 (as per ProjectVISION).
*   **Feature Adoption Rate**: Percentage of users utilizing key features (e.g., AI recommendations, "Why this weight?" tooltip, plan builder when available).

### II. Algorithm Performance & Effectiveness
*   **Recommendation Adherence Rate**: Percentage of sets where users use the AI-recommended weight (e.g., within +/- 5% of recommendation).
*   **Average RIR Deviation**: Difference between target RIR and actual RIR logged by users. (Track if RIR bias is converging).
*   **Perceived Recommendation Accuracy (from Survey)**: User-reported satisfaction with recommendations. Target: >4.0/5.
*   **Progression Rate**: Average rate of strength/1RM increase on key exercises for users over time. (Long-term metric).
*   **Plateau Incidence & Resolution**: Number of users hitting plateaus and successfully navigating them with app guidance (once plateau features are live).

### III. Platform Stability & Performance
*   **Application Crash Rate**: Number of crashes per session or per user.
*   **API Error Rate**: Percentage of API calls returning errors (e.g., 5xx).
*   **Average API Response Time**: Latency for key API endpoints. Target <200ms for 95th percentile (as per ProjectVISION).
*   **Uptime**: Percentage of time the service is available. Target: 99.9%.

### IV. Product & Business Metrics (Future-focused for Beta, more critical post-launch)
*   **Net Promoter Score (NPS)**: From surveys. (Standard measure of user satisfaction and loyalty).
*   **Conversion Rate (Freemium)**: Percentage of free users converting to paid plans (once applicable). Target: 5% (as per ProjectVISION).
*   **Customer Acquisition Cost (CAC)**: (Post-launch marketing). Target: <$50.
*   **Lifetime Value (LTV)**: (Post-launch). Target: >$300.
*   **Churn Rate**: Percentage of users discontinuing use/subscription per period. Target: <5% monthly for paid (as per ProjectVISION).

### Implementation Notes for KPI Dashboard:
*   **Data Sources**:
    *   Application Database (PostgreSQL): For user activity, workout logs, etc.
    *   Analytics Platform (e.g., Mixpanel): For event tracking, funnel analysis, user segmentation.
    *   Survey Tools: For qualitative feedback and NPS.
*   **Visualization**:
    *   Use a dashboarding tool (e.g., Grafana, Metabase, or built-in Mixpanel dashboards).
    *   Display trends over time (daily, weekly, monthly).
    *   Allow segmentation by user demographics, experience level, etc.

This `PRODUCT_FEEDBACK.md` serves as a starting point. The survey should be implemented using a suitable survey tool (e.g., Google Forms, Typeform, SurveyMonkey), and the KPI dashboard built out using appropriate analytics and visualization tools.

### Deployment Notes

The beta feedback survey is hosted on **Typeform** at `https://gymgenius.typeform.com/beta-survey`. The link is exposed in the PWA footer and configured via `webapp/js/config.js` so it can be updated without markup changes.
