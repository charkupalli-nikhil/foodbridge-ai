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

### AI Food Quality & Priority Assessment (Google Gemini)

FoodBridge AI integrates **Google Gemini 1.5 Pro** to automatically verify food images.
* **Anti-Fake System:** Detects if an uploaded image is a real photo of food, rejecting random pictures.
* **Smart Priority:** Evaluates freshness and assigns priority (High, Medium, Low) based on visual packaging and category.

### Geospatial Smart Matching

Instead of generic keyword matching, the system calculates the real Haversine Distance in Kilometres between the Donor and NGO using **OpenStreetMap Nominatim API**, sorting available donations by nearest physical proximity.

### Real-Time Impact Analytics

Using robust MongoDB Aggregation Pipelines and **Recharts**, the platform offers dynamic dashboard charts tracking:
* Donations over time (Line Charts)
* Food category distributions (Pie Charts)
* Complete tracking of total meals redistributed.

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

## REST API Endpoints

### Authentication APIs

| Method | Endpoint             | Purpose                          |
| ------ | -------------------- | -------------------------------- |
| `POST` | `/api/auth/register` | Register donor or NGO account    |
| `POST` | `/api/auth/login`    | Login user and receive JWT token |
| `GET`  | `/api/auth/me`       | Get currently authenticated user |

### Donation APIs

| Method  | Endpoint                               | Purpose                          | Access |
| ------- | -------------------------------------- | -------------------------------- | ------ |
| `GET`   | `/api/donations/my`                    | View donor's submitted donations | Donor  |
| `POST`  | `/api/donations`                       | Create a new donation            | Donor  |
| `GET`   | `/api/donations/available`             | View available active donations  | NGO    |
| `GET`   | `/api/donations/my-pickups`            | View assigned NGO pickups        | NGO    |
| `PATCH` | `/api/donations/{donation_id}/accept`  | Accept an active donation        | NGO    |
| `PATCH` | `/api/donations/{donation_id}/collect` | Mark accepted food as collected  | NGO    |

### Statistics APIs

| Method | Endpoint                | Purpose                           | Access |
| ------ | ----------------------- | --------------------------------- | ------ |
| `GET`  | `/api/statistics/donor` | View donor recovery statistics    | Donor  |
| `GET`  | `/api/statistics/ngo`   | View NGO collection statistics    | NGO    |
| `GET`  | `/api/admin/statistics` | View complete platform statistics | Admin  |

### Admin APIs

| Method | Endpoint                | Purpose                   |
| ------ | ----------------------- | ------------------------- |
| `GET`  | `/api/admin/statistics` | Platform-level metrics    |
| `GET`  | `/api/admin/users`      | View registered accounts  |
| `GET`  | `/api/admin/donations`  | View all donation records |

---

## Database Design

The application stores information in MongoDB Atlas using two primary collections.

### Users Collection

```json
{
  "fullName": "User Name",
  "email": "user@example.com",
  "organisation": "Organisation Name",
  "role": "donor | ngo | admin",
  "location": "Operating Location",
  "contactNumber": "Mobile Number",
  "passwordHash": "Secure Hashed Password",
  "createdAt": "Date and Time"
}
```

### Donations Collection

```json
{
  "foodName": "Vegetable Rice Meal",
  "category": "Cooked Meal",
  "servings": 60,
  "preparationTime": "Prepared 20 minutes ago",
  "pickupDeadline": "Date and Time",
  "location": "Pickup Location",
  "packagingCondition": "Packed in clean covered containers",
  "donorUserId": "Donor Account ID",
  "donorName": "Donor Name",
  "donorOrganisation": "Donor Organisation",
  "priority": "High | Medium | Low",
  "status": "Active | Accepted | Collected",
  "acceptedByUserId": "NGO Account ID",
  "acceptedByName": "NGO Contact Name",
  "acceptedByOrganisation": "NGO Organisation",
  "acceptedAt": "Date and Time",
  "collectedAt": "Date and Time",
  "createdAt": "Date and Time"
}
```

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
