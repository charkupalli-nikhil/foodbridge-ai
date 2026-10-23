# FoodBridge AI

### Smart Surplus Food Recovery and NGO Coordination Platform

FoodBridge AI is a full-stack web application designed to reduce food waste by connecting food donors such as restaurants, college canteens and event organisers with NGOs that can collect and distribute surplus food to communities in need.

The platform provides secure role-based dashboards for **Food Donors**, **NGO Partners** and **Administrators**, enabling complete donation tracking from listing creation to successful collection.

> Current Version: **Phase 9 (Final Version)** - Fully operational B.Tech Final Year Project.
> Features Included: Google Gemini AI integration, OpenStreetMap Geospatial Distance Matching, Live Real-time Analytics via Recharts, and premium Glassmorphism UI/UX.

---

## Live Application

| Service                   | Link                                                                       |
| ------------------------- | -------------------------------------------------------------------------- |
| Frontend Website          | [Open FoodBridge AI](https://foodbridge-ai-frontend.onrender.com)          |
| Backend Health API        | [Check Backend Status](https://foodbridge-ai-wu9l.onrender.com/api/health) |
| Swagger API Documentation | [View API Docs](https://foodbridge-ai-wu9l.onrender.com/docs)              |

---

## Problem Statement

Large quantities of usable surplus food are wasted every day by restaurants, canteens and event organisers, while NGOs and community organisations may not receive timely information about nearby available food.

FoodBridge AI solves this coordination problem by providing a digital platform where:

* Donors can quickly post available surplus food.
* NGOs can view and accept available pickup requests.
* Collected meals can be tracked transparently.
* Administrators can monitor platform users, donations and recovery impact.

---

## Key Features

### Food Donor Portal

Food donors can:

* Register and securely login.
* Add new surplus food donations.
* Enter food category, quantity, preparation details, pickup deadline and location.
* View all of their submitted donations.
* Monitor donation status as `Active`, `Accepted` or `Collected`.
* View meals successfully recovered through their donations.

### NGO Partner Portal

NGO partners can:

* Register and securely login.
* View active food donations posted by donors.
* Accept available pickup requests.
* View assigned pickups.
* Mark accepted donations as collected.
* Track meals collected through the platform.

### Administrator Portal

Administrators can:

* Login through a privately created admin account.
* View platform-level statistics.
* Monitor total users, donors and NGO partners.
* View active, accepted and completed donations.
* View total meals recovered.
* View all platform users and donation activity.

### AI-Assisted Food Safety Screening & Layered Originality Check

FoodBridge AI integrates **Google Gemini** multimodal vision aligned with FSSAI guidance alongside a multi-layered authenticity engine to verify food safety and originality:
* **Live Camera Capture Flow:** Guided camera viewfinder captures fresh photos directly from the donor's device with server-signed 10-minute capture session tokens.
* **EXIF Recency Verification:** Extracts camera metadata and validates that photos were captured recently (<= 30 minutes).
* **Perceptual Hashing & Duplicate Detection:** Computes SHA-256, pHash, and dHash fingerprints against past database records with Hamming distance thresholding (<= 6) to detect reused photos or downloaded stock images.
* **Geospatial Capture Verification:** Compares device capture GPS coordinates against the declared pickup location via Haversine calculation, flagging discrepancies > 1.0 km.
* **Visual Authenticity Cues:** Gemini vision inspects for stock photo watermarks, digital screen moiré patterns, and artificial studio staging.
* **Fail-Closed Authenticity Enforcement:** Submissions scored as "Likely Internet Image" are blocked with HTTP 422 and deduct donor trust score points.

### Geospatial Smart Matching & Logistics Feasibility

* **OpenStreetMap Nominatim Geocoding:** Auto-populates GeoJSON `Point` coordinates for donor pickup locations and receiver organization facilities, backed by an in-memory 1 req/sec throttle and a 90-day MongoDB cache.
* **Real Road Distance & Travel ETA:** Combines great-circle Haversine distance with an urban circuity multiplier (1.3x) and a 25 km/h urban velocity model to compute accurate road travel times.
* **Time Feasibility Engine:** Evaluates whether a receiver can travel to the donor before the `pickupDeadline`. If the ETA exceeds the time remaining, an urgency alert is triggered.
* **Deterministic Proximity Match:** Generates a 0–100% proximity score ($100 \times \max(0, 1 - \text{roadDist}/25)$) and allows sorting by Best Match, Distance, Urgency, or Newest.
* **Targeted Proximity Notifications:** Dispatches distance-aware alerts (e.g. `(4.2 km away)`) to verified receivers within the configured notification radius.

### Privacy-Preserving Donation Cards

* **Clean Priority Presentation:** Donation cards display neutral priority indicators (`Priority: High / Medium / Low`) without exposing internal algorithmic parameters or raw confidence percentages to public users.
* **Role-Based Inspection:** Administrators retain full visibility of model features, confidence scores, and perceptual hash metadata for safety compliance and audits.

---

## Technology Stack

### Frontend

| Technology       | Purpose                                               |
| ---------------- | ----------------------------------------------------- |
| React.js         | Component-based user interface                        |
| Vite             | Frontend development and production build tool        |
| React Router DOM | Client-side navigation and protected dashboard routes |
| CSS              | Custom responsive page and dashboard styling          |
| Fetch API        | Communication with backend REST APIs                  |

### Backend

| Technology       | Purpose                                |
| ---------------- | -------------------------------------- |
| Python           | Backend programming language           |
| FastAPI          | REST API development framework         |
| Uvicorn          | ASGI server used to run FastAPI        |
| Pydantic         | Request validation and response models |
| PyMongo          | MongoDB database connection            |
| JWT              | Secure authentication tokens           |
| Password Hashing | Secure password storage                |

### Database and Deployment

| Technology         | Purpose                                 |
| ------------------ | --------------------------------------- |
| MongoDB Atlas      | Cloud database for users and donations  |
| Render Web Service | Deployment of FastAPI backend           |
| Render Static Site | Deployment of React frontend            |
| GitHub             | Version control and source-code hosting |

---

## System Architecture

```text
+----------------------------+
|        User Browser        |
| Donor / NGO / Administrator|
+-------------+--------------+
              |
              | HTTPS Requests
              v
+----------------------------+
|     React + Vite Frontend  |
| Hosted on Render Static Site|
+-------------+--------------+
              |
              | REST API + JWT Token
              v
+----------------------------+
|      FastAPI Backend       |
| Hosted on Render Web Service|
+-------------+--------------+
              |
              | PyMongo Connection
              v
+----------------------------+
|       MongoDB Atlas        |
| Users and Donations Storage|
+----------------------------+
```

---

## User Roles and Workflows

### Donor Workflow

```text
Register / Login
      ↓
Create Donation Listing
      ↓
System Assigns Priority
      ↓
Donation Becomes Available to NGOs
      ↓
NGO Accepts Pickup
      ↓
NGO Marks Food as Collected
      ↓
Meals Saved Updated on Dashboard
```

### NGO Workflow

```text
Register / Login
      ↓
View Available Donations
      ↓
Accept Suitable Donation
      ↓
View Assigned Pickup
      ↓
Collect Food
      ↓
Mark Donation as Collected
```

### Administrator Workflow

```text
Private Admin Account Login
      ↓
View Platform Dashboard
      ↓
Monitor Users and Donations
      ↓
Track Completed Pickups
      ↓
Track Total Meals Recovered
```

---

## Authentication and Security

FoodBridge AI uses role-based authentication and authorization.

### Security Features

* User passwords are stored as secure hashes, not plain text.
* JWT access tokens are generated after successful login.
* Protected API routes require a valid access token.
* Role validation prevents unauthorised dashboard access.
* Donor-only actions cannot be performed by NGOs or administrators.
* NGO-only collection actions cannot be performed by donors.
* Administrator routes are protected separately.
* Environment secrets are stored outside GitHub using `.env` files and Render environment variables.
* CORS allows requests only from approved frontend origins.

### Protected Roles

| Role  | Access                                               |
| ----- | ---------------------------------------------------- |
| Donor | Add and monitor personal donations                   |
| NGO   | Accept and collect available donations               |
| Admin | Monitor all platform users, donations and statistics |

---

## Application Pages

| Route              | Page Description                              |
| ------------------ | --------------------------------------------- |
| `/`                | Landing page describing the platform          |
| `/register`        | Registration page for donors and NGO partners |
| `/login`           | Secure login page                             |
| `/donor-dashboard` | Food donor dashboard                          |
| `/ngo-dashboard`   | NGO partner dashboard                         |
| `/admin-dashboard` | Administrator monitoring dashboard            |

---

### AI Food Inspection & Quality Assessment (Google GenAI SDK)

FoodBridge AI integrates **Google Gemini 2.5 Flash** via the official `google-genai` SDK for automated visual food screening strictly aligned with **FSSAI** guidance:
* **Anti-Fake Screening:** Rejects non-food items (laptops, walls, electronic devices, memes, screenshots, empty plates).
* **Description Match Verification:** Confirms that the uploaded food photo visually matches the donor's declared title and category.
* **Fail-Closed Architecture:** If confidence is below 0.60 or verification cannot be performed, the system marks the inspection as `Unverified` and prevents unverified donation creation.
* **FSSAI Disclaimer:** Clearly identifies screening as an AI-assisted visual check, not a laboratory certification.

### In-App Notification System

A persistent MongoDB `notifications` collection with compound and 30-day TTL indexes:
* Automated alerts dispatched on new donation listings, partial pickups, complete acceptance, and collection completion.
* Unread badge counter with automatic background polling every 20 seconds.
* Direct deep-linking with card focus and pulse highlighting.

### Partial Acceptance & Claims Architecture

Supports multi-organization food recovery for large donations:
* A dedicated `claims` collection tracks which organization accepted what quantity.
* Atomic `$inc` and `$gte` MongoDB operations prevent race conditions and over-allocation.
* Life cycle: `Active` ➔ `Partially Accepted` ➔ `Accepted` ➔ `Collected`.
* Receiver capacity limits prevent over-claiming beyond handling capabilities.

---

## REST API Endpoints

### Authentication APIs

| Method | Endpoint             | Purpose                          |
| ------ | -------------------- | -------------------------------- |
| `POST` | `/api/auth/register` | Register donor or NGO account    |
| `POST` | `/api/auth/login`    | Login user and receive JWT token |
| `GET`  | `/api/auth/me`       | Get currently authenticated user |

### Donation & Verification APIs

| Method  | Endpoint                               | Purpose                                          | Access |
| ------- | -------------------------------------- | ------------------------------------------------ | ------ |
| `POST`  | `/api/donations/verify-image`          | Pre-submission AI food inspection screening      | Donor  |
| `GET`   | `/api/donations/my`                    | View donor's submitted donations and claims      | Donor  |
| `POST`  | `/api/donations`                       | Create a new donation with verified food image   | Donor  |
| `GET`   | `/api/donations/available`             | View active & partially accepted donations       | NGO    |
| `GET`   | `/api/donations/recommended`           | View AI-prioritised and geo-matched donations    | NGO    |
| `GET`   | `/api/donations/my-pickups`            | View assigned NGO pickup claims                  | NGO    |
| `PATCH` | `/api/donations/{donation_id}/accept`  | Accept/claim servings from an available donation | NGO    |
| `PATCH` | `/api/claims/{claim_id}/collect`       | Mark specific claim quantity as collected        | NGO    |
| `PATCH` | `/api/donations/{donation_id}/collect` | Backward-compatible collection completion        | NGO    |

### Notification APIs

| Method  | Endpoint                               | Purpose                                      | Access        |
| ------- | -------------------------------------- | -------------------------------------------- | ------------- |
| `GET`   | `/api/notifications`                   | Fetch user notifications (supports limit)    | Authenticated |
| `GET`   | `/api/notifications/unread-count`      | Get unread notification badge count          | Authenticated |
| `PATCH` | `/api/notifications/{id}/read`         | Mark a single notification as read           | Authenticated |
| `PATCH` | `/api/notifications/read-all`          | Mark all user notifications as read          | Authenticated |

### Statistics APIs

| Method | Endpoint                | Purpose                            | Access |
| ------ | ----------------------- | ---------------------------------- | ------ |
| `GET`  | `/api/statistics/donor` | View donor recovery & claim stats  | Donor  |
| `GET`  | `/api/statistics/ngo`   | View NGO collection & claim stats  | NGO    |
| `GET`  | `/api/admin/statistics` | View complete platform statistics  | Admin  |
| `GET`  | `/api/public/stats`     | Public aggregate recovery counters | Public |

### Admin APIs

| Method | Endpoint                            | Purpose                            |
| ------ | ----------------------------------- | ---------------------------------- |
| `GET`  | `/api/admin/statistics`             | Platform-level metrics             |
| `GET`  | `/api/admin/users`                  | View registered platform accounts  |
| `GET`  | `/api/admin/donations`              | View all donations and claims      |
| `GET`  | `/api/admin/verification/pending`   | Review pending NGO applications    |
| `PUT`  | `/api/admin/verification/{id}/approve` | Approve NGO account             |
| `PUT`  | `/api/admin/verification/{id}/reject`  | Reject NGO application          |

---

## Database Architecture

Data is stored in MongoDB Atlas across four indexed collections:

### 1. `users` Collection
Stores user profiles, credentials, verification documents, and trust ratings.

### 2. `donations` Collection
Tracks food listings, remaining servings, AI inspection verdicts, and pickup deadlines.
* Compound index: `status`, `remainingServings`, `createdAt`.
* TTL index: `pickupDeadline` (expires unaccepted Active listings after deadline).

### 3. `claims` Collection
Tracks partial acceptance and multi-organization claims:
```json
{
  "_id": "ObjectId",
  "donationId": "Donation ID string",
  "receiverUserId": "NGO User ID string",
  "receiverOrgName": "Hope Foundation",
  "quantity": 30,
  "status": "Accepted | Collected",
  "createdAt": "Timestamp",
  "collectedAt": "Timestamp (optional)"
}
```

### 4. `notifications` Collection
Stores asynchronous in-app notifications:
```json
{
  "_id": "ObjectId",
  "recipientUserId": "User ID string",
  "type": "new_donation | donation_accepted | partial_remaining | pickup_collected",
  "title": "Title string",
  "message": "Notification message string",
  "donationId": "Donation ID string (optional)",
  "read": false,
  "createdAt": "Timestamp"
}
```
* Compound Index: `recipientUserId` (1), `read` (1), `createdAt` (-1).
* TTL Index: `createdAt` with `expireAfterSeconds: 2592000` (auto-purges after 30 days).

---

## Project Folder Structure

```text
foodbridge-ai
├── backend
│   ├── .env.example
│   ├── create_admin.py
│   ├── database.py
│   ├── main.py
│   ├── requirements.txt
│   └── security.py
│
├── frontend
│   ├── public
│   ├── src
│   │   ├── pages
│   │   │   ├── AdminDashboard.jsx
│   │   │   ├── AdminDashboard.css
│   │   │   ├── Auth.css
│   │   │   ├── Dashboard.css
│   │   │   ├── DonorDashboard.jsx
│   │   │   ├── Home.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── NgoDashboard.jsx
│   │   │   ├── NgoDashboard.css
│   │   │   └── Register.jsx
│   │   ├── App.jsx
│   │   ├── config.js
│   │   ├── index.css
│   │   └── main.jsx
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
│
├── .gitignore
└── README.md
```

---

## Local Installation and Setup

### Prerequisites

Install the following tools:

* Node.js and npm
* Python
* Git
* MongoDB Atlas account
* VS Code

### 1. Clone the Repository

```bash
git clone https://github.com/charkupalli-nikhil/foodbridge-ai.git
cd foodbridge-ai
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
```

Activate the virtual environment on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside `backend`:

```env
MONGODB_URI=YOUR_MONGODB_ATLAS_CONNECTION_STRING
MONGODB_DATABASE=foodbridge_ai
JWT_SECRET=YOUR_SECURE_RANDOM_JWT_SECRET
```

Run the backend:

```bash
fastapi dev main.py
```

Backend API will run locally at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend will run locally at:

```text
http://localhost:5173
```

---

## Creating an Administrator Account

Public registration is available only for donors and NGO partners. Administrator accounts must be created privately from the backend.

From the `backend` folder, run:

```bash
python create_admin.py
```

Enter administrator details when prompted. The administrator can then login from the frontend using the **Administrator** role option.

---

## Environment Variables

### Backend Environment Variables

Create `backend/.env` locally:

```env
MONGODB_URI=YOUR_MONGODB_ATLAS_CONNECTION_STRING
MONGODB_DATABASE=foodbridge_ai
JWT_SECRET=YOUR_LONG_RANDOM_SECRET
```

### Frontend Environment Variables

Create `frontend/.env` when required:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

For production deployment:

```env
VITE_API_BASE_URL=https://foodbridge-ai-wu9l.onrender.com/api
```

> Never upload real `.env` files containing credentials or secrets to GitHub.

---

## Deployment

### Backend Deployment

The FastAPI backend is deployed on Render as a Web Service.

| Setting        | Value                                          |
| -------------- | ---------------------------------------------- |
| Root Directory | `backend`                                      |
| Build Command  | `pip install -r requirements.txt`              |
| Start Command  | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

Production backend environment variables:

```text
MONGODB_URI
MONGODB_DATABASE
JWT_SECRET
PYTHON_VERSION
```

### Frontend Deployment

The React/Vite frontend is deployed on Render as a Static Site.

| Setting           | Value           |
| ----------------- | --------------- |
| Root Directory    | `frontend`      |
| Build Command     | `npm run build` |
| Publish Directory | `dist`          |

Production frontend environment variable:

```env
VITE_API_BASE_URL=https://foodbridge-ai-wu9l.onrender.com/api
```

React Router rewrite configuration:

| Source | Destination   | Action  |
| ------ | ------------- | ------- |
| `/*`   | `/index.html` | Rewrite |

---



---

## Testing Summary

The deployed platform has been tested for the following workflows:

| Test Case                         | Result  |
| --------------------------------- | ------- |
| Donor/NGO registration and login  | Working |
| Gemini AI Image Verification      | Working |
| Geospatial Distance Calculation   | Working |
| NGO acceptance of donation        | Working |
| Analytics Dashboard Rendering     | Working |
| MongoDB realistic data seeding    | Working |

---

## Project Status

```text
Current Status: 100% Complete (Final B.Tech Presentation Version).

Fully Implemented & Polished:
- Premium Glassmorphism UI/UX with Modern Typography
- Google Gemini Vision AI Anti-Fake Verification
- OpenStreetMap Location Matching
- Recharts Dashboard Analytics
- MongoDB Aggregation Pipelines
- Production Database Seeding
- Render Live Deployment
```

---

## Author

**Nikhil Charkupalli**
Information Technology Engineering Student

GitHub: [charkupalli-nikhil](https://github.com/charkupalli-nikhil)

---

## Repository

Source Code: [FoodBridge AI GitHub Repository](https://github.com/charkupalli-nikhil/foodbridge-ai)

---

## License

This project is developed for academic, learning and portfolio demonstration purposes.
