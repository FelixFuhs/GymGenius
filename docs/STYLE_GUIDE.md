# GymGenius Frontend Style Guide

## 1. Introduction

This style guide provides a reference for the visual design language used across the GymGenius web application. Its purpose is to ensure consistency in user interface elements, promote maintainability, and provide a clear set of guidelines for any future development or modifications. The overall aesthetic aims for a clean, modern, and organized appearance, with a "spreadsheet-inspired" feel where data density is required, prioritizing clarity and ease of use.

## 2. Color Palette

The color palette is designed to be clean, accessible, and provide clear visual hierarchy.

| Role              | Color Name      | Hex Code   | Usage Examples                                  |
|-------------------|-----------------|------------|-------------------------------------------------|
| **Primary Text**  | Near Black      | `#212529`  | Main body text, paragraph content.              |
| **Heading Text**  | Dark Blue/Charcoal | `#2c3e50`  | All headings (h1-h6).                         |
| **Secondary Text**| Medium Gray     | `#7f8c8d`  | Subtext, placeholder text, footer text.         |
| **Label Text**    | Dark Slate Gray | `#34495e`  | Form labels, descriptive text.                  |
|                   | Muted Gray      | `#495057`  | Table headers, some secondary info.             |
| **Accent**        | Primary Blue    | `#007bff`  | Links, primary buttons, active indicators.      |
| **Accent Hover**  | Darker Blue     | `#0056b3`  | Hover state for links and primary buttons.      |
| **Background**    | Light Gray      | `#f4f6f8`  | Main page body background.                      |
| **Content Area**  | White           | `#ffffff`  | Cards, modals, input fields, sections.          |
| **Border**        | Light Gray      | `#dee2e6`  | Borders for cards, sections, tables, inputs.    |
|                   | Medium Gray     | `#ced4da`  | Alternative border (e.g., default input border).|
| **Feedback (Success)** | Green      | `#28a745`  | Success messages, positive indicators.          |
|                   | Light Green BG  | `#d4edda`  | Background for success messages.                |
|                   | Dark Green Text | `#155724`  | Text color for success messages.                |
| **Feedback (Error)**   | Red        | `#dc3545`  | Error messages, destructive action buttons.     |
|                   | Light Red BG    | `#f8d7da`  | Background for error messages.                  |
|                   | Dark Red Text   | `#721c24`  | Text color for error messages.                  |
| **Feedback (Warning)** | Yellow     | `#ffc107`  | Warning messages (e.g., plateau notifications). |
|                   | Light Yellow BG | `#fff3cd`  | Background for warning messages.                |
|                   | Dark Yellow Text| `#856404`  | Text color for warning messages.                |
| **Disabled**      | Gray            | `#adb5bd`  | Disabled buttons, inactive elements.            |
| **Subtle BG**     | Very Light Gray | `#f8f9fa`  | Subtle backgrounds (e.g., table headers, AI box).|

## 3. Typography

Consistent typography enhances readability and user experience.

*   **Font Family**: `"Segoe UI", Roboto, Helvetica, Arial, sans-serif` (sans-serif stack)
*   **Base Font Size**: `1em` (typically 16px)
*   **Line Height (Body)**: `1.5`

### Headings

| Element | Font Size | Font Weight | Color     | Margin Bottom |
|---------|-----------|-------------|-----------|---------------|
| `h1`    | `2.5em`   | `600`       | `#2c3e50` | `0.75rem`     |
| `h2`    | `2em`     | `600`       | `#2c3e50` | `0.75rem`     |
| `h3`    | `1.75em`  | `600`       | `#2c3e50` | `0.5rem`      |
| `h4`    | `1.5em`   | `600`       | `#2c3e50` | `0.5rem`      |
| `h5`    | `1.25em`  | `600`       | `#2c3e50` | `0.5rem`      |
| `h6`    | `1em`     | `600`       | `#2c3e50` | `0.5rem`      |
*Header H1 (`header > h1`)*: `1.75em`, `600`, `#2c3e50`, `margin: 0`.

### Text Elements

*   **Body Text (`p`, general text)**: `1em`, `normal` weight, `#212529` color, `line-height: 1.5`.
*   **Labels (`label`)**: `1em` (or `0.95em` in specific contexts like profile forms), `500` weight, `#34495e` color, `margin-bottom: 8px`.
*   **Links (`a`)**: Inherit font size, `normal` or `500` weight, `#007bff` color. Hover: `#0056b3`. No text decoration by default, underline on hover for some links (e.g., `.form-link`).
*   **Small Text (`small`)**: `0.85em` - `0.9em`.

