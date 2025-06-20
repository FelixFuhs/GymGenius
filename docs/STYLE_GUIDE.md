# GymGenius Frontend Style Guide

## 1. Introduction

This style guide provides a reference for the visual design language used across the GymGenius web application. Its purpose is to ensure consistency in user interface elements, promote maintainability, and provide a clear set of guidelines for any future development or modifications. The overall aesthetic aims for a clean, modern, and organized appearance, with a "spreadsheet-inspired" feel where data density is required, prioritizing clarity and ease of use.

## 2. Color Palette

The color palette is designed to be clean, accessible, and provide clear visual hierarchy.

|Role                |Color Name    |Hex Code |Usage Examples                              |
|--------------------|--------------|---------|--------------------------------------------|
|**Primary Text**    |Primary Dark  |`#1d1d1f`|Main body text, headings, primary content   |
|**Secondary Text**  |Medium Gray   |`#515154`|Hover states, secondary interactive elements|
|**Tertiary Text**   |Light Gray    |`#86868b`|Placeholder text, captions, disabled states |
|**Accent (Success)**|Success Green |`#30d158`|Success messages, positive indicators       |
|**Accent (Error)**  |Error Red     |`#ff3b30`|Error messages, destructive actions         |
|**Accent (Warning)**|Warning Orange|`#ff9500`|Warning messages, attention states          |
|**Background**      |Off White     |`#fafbfc`|Main page background                        |
|**Surface**         |Pure White    |`#ffffff`|Cards, modals, input fields, content areas  |
|**Border**          |Light Border  |`#e5e5e7`|Borders, dividers, subtle separations       |

## 3. Typography

Consistent typography enhances readability and user experience.

*   **Font Family**: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` (sans-serif stack)
*   **Base Font Size**: `1em` (typically 16px)
*   **Line Height (Body)**: `1.6`

### Headings

| Element | Font Size | Font Weight | Color     | Margin Bottom |
|---------|-----------|-------------|-----------|---------------|
| `h1`    | `2.5em`   | `700`       | `#1d1d1f` | `0.75rem`     |
| `h2`    | `2em`     | `700`       | `#1d1d1f` | `0.75rem`     |
| `h3`    | `1.75em`  | `600`       | `#1d1d1f` | `0.5rem`      |
| `h4`    | `1.5em`   | `600`       | `#1d1d1f` | `0.5rem`      |
| `h5`    | `1.25em`  | `600`       | `#1d1d1f` | `0.5rem`      |
| `h6`    | `1em`     | `600`       | `#1d1d1f` | `0.5rem`      |
*Header H1 (`header > h1`)*: `1.75em`, `700`, `#1d1d1f`, `margin: 0`.

### Text Elements

*   **Body Text (`p`, general text)**: `1em`, `400` weight, `#1d1d1f` color, `line-height: 1.6`.
*   **Labels (`label`)**: `1em` (or `0.95em` in specific contexts like profile forms), `500` weight, `#1d1d1f` color, `margin-bottom: 8px`.
*   **Links (`a`)**: Inherit font size, `400` or `500` weight, `#1d1d1f` color. Hover: `#0056b3`. No text decoration by default, underline on hover for some links (e.g., `.form-link`).
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
    *   Cards, Major Sections: `16px`.
    *   Modals: `20px`.
    *   Tables: `16px`.
    *   Buttons, Inputs, Smaller Elements: `10px`.
    *   Pill-shaped elements (e.g., mesocycle phase items): `15px` or larger.

### Shadows

- Standard Card: `0 1px 3px rgba(0,0,0,0.02), 0 20px 40px rgba(0,0,0,0.015), inset 0 1px 0 rgba(255, 255, 255, 0.7)`
- Elevated/Hover: `0 8px 25px rgba(0,0,0,0.15)` for buttons, `0 6px 20px rgba(0,0,0,0.08)` for secondary
- Modal: `0 32px 64px rgba(0,0,0,0.12), 0 8px 32px rgba(0,0,0,0.08), inset 0 2px 0 rgba(255, 255, 255, 0.8)`

## 6. Glassmorphism & Texture Effects

### Glassmorphism Effects

- **Cards:** `background: radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.8) 0%, rgba(255, 255, 255, 0.95) 50%), linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(250, 251, 252, 0.95) 100%); backdrop-filter: blur(20px);`
- **Buttons (Primary):** `background: linear-gradient(135deg, #1d1d1f 0%, #2d2d30 100%);`
- **Buttons (Secondary):** `background: linear-gradient(135deg, rgba(245, 245, 247, 0.95) 0%, rgba(250, 251, 252, 0.98) 100%); backdrop-filter: blur(10px);`
- **Form Inputs:** `background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(250, 251, 252, 0.98) 100%); backdrop-filter: blur(10px);`

### Sparkle Texture Effects

