# FuelRoute Pro — UI/UX Architecture & Product Blueprint

## 1. Product Vision & Introduction

### Why FuelRoute Pro?
Fuel is one of the largest variable costs for independent drivers, small fleets, and long-distance travelers. While generic map apps can get you from Point A to Point B, they do not understand **fuel economics**. 

**FuelRoute Pro** is a purpose-built, intelligent routing platform that bridges the gap between navigation and financial optimization. By combining real-time route geometry with a proprietary database of fuel prices, our advanced greedy-optimization algorithm calculates the absolute most cost-effective places to refuel along your specific journey. 

We built this application to democratize enterprise-level logistics technology. Whether you are an owner-operator trying to maximize your margin, a family planning a cross-country road trip, or a developer integrating routing into your own platform, FuelRoute Pro provides enterprise-grade accuracy with consumer-grade simplicity.

---

## 2. Target Audience & User Personas

1. **The Independent Owner-Operator (Primary)**: Drives an 18-wheeler. Margins are tight. Needs to know exactly where to stop to save $50–$100 per trip. Values transparency and offline reliability.
2. **The Fleet Dispatcher (Secondary)**: Manages 10–50 vehicles. Needs to plan routes in the office and push them to drivers. Values CSV exports, vehicle profiles, and API access.
3. **The Road-Trip Planner (Tertiary)**: Drives a personal vehicle or RV. Wants to minimize vacation costs. Values a clean, easy-to-use map interface and clear, jargon-free explanations.

---

## 3. Global Navigation & Layout System

The application uses a responsive, top-navigation layout that adapts based on authentication state.

### A. Public Navigation (Unauthenticated)
*   **Logo**: "⛽ FuelRoute Pro" (Links to `/`)
*   **Links**: Home | About Dev | Support Us
*   **Action**: `[ Login / Register ]` (Primary Button)

### B. Authenticated Navigation (Logged In)
*   **Logo**: "⛽ FuelRoute Pro" (Links to `/dashboard`)
*   **Links**: Dashboard | Application | Files | Settings | Account
*   **Utility**: `[ About Dev ]` | `[ Support Us ]` | `[ Logout ]`
*   **User Avatar**: Dropdown for quick account access.

---

## 4. Page-by-Page Architecture

### A. Homepage (`/`)
*   **Hero Section**: 
    *   Headline: *"Plan the cheapest, most efficient fuel stops on any U.S. route."*
    *   Subheadline: *"Save up to 15% on fuel costs with our intelligent, algorithm-driven route optimizer."*
    *   CTA Buttons: `[ Try a Demo Route ]` (Scrolls to form) | `[ Create Free Account ]`
*   **Real-Time Platform Stats (Data Tiles)**: *(Fetched via lightweight API endpoint)*
    1.  **Verified Stations**: "300+ Actively Monitored Fuel Stops"
    2.  **Routes Optimized**: "1,240+ Routes Calculated" *(Tracks DB count)*
    3.  **Avg. Savings**: "~$45 Saved per 500-mile trip" *(Based on algorithmic baseline)*
    4.  **System Speed**: "< 2.0s Average Response Time"
*   **"How It Works" Section**: 3-step visual guide (1. Enter Route, 2. Algorithm Analyzes, 3. Save Money).
*   **Footer**: Standard links, OpenStreetMap/OSRM attribution, Privacy Policy, Terms of Service.

### B. Authentication Pages (`/login`, `/register`)
*   **Layout**: Centered card on a subtle, branded background.
*   **Top Nav**: `[ ← Back to Home ]` | `About Dev` | `Support Us`
*   **Features**: Email/Password fields, "Remember Me" checkbox, "Forgot Password?" link, and clear error messaging for invalid credentials.