## 4. Spacing

Consistent spacing creates visual rhythm and balance.

*   **General Padding**:
    *   Page `main` content area: `1.5rem` (approx `24px`).
    *   Sections/Cards: `20px` or `25px`.
    *   Smaller elements/inputs: `10px`.
*   **Margins**:
    *   Between elements: `0.5rem` to `1.5rem` (`8px` to `24px`) depending on context and element size.
    *   Headings have specific `margin-bottom` values (see Typography).
*   **Layout Gaps** (e.g., CSS Grid): `20px` to `25px`.

## 5. Borders and Shadows

### Borders

*   **Standard Border**: `1px solid #dee2e6` (for cards, sections, tables).
*   **Input Border**: `1px solid #ced4da` (default for inputs, can also use `#dee2e6`).
*   **Border Radius**:
    *   Cards, Modals, Major Sections: `6px`.
    *   Buttons, Inputs, Smaller Elements: `4px`.
    *   Pill-shaped elements (e.g., mesocycle phase items): `15px` or larger.

### Shadows

*   **Standard Card Shadow**: `0 1px 3px rgba(0,0,0,0.04)` (very subtle).
*   **Elevated Shadow (e.g., on hover or modals)**: `0 4px 8px rgba(0,0,0,0.1)` or `0 2px 4px rgba(0,0,0,0.05)`.
    Shadows should be used sparingly to indicate elevation or interactivity.

## 6. Component Styling

### Buttons

Base `button` style includes `cursor: pointer; border: 1px solid transparent; padding: 10px 15px; font-size: 1em; border-radius: 4px; font-weight: 500;`.

| Class                   | Background      | Text Color | Border Color    | Hover Background | Hover Border    | Notes                                      |
|-------------------------|-----------------|------------|-----------------|------------------|-----------------|--------------------------------------------|
| `.button-primary`       | `#007bff`       | `white`    | `#007bff`       | `#0056b3`        | `#0056b3`       | Primary actions.                           |
| `.button-secondary`     | `#6c757d`       | `white`    | `#6c757d`       | `#5a6268`        | `#545b62`       | Secondary actions.                         |
| `.button-error`         | `#dc3545`       | `white`    | `#dc3545`       | `#c82333`        | `#bd2130`       | Destructive actions (e.g., delete).        |
| `.button-danger-outline`| `transparent`   | `#dc3545`  | `#dc3545`       | `#dc3545`        | `#dc3545`       | (Hover text becomes white) Less prominent destructive. |
| `.button-link`          | `transparent`   | `#007bff`  | `none`          | `transparent`    | `none`          | (Hover text `#0056b3`, underline) Link-like. |
| `.button-sm`            | (Inherits base) | (Inherits) | (Inherits)      | (Inherits)       | (Inherits)      | `padding: 5px 10px; font-size: 0.875em;`     |

*   **Disabled State**: Buttons use `background-color: #adb5bd; cursor: not-allowed;` when disabled.
*   **Button with Loader**: `<span class="loader"></span>` can be placed inside a button.

### Forms

*   **Labels (`label`)**: `display: block; margin-bottom: 8px; font-weight: 500; color: #34495e;`.
*   **Inputs (`input[type="text"]`, `input[type="password"]`, `input[type="email"]`, `input[type="number"]`, `textarea`, `select`)**:
    *   `width: 100%;` (within their container).
    *   `padding: 10px;`
    *   `border: 1px solid #ced4da;`
    *   `border-radius: 4px;`
    *   `box-sizing: border-box;`
    *   `font-size: 1em;`
    *   `background-color: #ffffff;`
*   **`.form-control` class**: Can be added to inputs/selects to explicitly apply the above styling.
*   **Checkboxes**: Standard browser appearance with `vertical-align: middle; margin-right: 5px;`. Labels are `display: inline-block; font-weight: normal;`.
*   **Form Groups (`form div`)**: Provide basic structure; spacing is primarily managed by label margins and input margins.

### Modals

