# GymGenius - Comprehensive Project Specification
*The AI-Powered Adaptive Training System That Thinks So You Don't Have To*

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Core Concept & Vision](#core-concept--vision)
3. [User Problems We're Solving](#user-problems-were-solving)
4. [Feature Specifications](#feature-specifications)
5. [Algorithm Design](#algorithm-design)
6. [User Interface & Experience](#user-interface--experience)
7. [Technical Architecture](#technical-architecture)
8. [Data Models & Schema](#data-models--schema)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Future Vision & Extensions](#future-vision--extensions)

---

## Executive Summary

GymGenius is an intelligent gym training application that automatically optimizes weight, rep, and rest recommendations based on individual performance data and exercise science. Unlike traditional workout apps that simply log data, GymGenius actively learns from each set performed and provides real-time, personalized recommendations that adapt to the user's recovery, strength progression, and goals.

### Key Differentiators:
- **Zero Thinking Required**: AI predicts optimal weights for every set
- **Science-Based**: Grounded in mechanical tension research and volume landmarks
- **Truly Adaptive**: Learns individual recovery patterns and RIR accuracy
- **Flexible**: Handles missed workouts, different equipment, and changing goals
- **Beautiful Data**: Spreadsheet-inspired UI that's information-dense yet elegant

---

## Core Concept & Vision

### The Problem
Every gym-goer faces the same questions:
- "Should I increase the weight today?"
- "How many reps should I aim for?"
- "Am I doing too much or too little volume?"
- "When should I deload?"

Current solutions either provide generic programs or require extensive knowledge to self-regulate.

### Our Solution
An AI that acts as a personal coach in your pocket, making optimal decisions based on:
- Your actual performance data
- Current fatigue levels
- Individual recovery patterns
- Scientific principles of strength and hypertrophy

### The Training Loop
```
1. Open app → See today's workout with AI-predicted weights
2. Perform set → Input actual reps and RIR
3. Algorithm learns and adapts
4. Next set gets smarter recommendation
5. Continuous improvement over time
```

---

## User Problems We're Solving

### 1. **Decision Fatigue in the Gym**
- **Problem**: Constantly wondering if you should go heavier or lighter
- **Solution**: AI makes the decision based on your recent performance

### 2. **Plate Math Complexity**
- **Problem**: Calculating 67.5kg with available plates
- **Solution**: Automatic rounding to available equipment

### 3. **Volume Management**
- **Problem**: Not knowing if you're doing too much or too little
- **Solution**: Real-time volume tracking with scientific landmarks (MEV/MAV/MRV)

### 4. **Plateau Detection**
- **Problem**: Not recognizing when progress has stalled
- **Solution**: Automatic detection and implementation of overload/deload protocols

### 5. **Schedule Flexibility**
- **Problem**: Programs break when life happens
- **Solution**: Floating rest days and intelligent adaptation

### 6. **Goal Confusion**
- **Problem**: Complex periodization for mixed goals
- **Solution**: Simple slider from strength to hypertrophy

---

## Feature Specifications

### Part 1: Exercise Database & Management

#### Pre-loaded Exercise Library
- **Categories**: 
  - Movement Pattern: Push/Pull/Squat/Hinge/Carry/Isolation
  - Equipment: Barbell/Dumbbell/Cable/Machine/Bodyweight
  - Difficulty: Beginner/Intermediate/Advanced
  
- **Exercise Data Structure**:
  ```
  {
    name: "Barbell Bench Press",
    category: "Push",
    equipment: "Barbell",
    primaryMuscles: { chest: 1.0 },
    secondaryMuscles: { triceps: 0.5, frontDelts: 0.3 },
    fatigueRating: "High",
    techniqueNotes: "...",
    commonMistakes: ["..."],
    videoUrl: "..."
  }
  ```

#### Custom Exercise Creator
- Users can add personal variations
- Specify muscle involvement percentages
- Add notes and cues
- Mark as public/private

### Part 2: Smart Training Plan Builder

#### Plan Creation Interface
- **Drag-and-drop** exercises between days
- **Real-time volume analysis** per muscle group
- **Frequency recommendations** based on goals
- **Template library** for common splits

#### Volume Analysis Features
- **Visual indicators**: 
  ```
  Chest: ████████████░░░░ (16 sets) ✓ Optimal
  Back:  ██████████████████ (20 sets) ⚠️ Approaching MRV
  ```
- **Fractional set counting**: Bench = 1.0 chest, 0.5 triceps
- **Recovery time estimates** per muscle group

#### Flexible Scheduling
- **Floating rest days**: Plan adapts to actual training days
- **Missed workout handling**: Volume redistribution
- **Vacation mode**: Intelligent restart protocols

### Part 3: Intelligent Workout Execution

#### During-Workout Features
- **AI Weight Recommendations**: Based on recent performance
- **RIR Learning**: Calibrates to user's accuracy over time
- **Rest Timer**: Adaptive based on load and fatigue
- **Performance Tracking**: Real-time comparison to previous sessions

#### The Prediction Engine
- **Inputs**:
  - Historical sets (weight × reps × RIR)
  - Time since last stimulus
  - Recent trend (improving/plateauing)
  - Session RPE
  - Recovery markers
  
- **Outputs**:
  - Recommended weight (plate-rounded)
  - Target rep range
  - Target RIR
  - Confidence score (0-100%)

### Part 4: Analytics & Progress Tracking

#### Performance Dashboard
- **1RM Evolution**: Track estimated max strength over time
- **Volume Distribution**: Visual breakdown by muscle group
- **Mechanical Tension Index**: Cumulative effective reps
- **Fatigue Monitoring**: Trend analysis and deload recommendations

#### Progress Visualization
- **Strength curves** per exercise
- **Volume heatmaps** by muscle group
- **Recovery patterns** learning
- **Goal achievement** tracking

### Part 5: Community & Social Features (Future)

#### Program Marketplace
- **Verified coaches** can publish programs
- **User ratings** and reviews
- **AI adaptation**: Purchased programs adjust to user level
- **Revenue sharing** for creators

#### Social Elements
- **Training partners**: Virtual workout buddies
- **Form checks**: Video submission for feedback
- **Challenges**: Friendly competitions
- **Achievements**: Gamification without being cheesy

---

## Algorithm Design

### Core Algorithm: Adaptive Training Engine

#### 1. Goal Interpolation System
```python
# User sets goal: 0 = pure hypertrophy, 1 = pure strength
def calculate_training_params(goal_strength_fraction):
    load_percentage = 0.60 + 0.35 * goal_strength_fraction
    target_rir = 2.5 - 1.5 * goal_strength_fraction  
    rest_minutes = 1.5 + 2.0 * goal_strength_fraction
    
    # Rep ranges
    rep_high = 6 + 6 * (1 - goal_strength_fraction)
    rep_low = max(1, rep_high - 4)
    
    return {
        'load': load_percentage,
        'rir': int(round(target_rir)),
        'rest': rest_minutes * 60,  # in seconds
        'rep_range': (rep_low, rep_high)
    }
```

#### 2. 1RM Estimation with RIR
```python
def estimate_1rm(weight, reps, rir, user_rir_bias):
    """Extended Epley formula with RIR adjustment"""
    adjusted_rir = max(0, rir - user_rir_bias)
    total_reps = reps + adjusted_rir
    
    if total_reps >= 30:
        return weight * 2.5  # Cap at 2.5x for high reps
    
    one_rm = weight / (1 - 0.0333 * total_reps)
    return one_rm
```

#### 3. Mechanical Tension Index (MTI)
```python
def calculate_mti(sets_data):
    """Calculate cumulative mechanical tension"""
    total_mti = 0
    
    for set_data in sets_data:
        weight, reps, rir = set_data
        
        # Only last ~4-5 reps before failure count as "effective"
        effective_reps = max(0, reps - max(0, rir - 4))
        
        # Weight factor (normalized to estimated 1RM)
        weight_factor = weight / estimate_1rm(weight, reps, rir)
        
        total_mti += effective_reps * weight_factor
    
    return total_mti
```

#### 4. Fatigue & Recovery Model
```python
def calculate_fatigue(session_history, muscle_group):
    """Impulse-response fatigue model"""
    current_fatigue = 0
    now = datetime.now()
    
    # Recovery time constants (hours)
    recovery_tau = {
        'chest': 48, 'back': 48, 'shoulders': 36,
        'biceps': 36, 'triceps': 36, 'quads': 72,
        'hamstrings': 48, 'glutes': 48, 'calves': 24
    }
    
    for session in session_history:
        time_elapsed = (now - session.date).total_seconds() / 3600
        session_contribution = session.volume * session.intensity
        
        # Exponential decay
        decay_factor = exp(-time_elapsed / recovery_tau[muscle_group])
        current_fatigue += session_contribution * decay_factor
    
    return current_fatigue
```

#### 5. Adaptive Weight Recommendation
```python
def recommend_weight(user, exercise, set_number, goal_fraction):
    """Main recommendation engine"""
    
    # Get baseline from recent performance
    recent_sets = get_recent_sets(user, exercise, days=14)
    estimated_1rm = calculate_rolling_1rm(recent_sets)
    
    # Apply goal-based loading
    base_load = estimated_1rm * (0.60 + 0.35 * goal_fraction)
    
    # Adjust for fatigue
    fatigue_factor = calculate_fatigue_factor(user, exercise)
    base_load *= (1 - fatigue_factor * 0.1)  # Max 10% reduction
    
    # Adjust for within-session fatigue
    if set_number > 1:
        previous_set_performance = get_previous_set_today(user, exercise)
        if previous_set_performance.rir < target_rir:
            base_load *= 0.95  # 5% reduction if struggling
    
    # Adjust for readiness (if available)
    readiness = calculate_readiness(user)
    base_load *= (1 + readiness * 0.05)  # ±5% based on readiness
    
    # Round to available plates
    rounded_weight = round_to_plates(base_load, user.available_plates)
    
    # Calculate confidence
    confidence = calculate_confidence(recent_sets, estimated_1rm)
    
    return {
        'weight': rounded_weight,
        'confidence': confidence,
        'reasoning': generate_reasoning(...)
    }
```

#### 6. Plateau Detection & Breaking
```python
def detect_plateau(exercise_history):
    """Detect training plateaus"""
    
    # Calculate 14-day trend
    recent_1rm_estimates = [estimate_1rm(s.weight, s.reps, s.rir) 
                           for s in exercise_history[-6:]]
    
    if len(recent_1rm_estimates) < 3:
        return False
    
    # Linear regression
    slope = calculate_trend_slope(recent_1rm_estimates)
    
    # Plateau if less than 0.5% improvement
    if slope < 0.005 * mean(recent_1rm_estimates):
        return True
    
    return False

def generate_plateau_protocol(current_program):
    """Generate overload->deload protocol"""
    return {
        'week1': {
            'volume_multiplier': 1.1,  # +10% volume
            'intensity_multiplier': 1.0  # same intensity
        },
        'week2': {
            'volume_multiplier': 0.6,   # -40% volume  
            'intensity_multiplier': 0.85  # -15% intensity
        }
    }
```

#### 7. Learning & Personalization
```python
class UserLearningModel:
    def __init__(self, user_id):
        self.user_id = user_id
        self.rir_bias = 2.0  # Most users underestimate
        self.recovery_multipliers = defaultdict(lambda: 1.0)
        self.exercise_relationships = {}
        
    def update_rir_bias(self, predicted_reps, actual_reps):
        """Learn user's RIR accuracy"""
        error = predicted_reps - actual_reps
        learning_rate = 0.1
        
        self.rir_bias = self.rir_bias * (1 - learning_rate) + error * learning_rate
        
    def update_recovery_rate(self, muscle_group, performance_delta, days_rest):
        """Learn individual recovery patterns"""
        expected_recovery = 1 - exp(-days_rest / 48)  # Standard 48h tau
        actual_recovery = performance_delta
        
        adjustment = actual_recovery / expected_recovery
        self.recovery_multipliers[muscle_group] *= adjustment ** 0.1
        
    def learn_exercise_transfer(self, exercise1, exercise2, correlation):
        """Learn relationships between exercises"""
        self.exercise_relationships[(exercise1, exercise2)] = correlation
```

---

## User Interface & Experience

### Design Principles
1. **Spreadsheet-Inspired**: Clean tables, data-dense but organized
2. **Minimal Clicks**: Most actions in 1-2 taps
3. **Real-time Feedback**: Instant volume calculations
4. **Progressive Disclosure**: Simple for beginners, powerful for advanced
5. **Mobile-First**: Optimized for gym use with sweaty hands

### Key Screens

#### 1. Dashboard
```
┌─────────────────────────────────────┐
│ GymGenius        [≡]  [👤]  [⚙️]   │
├─────────────────────────────────────┤
│                                     │
│ Next Workout: Push A                │
│ ┌─────────────────────────────┐     │
│ │ 📊 This Week                │     │
│ │ Sessions: ███░ 3/4          │     │
│ │ Volume: ████████ 85%        │     │
│ │ Fatigue: ████░░ Moderate    │     │
│ └─────────────────────────────┘     │
│                                     │
│ [Start Workout →]                   │
│                                     │
│ Recent Progress                     │
│ ┌─────────────────────────────┐     │
│ │ Bench: ↗ +2.5kg this week  │     │
│ │ Squat: → Plateau detected   │     │
│ │ Dead:  ↗ +5kg this week    │     │
│ └─────────────────────────────┘     │
└─────────────────────────────────────┘
```

#### 2. Workout Execution
```
┌─────────────────────────────────────┐
│ ← Push A          Exercise 1/6      │
├─────────────────────────────────────┤
│                                     │
│ BARBELL BENCH PRESS                 │
│ Primary: Chest                      │
│                                     │
│ Set 2 of 4                          │
│ ┌─────────────────────────────┐     │
│ │ 💡 AI Recommends:           │     │
│ │                             │     │
│ │ 80 kg × 8 reps @ 2 RIR     │     │
│ │                             │     │
│ │ Confidence: 85%            │     │
│ └─────────────────────────────┘     │
│                                     │
│ ┌─────────┬─────────┬─────────┐     │
│ │ Weight  │ Reps    │ RIR     │     │
│ ├─────────┼─────────┼─────────┤     │
│ │ 80 ▼    │ [    ]  │ [  ] ▼  │     │
│ └─────────┴─────────┴─────────┘     │
│                                     │
│ [Log Set]                           │
│                                     │
│ Previous Sets:                      │
│ Set 1: 80kg × 9 @ 2 RIR ✓         │
│                                     │
│ Rest Timer: 1:32 ████████░░        │
└─────────────────────────────────────┘
```

#### 3. Plan Builder
```
┌─────────────────────────────────────────────────────┐
│ Plan Builder                    [Save] [Preview]    │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Week Overview                                       │
│ ┌───────┬───────┬───────┬───────┬───────┬─────┐   │
│ │ Mon   │ Tue   │ Wed   │ Thu   │ Fri   │ Sat │   │
│ ├───────┼───────┼───────┼───────┼───────┼─────┤   │
│ │ Push A│ Rest  │ Pull A│ Rest  │ Legs  │Push B│  │
│ │ 6 ex  │       │ 5 ex  │       │ 7 ex  │ 5 ex│   │
│ └───────┴───────┴───────┴───────┴───────┴─────┘   │
│                                                     │
│ Monday - Push A        [+ Add Exercise]             │
│ ┌─────────────────────┬──────┬──────┬─────┐       │
│ │ Exercise            │ Sets │ Reps │ RIR │       │
│ ├─────────────────────┼──────┼──────┼─────┤       │
│ │ Bench Press         │ 4    │ 6-8  │ 1-2 │ [⋮]  │
│ │ DB Shoulder Press   │ 3    │ 8-10 │ 2   │ [⋮]  │
│ │ Cable Lateral Raise │ 4    │12-15 │ 1   │ [⋮]  │
│ └─────────────────────┴──────┴──────┴─────┘       │
│                                                     │
│ Volume Analysis           Status                    │
│ ┌──────────────────────────────────────────┐       │
│ │ Chest:     ████████████░░░░ 16 sets ✓   │       │
│ │ Shoulders: ████████░░░░░░░░ 12 sets ✓   │       │
│ │ Triceps:   ██████████░░░░░░ 14 sets ✓   │       │
│ └──────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

#### 4. Analytics Dashboard
```
┌─────────────────────────────────────────────┐
│ Progress Analytics    [1M] [3M] [6M] [1Y]  │
├─────────────────────────────────────────────┤
│                                             │
│ Estimated 1RM Progress                      │
│ ┌─────────────────────────────────────┐     │
│ │     Bench Press                     │     │
│ │ 120┤    ╱─────                     │     │
│ │ 100┤ ╱──                           │     │
│ │  80┤─                              │     │
│ │    └────────────────────────       │     │
│ │      Jan   Feb   Mar   Apr         │     │
│ └─────────────────────────────────────┘     │
│                                             │
│ Weekly Volume by Muscle                     │
│ ┌─────────────────────────────────────┐     │
│ │ Chest     ████████████ 18 sets     │     │
│ │ Back      ██████████████ 20 sets   │     │
│ │ Shoulders ████████ 12 sets         │     │
│ │ Arms      ██████ 10 sets           │     │
│ │ Legs      ████████████████ 24 sets │     │
│ └─────────────────────────────────────┘     │
│                                             │
│ Training Consistency                        │
│ ┌─────────────────────────────────────┐     │
│ │ Last 4 weeks: 15/16 sessions ✓    │     │
│ │ Adherence: 94%                     │     │
│ └─────────────────────────────────────┘     │
└─────────────────────────────────────────────┘
```

### Mobile Adaptations
- **Swipe navigation** between exercises
- **Large touch targets** (minimum 44px)
- **Collapsible sections** for smaller screens
- **Landscape mode** for detailed tables
- **Quick input mode** with number pad
- **Gesture controls** (swipe to complete set)

### Accessibility Features
- **High contrast mode**
- **Adjustable font sizes**
- **Screen reader support**
- **Color-blind friendly palettes**
- **Voice input** for hands-free logging

---

## Technical Architecture

### Frontend Stack
- **Framework**: React with TypeScript
- **State Management**: Zustand or Redux Toolkit
- **UI Library**: Custom components with Tailwind CSS
- **Charts**: Recharts or D3.js for visualizations
- **PWA**: Service workers for offline functionality
- **Testing**: Jest + React Testing Library

### Backend Stack
- **Runtime**: Node.js with Express or Fastify
- **Language**: TypeScript
- **Database**: PostgreSQL with Prisma ORM
- **Caching**: Redis for session data
- **Queue**: Bull for background jobs
- **Authentication**: JWT with refresh tokens
- **API**: RESTful with OpenAPI documentation

### Infrastructure
- **Hosting**: AWS or Google Cloud Platform
- **Container**: Docker with Kubernetes
- **CI/CD**: GitHub Actions
- **Monitoring**: Sentry for errors, Datadog for metrics
- **Analytics**: Mixpanel for user behavior
- **CDN**: CloudFront for static assets

### AI/ML Components
- **Recommendation Engine**: Python microservice
- **ML Framework**: TensorFlow or PyTorch
- **Model Storage**: S3 with versioning
- **Training Pipeline**: Airflow or Kubeflow
- **A/B Testing**: Split.io or Optimizely

---

## Data Models & Schema

### Core Entities

#### Users
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    
    -- Profile
    name VARCHAR(255),
    birth_date DATE,
    gender VARCHAR(20),
    
    -- Settings
    goal_slider DECIMAL(3,2) DEFAULT 0.5, -- 0=hypertrophy, 1=strength
    experience_level VARCHAR(20) DEFAULT 'intermediate',
    unit_system VARCHAR(10) DEFAULT 'metric',
    
    -- Gym equipment
    available_plates JSONB DEFAULT '{"kg": [1.25, 2.5, 5, 10, 20]}',
    
    -- Learning model
    rir_bias DECIMAL(3,1) DEFAULT 2.0,
    recovery_multipliers JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Exercises
```sql
CREATE TABLE exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    
    -- Categorization
    category VARCHAR(50), -- push/pull/squat/hinge/carry/isolation
    equipment VARCHAR(50), -- barbell/dumbbell/cable/machine/bodyweight
    difficulty VARCHAR(20), -- beginner/intermediate/advanced
    
    -- Muscle involvement (0-1 scale)
    primary_muscles JSONB NOT NULL, -- {"chest": 1.0}
    secondary_muscles JSONB, -- {"triceps": 0.5, "front_delts": 0.3}
    
    -- Metadata
    fatigue_rating VARCHAR(20), -- low/medium/high
    technique_notes TEXT,
    common_mistakes TEXT[],
    video_url VARCHAR(500),
    
    -- User-created
    created_by UUID REFERENCES users(id),
    is_public BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Workout Plans
```sql
CREATE TABLE workout_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    
    -- Schedule
    days_per_week INTEGER,
    plan_length_weeks INTEGER,
    
    -- Configuration
    goal_focus DECIMAL(3,2), -- 0=hypertrophy, 1=strength
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE plan_days (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES workout_plans(id),
    day_number INTEGER NOT NULL,
    name VARCHAR(100),
    
    UNIQUE(plan_id, day_number)
);

CREATE TABLE plan_exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_day_id UUID REFERENCES plan_days(id),
    exercise_id UUID REFERENCES exercises(id),
    order_index INTEGER NOT NULL,
    
    -- Prescription
    sets INTEGER NOT NULL,
    rep_range_low INTEGER,
    rep_range_high INTEGER,
    target_rir INTEGER,
    rest_seconds INTEGER,
    
    notes TEXT,
    
    UNIQUE(plan_day_id, order_index)
);
```

#### Workout Logging
```sql
CREATE TABLE workouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    plan_day_id UUID REFERENCES plan_days(id),
    
    -- Session data
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    session_rpe INTEGER CHECK (session_rpe BETWEEN 1 AND 10),
    
    -- Context
    fatigue_level INTEGER CHECK (fatigue_level BETWEEN 1 AND 10),
    sleep_hours DECIMAL(3,1),
    stress_level INTEGER CHECK (stress_level BETWEEN 1 AND 10),
    
    notes TEXT
);

CREATE TABLE workout_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id UUID REFERENCES workouts(id),
    exercise_id UUID REFERENCES exercises(id),
    set_number INTEGER NOT NULL,
    
    -- Recommendation
    recommended_weight DECIMAL(5,2),
    recommended_reps INTEGER,
    recommended_rir INTEGER,
    confidence_score DECIMAL(3,2),
    
    -- Actual performance
    actual_weight DECIMAL(5,2),
    actual_reps INTEGER,
    actual_rir INTEGER,
    
    -- Timing
    rest_before_seconds INTEGER,
    completed_at TIMESTAMP,
    
    -- Metadata
    form_rating INTEGER CHECK (form_rating BETWEEN 1 AND 5),
    notes TEXT,
    
    UNIQUE(workout_id, exercise_id, set_number)
);
```

#### Analytics & Learning
```sql
CREATE TABLE estimated_1rm_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    exercise_id UUID REFERENCES exercises(id),
    
    estimated_1rm DECIMAL(5,2),
    calculation_method VARCHAR(50), -- epley/brzycki/lombardi
    confidence DECIMAL(3,2),
    
    calculated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE muscle_recovery_patterns (
    user_id UUID REFERENCES users(id),
    muscle_group VARCHAR(50),
    recovery_tau_hours DECIMAL(4,1),
    last_updated TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (user_id, muscle_group)
);

CREATE TABLE plateau_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    exercise_id UUID REFERENCES exercises(id),
    
    detected_at TIMESTAMP DEFAULT NOW(),
    plateau_duration_days INTEGER,
    protocol_applied VARCHAR(50), -- overload_deload/exercise_variation/etc
    resolved_at TIMESTAMP
);
```

### Indexes
```sql
-- Performance indexes
CREATE INDEX idx_workouts_user_date ON workouts(user_id, started_at DESC);
CREATE INDEX idx_workout_sets_exercise ON workout_sets(exercise_id, completed_at DESC);
CREATE INDEX idx_1rm_history_lookup ON estimated_1rm_history(user_id, exercise_id, calculated_at DESC);

-- Analytics indexes
CREATE INDEX idx_sets_for_volume ON workout_sets(workout_id, exercise_id);
CREATE INDEX idx_workouts_date_range ON workouts(user_id, started_at);
```

---

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)
**Goal**: Basic functional app with core training loop

#### Week 1-2: Project Setup & Auth
- [ ] Initialize monorepo structure
- [ ] Set up TypeScript, ESLint, Prettier
- [ ] Configure Docker development environment
- [ ] Implement authentication (signup/login/JWT)
- [ ] Create user profile management
- [ ] Set up CI/CD pipeline

#### Week 3-4: Core Data Models
- [ ] Design and implement database schema
- [ ] Create exercise database with 50 starter exercises
- [ ] Build basic CRUD APIs
- [ ] Implement workout logging endpoints
- [ ] Create simple linear progression algorithm
- [ ] Build MVP frontend with basic screens

**Deliverable**: Users can sign up, browse exercises, log workouts with manual weight entry

### Phase 2: Intelligence Layer (Weeks 5-8)
**Goal**: Implement the adaptive algorithm

#### Week 5-6: Smart Recommendations
- [ ] Implement Extended Epley 1RM calculation
- [ ] Build weight recommendation engine
- [ ] Add plate rounding logic
- [ ] Create RIR learning system
- [ ] Implement goal slider interpolation

#### Week 7-8: Adaptive Features
- [ ] Build fatigue tracking model
- [ ] Implement trend detection
- [ ] Add plateau detection
- [ ] Create deload protocols
- [ ] Build confidence scoring

**Deliverable**: App provides intelligent weight recommendations that improve over time

### Phase 3: Plan Builder & Analytics (Weeks 9-12)
**Goal**: Complete workout planning and progress tracking

#### Week 9-10: Plan Creation
- [ ] Build drag-and-drop plan builder UI
- [ ] Implement volume analysis calculations
- [ ] Create muscle group frequency tracking
- [ ] Add exercise selection recommendations
- [ ] Build plan templates library
- [ ] Implement flexible scheduling system

#### Week 11-12: Analytics Dashboard
- [ ] Create progress visualization charts
- [ ] Build strength curve tracking
- [ ] Implement volume heatmaps
- [ ] Add performance trend analysis
- [ ] Create exportable reports
- [ ] Build achievement system

**Deliverable**: Full-featured app with planning tools and comprehensive analytics

### Phase 4: Polish & Scale (Weeks 13-16)
**Goal**: Production-ready application

#### Week 13-14: Performance & Testing
- [ ] Optimize database queries
- [ ] Implement caching layer
- [ ] Add comprehensive error handling
- [ ] Create unit and integration tests
- [ ] Perform load testing
- [ ] Security audit

#### Week 15-16: Launch Preparation
- [ ] Create onboarding flow
- [ ] Build admin dashboard
- [ ] Implement analytics tracking
- [ ] Create documentation
- [ ] Set up monitoring and alerts
- [ ] Beta testing with real users

**Deliverable**: Production-ready application with <100ms response times

### Phase 5: Advanced Features (Post-Launch)
- [ ] Coach portal for trainers
- [ ] Program marketplace
- [ ] Social features
- [ ] Wearable integrations
- [ ] AI form checking
- [ ] Nutrition tracking

---

## Future Vision & Extensions

### Immediate Extensions (3-6 months)
1. **Mobile Apps**: Native iOS/Android for better performance
2. **Apple Watch App**: Quick logging during workouts
3. **Barcode Scanner**: For plate loading assistance
4. **Voice Commands**: "Log 8 reps at 2 RIR"
5. **Export Features**: PDF reports, CSV data

### Medium-term Features (6-12 months)
1. **AI Form Coach**: Video analysis for form correction
2. **Community Features**: Share workouts, find gym buddies
3. **Trainer Platform**: Manage multiple clients
4. **Integration Hub**: Sync with MyFitnessPal, Fitbit, etc.
5. **Advanced Analytics**: ML-powered insights

### Long-term Vision (1-2 years)
1. **Gym Partnerships**: QR codes on equipment
2. **VR Training**: Form practice in virtual environment
3. **Genetic Integration**: Personalization based on DNA
4. **Research Platform**: Contribute anonymized data
5. **Global Leaderboards**: Compete worldwide

---

## Key Success Metrics

### User Engagement
- **DAU/MAU ratio**: Target >60%
- **Session length**: Average 15-30 minutes
- **Workouts per week**: Average 3-4
- **Retention**: 80% month-1, 60% month-3

### Algorithm Performance
- **Recommendation accuracy**: <5% deviation from optimal
- **Plateau detection**: 90% sensitivity
- **User satisfaction**: >4.5/5 for recommendations
- **Strength gains**: 20% better than control group

### Business Metrics
- **Conversion rate**: 5% free to paid
- **CAC**: <$50
- **LTV**: >$300
- **Churn**: <5% monthly

---

## Technical Specifications for Implementation

### API Design Principles
1. **RESTful architecture** with consistent naming
2. **Versioned endpoints** (v1, v2)
3. **Pagination** for all list endpoints
4. **Rate limiting** per user and IP
5. **Comprehensive error codes**

### Example API Endpoints
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/refresh

GET    /api/v1/exercises
POST   /api/v1/exercises
GET    /api/v1/exercises/:id
PUT    /api/v1/exercises/:id

GET    /api/v1/workouts
POST   /api/v1/workouts
GET    /api/v1/workouts/:id
POST   /api/v1/workouts/:id/sets

GET    /api/v1/recommendations/next-set
POST   /api/v1/recommendations/feedback

GET    /api/v1/analytics/progress
GET    /api/v1/analytics/volume
GET    /api/v1/analytics/trends
```

### Security Considerations
1. **HTTPS everywhere**
2. **Input validation** on all endpoints
3. **SQL injection protection** via parameterized queries
4. **XSS prevention** with content security policies
5. **Rate limiting** to prevent abuse
6. **Data encryption** at rest and in transit

### Performance Requirements
1. **Response time**: <200ms for 95th percentile
2. **Uptime**: 99.9% availability
3. **Concurrent users**: Support 10,000+
4. **Data retention**: 2 years of workout history
5. **Backup**: Daily automated backups

---

## Competitive Analysis

### Direct Competitors
1. **Strong**: Good tracking, poor recommendations
2. **FitBod**: Decent AI, limited customization
3. **JEFIT**: Feature-rich, overwhelming UI
4. **Hevy**: Clean UI, basic features

### Our Advantages
1. **True AI adaptation** vs simple progression
2. **Science-based** recommendations
3. **Beautiful, intuitive UI**
4. **Flexible scheduling**
5. **Transparent reasoning**

### Moat
1. **Learning algorithm** improves with each user
2. **Network effects** from community features
3. **Data advantage** from user base
4. **Brand** as the "smart" workout app

---

## Marketing & Launch Strategy

### Target Audience
1. **Primary**: Intermediate lifters wanting to optimize
2. **Secondary**: Beginners needing guidance
3. **Tertiary**: Advanced lifters hitting plateaus

### Launch Plan
1. **Beta**: 100 users from fitness forums
2. **Soft launch**: 1,000 users with referral codes
3. **Public launch**: Product Hunt, Reddit r/fitness
4. **Growth**: Influencer partnerships, content marketing

### Pricing Strategy
- **Free tier**: Basic tracking, 3 exercises/day
- **Pro ($9.99/mo)**: Full AI, unlimited exercises
- **Coach ($29.99/mo)**: Multi-client management
- **Enterprise**: Custom pricing for gyms

---

## Risk Analysis & Mitigation

### Technical Risks
1. **Algorithm accuracy**: Extensive testing, gradual rollout
2. **Scaling issues**: Cloud architecture, caching
3. **Data loss**: Regular backups, redundancy

### Business Risks
1. **Competition**: Fast feature development
2. **User acquisition cost**: Focus on retention
3. **Regulatory**: GDPR compliance from day 1

### Mitigation Strategies
1. **A/B testing** everything
2. **User feedback loops**
3. **Iterative development**
4. **Conservative financial planning**

---

## Conclusion

GymGenius represents a paradigm shift in workout tracking - from passive logging to active coaching. By combining exercise science with machine learning, we create a system that truly adapts to each user's unique physiology and goals.

The key innovation is making complex training decisions simple. Users don't need to understand periodization, volume landmarks, or fatigue management - they just need to show up and lift what the app recommends.

With a clear technical roadmap, strong scientific foundation, and focus on user experience, GymGenius is positioned to become the definitive training companion for serious lifters worldwide.

---

## Appendices

### A. Exercise Database Starter List
Core compound movements across all major patterns, with detailed muscle involvement percentages and fatigue ratings.

### B. Scientific References
Complete bibliography of research papers supporting our algorithm design, particularly around mechanical tension, volume landmarks, and recovery patterns.

### C. UI/UX Mockups
High-fidelity designs for all major screens, showing information architecture and interaction patterns.

### D. Database Migration Scripts
SQL scripts for initial schema creation and sample data population.

### E. Algorithm Pseudocode
Detailed implementation notes for all core algorithms, with example calculations.

### F. Testing Scenarios
Comprehensive test cases covering edge cases, user journeys, and algorithm validation.

---

*This document represents the complete vision for GymGenius. It serves as the single source of truth for all development decisions and should be updated as the product evolves.*