### C. About Dev (`/about`)
*   **Top Nav**: `[ ← Back ]` | `Login/Register` | `Support Us`
*   **Content**: 
    *   Professional profile card for **Siddhant (S-V-J)**.
    *   Bio: "Backend Django Engineer passionate about building efficient, real-world logistics tools that solve actual economic problems."
    *   Links: GitHub (https://github.com/S-V-J), Email (stjl093@gmail.com).
    *   **Mission Statement**: "To democratize route optimization, making enterprise-level fuel savings accessible to every driver on the road."

### D. Support Us (`/support`)
*   **Top Nav**: `[ ← Back ]` | `Login/Register` | `About Dev`
*   **Content**: 
    *   "Why Your Support Matters": Explains that donations cover server hosting, API rate limits, and continuous dataset expansion.
    *   **GitHub Sponsors**: Embedded iframe (`<iframe src="https://github.com/sponsors/S-V-J/card"...>`).
    *   **Alternative Support**: "Star the repository on GitHub" button, "Share with a fellow driver" social links.

---

### E. Dashboard (`/dashboard`) *(Authenticated)*
*   **Welcome Header**: "Welcome back, [User Name]."
*   **Personal Stats Tiles**: 
    *   Total Routes Planned
    *   Estimated Total Savings ($)
    *   Total Gallons Optimized
*   **Recent Activity Table**: Columns: Date, Start, Finish, Total Cost, Actions (`[ View ]`, `[ Export CSV ]`).
*   **Quick Action**: Large, prominent `[ + Plan New Route ]` button.

### F. Application / Route Planner (`/app`) *(Authenticated)*
*   **Layout**: Split-screen (Left: Controls, Right: Map).
*   **Left Sidebar (Controls)**:
    *   **Vehicle Profile Dropdown**: Select saved vehicle (e.g., "Default 10 MPG", "My Semi-Truck").
    *   **Inputs**: Start Location, Finish Location.
    *   **Advanced Options (Collapsible)**: Range, MPG, Starting Fuel, Buffer Miles.
    *   **Action**: `[ Calculate Optimal Route ]` (with HTMX loading spinner).
*   **Right Area (Map & Results)**:
    *   **Interactive Leaflet Map**: Shows route polyline, start/end pins, and numbered fuel stop markers.
    *   **Itinerary Panel (Below or beside map)**: 
        *   Summary: Total Distance, Total Cost, Total Gallons.
        *   Step-by-step list: "Stop 1: RICKY ROCKETS (Mile 0.2) - Buy 31.6 gal @ $3.10 = $97.91".
    *   **Export Actions**: `[ Download GPX ]`, `[ Export CSV ]`, `[ Print Summary ]`.

### G. Files / Data Manager (`/files`) *(Authenticated/Admin)*
*   **Purpose**: Interface to upload new CSV datasets to update the fuel price database.
*   **Features**:
    *   Drag-and-drop file upload zone (accepts `.csv`).
    *   Pre-flight validation: Checks for required columns (`OPIS Truckstop ID`, `Retail Price`, etc.).
    *   Processing Status: Progress bar or status badge (Pending, Processing, Success, Failed).
    *   Upload History: Table of past uploads with timestamps and record counts.

### H. Settings (`/settings`) *(Authenticated)*
*   **Default Vehicle Profile**: Set default MPG, Tank Capacity, and Starting Fuel to auto-populate the planner.
*   **Routing Preferences**: Checkboxes for "Avoid Tolls", "Prefer Major Highways" (Note: These can be passed as parameters to advanced routing providers if configured).
*   **API Configuration**: Input fields for users to add their own OpenRouteService or GraphHopper API keys to bypass public demo rate limits.

### I. Account (`/account`) *(Authenticated)*
*   **Profile**: Edit Name and Email.
*   **Security**: Change Password form.
*   **Danger Zone**: "Delete Account" button with a strict type-to-confirm modal.

---

## 5. Advanced & Research-Backed Features

To elevate this from a "script" to a "professional product," the following features will be integrated:

### 1. Integrated AI Assistant (Floating Chatbot)
*   **UI**: A subtle, floating chat icon in the bottom-right corner of the `/app` and `/dashboard` pages.
*   **Functionality**: A rule-based, context-aware assistant (can be upgraded to LLM later).
*   **Sample Interactions**:
    *   *User*: "Why did it choose Ricky Rockets?"
    *   *Bot*: "Ricky Rockets was selected because it is within your 25-mile buffer and offers the lowest price ($3.10/gal) before your vehicle's range depletes at mile 316."
    *   *User*: "How do I change my MPG?"
    *   *Bot*: "You can update your default MPG in the [Settings Page](/settings) or adjust it for a single trip in the 'Advanced Options' on the planner."

### 2. Progressive Web App (PWA) Readiness
*   **Implementation**: Add a `manifest.json` and a basic Service Worker.
*   **Benefit**: Allows users to "Install" the website to their phone or desktop home screen. Crucially, it enables **offline caching** of the last planned route, so drivers can still view their itinerary in areas with poor cell service.

### 3. Multi-Vehicle Profiles
*   Users can save multiple configurations (e.g., "Freightliner: 7 MPG, 150 gal" vs. "Ford Transit: 18 MPG, 25 gal"). The optimizer instantly recalculates the entire route when a profile is swapped.

### 4. Dark Mode Support
*   **Implementation**: CSS variables (`:root` vs `[data-theme="dark"]`) with a toggle in the Settings or Navigation bar. Essential for drivers using the app at night.

### 5. Accessibility (a11y) First Design
*   All form inputs will have explicit `<label>` associations.
*   Color contrast ratios will meet WCAG AA standards (e.g., ensuring the blue route line is visible to color-blind users by adding a subtle pattern or high-contrast border).
*   Full keyboard navigability for the map and form.

---

## 6. Real-Time Data Tiles Strategy

To make the homepage feel alive and trustworthy, we will implement a lightweight Django view (`/api/v1/stats/`) that returns:
1.  `station_count`: `Station.objects.count()`
2.  `total_plans`: `RoutePlan.objects.count()`
3.  `avg_savings`: A hardcoded, researched baseline (e.g., "$45") or a calculated average from a sample of recent plans.
4.  `avg_response_time`: Tracked via Django middleware or a simple cache metric.

These will be fetched via HTMX or Alpine.js on page load to display a subtle "counting up" animation, enhancing the professional feel.

---

## 7. Next Steps for Implementation

Once this architecture is approved, we will execute in the following order:

1.  **Phase 8.1**: Implement the Global Navigation, Base Templates, and the new Homepage (`/`) with Data Tiles.
2.  **Phase 8.2**: Build the Authentication system (Login/Register) and the `About` / `Support` pages.
3.  **Phase 8.3**: Upgrade the existing Route Planner (`/app`) into the split-screen Dashboard layout with Vehicle Profiles.
4.  **Phase 8.4**: Implement the Files/Data Manager and Settings pages.
5.  **Phase 8.5**: Integrate the Floating AI Chatbot widget and PWA manifest.

---
*Document Version: 1.0 | Last Updated: August 2026*