*   **Overlay (`#onboarding-modal`, generic `.modal`)**: `background-color: rgba(0, 0, 0, 0.6);`.
*   **Content Box (`.modal-content`)**:
    *   `background: #ffffff;`
    *   `padding: 25px;`
    *   `border-radius: 6px;`
    *   `box-shadow: 0 4px 8px rgba(0,0,0,0.1);`
    *   Typically `text-align: center;` (can be overridden).
    *   `max-width: 500px; width: 90%;`.

### Message Boxes / Notifications

Classes: `.success-message`, `.error-message`, `.warning-message` (can also use generic `.message` for success).
*   **Common Styles**: `padding: 10px 15px; border-radius: 4px; margin-bottom: 1rem; display: none;` (toggled by JS).
*   **Success (`.success-message`)**: Light green background (`#d4edda`), dark green text (`#155724`), green border (`#c3e6cb`).
*   **Error (`.error-message`)**: Light red background (`#f8d7da`), dark red text (`#721c24`), red border (`#f5c6cb`).
*   **Warning (`.warning-message`, e.g., Plateau Notifications, Touch Device Message)**: Light yellow background (`#fff3cd`), dark yellow text (`#856404`), yellow border (`#ffeeba`).

### Cards / Panels

Used for dashboard sections, plan builder panels, profile sections, workout execution modules.
*   `background-color: #ffffff;`
*   `border: 1px solid #dee2e6;`
*   `border-radius: 6px;`
*   `box-shadow: 0 1px 3px rgba(0,0,0,0.04);`
*   `padding: 20px;` (or `25px` for larger dashboard sections).

### Navigation

*   **Header/Footer Links (`header nav a`, `footer nav a`)**:
    *   `color: #007bff;`
    *   `text-decoration: none;`
    *   `padding: 0.5em 1em;`
    *   Hover: `color: #0056b3;`. Dashboard header links may have `text-decoration: underline;` on hover.
*   **Hamburger Menu (`.hamburger-menu .bar`)**: `background-color: #2c3e50;`.

### Lists

*   **Generic Lists (`ul`, `ol`)**: Standard browser defaults unless overridden.
*   **Item Lists (`ul.item-list li`)**: Styled as cards (see Cards/Panels for base style: white background, border, padding, radius, shadow). `display: flex; justify-content: space-between; align-items: center;`.
*   **Text Lists (e.g., Plan Details)**: `list-style-position: inside; padding-left: 0;` for `ul`. `li` has `margin-bottom: 5-8px; color: #34495e;`.

### Tables

*   **`table`**: `width: 100%; border-collapse: collapse; margin-bottom: 1rem;`.
*   **`th, td`**: `padding: 0.75rem; text-align: left; border: 1px solid #dee2e6; vertical-align: top;`.
*   **`th`**: `background-color: #f8f9fa; font-weight: 600; color: #495057;`.
*   Workout Execution Set Tracker Table (`.set-tracker`): `text-align: center` for cells, more specific padding, uppercase headers.

## 7. Utility Classes

*   **`.hidden`**: `display: none !important;`
*   **`.loader`**: Animated loading spinner.
*   **`.form-control`**: Explicitly applies standard input styling.
*   **Button variants**: `.button-primary`, `.button-secondary`, `.button-error`, `.button-danger-outline`, `.button-link`, `.button-sm`.
*   **Message variants**: `.success-message`, `.error-message`, `.warning-message`.

## 8. Responsive Design

The application aims for a responsive design:
*   **Mobile-First Considerations**: Layouts are generally fluid.
*   **Navigation**: Hamburger menu for main navigation on smaller screens (currently in footer, may move to header).
*   **Grid Layouts**: Dashboard and Workout Execution pages use CSS Grid that adapts to screen width (e.g., single column on mobile, multi-column on desktop).
*   **Panel Stacking**: Plan Builder's three-column layout stacks vertically on smaller screens.
*   **Full-Width Elements**: Form inputs and some buttons become full-width on smaller screens for easier interaction.
*   **Table Scrolling**: Workout Execution set logging table allows horizontal scroll on small screens.

## 9. Accessibility

While not exhaustively audited, considerations include:
*   **Color Contrast**: Striving for sufficient contrast between text and background colors, especially for primary content and interactive elements.
*   **Font Readability**: Using clear, sans-serif fonts with adequate sizing and line height.
*   **Interactive Elements**: Buttons and links are styled to be clearly identifiable. Focus states should be default browser states unless specifically overridden.
*   **Semantic HTML**: Using appropriate HTML5 elements for structure where possible.

This style guide should evolve with the application.