- **Diamond Dust for Primary Buttons:** Add `::before` pseudo-element with `radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.1) 0%, transparent 2px), radial-gradient(circle at 70% 70%, rgba(255, 255, 255, 0.08) 0%, transparent 1px), radial-gradient(circle at 20% 80%, rgba(255, 255, 255, 0.06) 0%, transparent 1px); background-size: 20px 20px, 30px 30px, 25px 25px;`
- **Special Cards:** Option for `.sparkle` class with animated sparkle background
- **Table Headers:** Subtle sparkle overlay using `::after` pseudo-element

## 7. Component Styling

### Buttons

```css
button, .button {
    cursor: pointer;
    border: none;
    padding: 12px 24px;
    font-size: 1em;
    border-radius: 10px;
    font-weight: 500;
    transition: all 0.3s ease;
    font-family: inherit; /* Will inherit from body or a more specific rule */
}

.button-primary {
    background: linear-gradient(135deg, #1d1d1f 0%, #2d2d30 100%);
    color: white;
    position: relative; /* Needed for pseudo-elements like sparkle */
    overflow: hidden; /* Helps contain pseudo-elements */
}

.button-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.15); /* From new shadow definitions */
}

.button-secondary {
    background: linear-gradient(135deg, rgba(245, 245, 247, 0.95) 0%, rgba(250, 251, 252, 0.98) 100%);
    backdrop-filter: blur(10px); /* From new glassmorphism effects */
    border: 1px solid rgba(229, 229, 231, 0.8); /* New border color */
    /* Note: text color for secondary button not specified, defaults to Primary Dark via inheritance or body style */
}

/* Add notes for other button types if necessary, or remove old ones if they are no longer relevant.
   The prompt focuses on primary and secondary.
   Remove old button classes like .button-error, .button-danger-outline, .button-link, .button-sm if they are not part of the new design.
   The provided CSS only defines `button`, `.button`, `.button-primary`, and `.button-secondary`.
*/
```

### Forms

*   **Labels (`label`)**: `display: block; margin-bottom: 8px; font-weight: 500; color: #1d1d1f;`.
*   **Inputs (`input[type="text"]`, `input[type="password"]`, `input[type="email"]`, `input[type="number"]`, `textarea`, `select`)**:
    *   `width: 100%;` (within their container).
    *   `padding: 12px 16px;`
    *   `border: 1px solid rgba(229, 229, 231, 0.8);` /* Light Border with 0.8 alpha */
    *   `border-radius: 10px;` (consistent with overall border strategy)
    *   `box-sizing: border-box;`
    *   `font-size: 1em;`
    *   `background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(250, 251, 252, 0.98) 100%);` (Glassmorphism effect)
    *   `backdrop-filter: blur(10px);`
    *   `color: #1d1d1f;` (Primary Dark for text)
    *   Placeholder text color: `#86868b;` (Light Gray)
    *   Focus state: `box-shadow: 0 0 0 3px rgba(29, 29, 31, 0.05); outline: none;` (Outline removed for cleaner focus)
*   **`.form-control` class**: Can be added to inputs/selects to explicitly apply the above styling.
*   **Checkboxes**: Standard browser appearance with `vertical-align: middle; margin-right: 5px;`. Labels are `display: inline-block; font-weight: normal; color: #1d1d1f;`.
*   **Form Groups (`form div`)**: Provide basic structure; spacing is primarily managed by label margins and input margins.

### Modals

*   **Overlay (`#onboarding-modal`, generic `.modal`)**: `background-color: rgba(0, 0, 0, 0.6);`.
*   **Content Box (`.modal-content`)**:
    *   `background: #ffffff;`
    *   `padding: 25px;`
    *   `border-radius: 20px;`
    *   `box-shadow: 0 4px 8px rgba(0,0,0,0.1);`
    *   Typically `text-align: center;` (can be overridden).
    *   `max-width: 500px; width: 90%;`.

### Message Boxes / Notifications

Classes: `.success-message`, `.error-message`, `.warning-message` (can also use generic `.message` for success).
*   **Common Styles**: `padding: 10px 15px; border-radius: 10px; margin-bottom: 1rem; display: none;` (toggled by JS).
*   **Success (`.success-message`)**: Light green background (`#d4edda`), dark green text (`#155724`), green border (`#c3e6cb`).
*   **Error (`.error-message`)**: Light red background (`#f8d7da`), dark red text (`#721c24`), red border (`#f5c6cb`).
*   **Warning (`.warning-message`, e.g., Plateau Notifications, Touch Device Message)**: Light yellow background (`#fff3cd`), dark yellow text (`#856404`), yellow border (`#ffeeba`).

### Cards / Panels

Used for dashboard sections, plan builder panels, profile sections, workout execution modules.
*   `background: radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.8) 0%, rgba(255, 255, 255, 0.95) 50%), linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(250, 251, 252, 0.95) 100%);` (Glassmorphism effect)
*   `backdrop-filter: blur(20px);`
*   `border: 1px solid #e5e5e7;` (Light Border)
*   `border-radius: 16px;` (Consistent with overall border strategy)
*   `box-shadow: 0 1px 3px rgba(0,0,0,0.02), 0 20px 40px rgba(0,0,0,0.015), inset 0 1px 0 rgba(255, 255, 255, 0.7);` (Standard Card shadow)
*   Padding:
    *   Standard: `20px`.
    *   Large option (for larger cards/sections): `32px`.
*   May include `::before` pseudo-elements for subtle texture overlays.
*   Special cards can use a `.sparkle` class for an animated sparkle background (see Sparkle Texture Effects).

### Navigation

*   **Header/Footer Links (`header nav a`, `footer nav a`)**:
    *   `color: #1d1d1f;`
    *   `text-decoration: none;`
    *   `padding: 0.5em 1em;`
    *   Hover: `color: #515154;`. Dashboard header links may have `text-decoration: underline;` on hover.
*   **Hamburger Menu (`.hamburger-menu .bar`)**: `background-color: #1d1d1f;`.

### Lists

*   **Generic Lists (`ul`, `ol`)**: Standard browser defaults unless overridden.
*   **Item Lists (`ul.item-list li`)**: Styled as cards (see Cards/Panels for base style: white background, border, padding, radius, shadow). `display: flex; justify-content: space-between; align-items: center;`.
*   **Text Lists (e.g., Plan Details)**: `list-style-position: inside; padding-left: 0;` for `ul`. `li` has `margin-bottom: 5-8px; color: #34495e;`.

### Tables

*   **`table`**:
    *   `width: 100%;`
    *   `margin-bottom: 1rem;`
    *   `border-collapse: separate;` (to allow `border-radius` on the table with cell borders)
    *   `border-spacing: 0;`
    *   `background: linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(250, 251, 252, 0.95) 100%);` (Glassmorphism)
    *   `backdrop-filter: blur(10px);`
    *   `border-radius: 16px;` (Consistent with overall border strategy)
    *   `overflow: hidden;` (Ensures child elements respect the table's border radius)
*   **`th, td`**:
    *   `padding: 16px 20px;`
    *   `text-align: left;`
    *   `border: 1px solid #e5e5e7;` (Light Border)
    *   `vertical-align: top;`
*   **`th` (Table Header Cells)**:
    *   `background-color: transparent;` (Allows table's glassmorphism to show through)
    *   `font-weight: 600;` (Consistent with typography)
    *   `color: #1d1d1f;` (Primary Dark)
    *   Can use `::after` pseudo-element for a subtle sparkle overlay (see Sparkle Texture Effects).
*   **`td` (Table Data Cells)**:
    *   `color: #1d1d1f;` (Primary Dark)
*   Workout Execution Set Tracker Table (`.set-tracker`): `text-align: center` for cells, more specific padding, uppercase headers.

## 8. Utility Classes

*   **`.hidden`**: `display: none !important;`
*   **`.loader`**: Animated loading spinner.
*   **`.form-control`**: Explicitly applies standard input styling.
*   **Button variants**: `.button-primary`, `.button-secondary`, `.button-error`, `.button-danger-outline`, `.button-link`, `.button-sm`.
*   **Message variants**: `.success-message`, `.error-message`, `.warning-message`.

## 9. Responsive Design

The application aims for a responsive design:
*   **Mobile-First Considerations**: Layouts are generally fluid.
*   **Navigation**: Hamburger menu for main navigation on smaller screens (currently in footer, may move to header).
*   **Grid Layouts**: Dashboard and Workout Execution pages use CSS Grid that adapts to screen width (e.g., single column on mobile, multi-column on desktop).
*   **Panel Stacking**: Plan Builder's three-column layout stacks vertically on smaller screens.
*   **Full-Width Elements**: Form inputs and some buttons become full-width on smaller screens for easier interaction.
*   **Table Scrolling**: Workout Execution set logging table allows horizontal scroll on small screens.

## 10. Accessibility

While not exhaustively audited, considerations include:
*   **Contrast Ratios**: Ensure all text and interactive elements meet WCAG AA contrast ratios with the new color palette. Particular attention should be paid to combinations like text on glassmorphic backgrounds. Strive for sufficient contrast, especially for primary content and interactive elements.
*   **Font Readability**: Using clear, sans-serif fonts with adequate sizing and line height.
*   **Readability with Effects**: Verify that glassmorphism effects, textures, and sparkle details do not impede readability or obscure important information. Test with various content types.
*   **Interactive Elements**: Buttons and links are styled to be clearly identifiable. Focus states should be clear and meet accessibility standards (note: default browser states are a baseline but custom focus states like the new input `box-shadow` should also be tested for clarity).
*   **Reduced Motion for Animations**: For sparkle animations and other significant motion effects, provide a mechanism or respect user preferences for reduced motion (e.g., via `prefers-reduced-motion` media query) to prevent discomfort for sensitive users.
*   **Semantic HTML**: Using appropriate HTML5 elements for structure where possible.

This style guide should evolve with the application.
