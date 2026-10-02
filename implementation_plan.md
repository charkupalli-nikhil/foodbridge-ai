# Phase 7: Impact Analytics & Reporting - Implementation Plan

Thank you for providing the complete master roadmap! Based on this document and the work we've already completed together in this repository, here is our actual progress:
- **Phase 2 (Trust & Verification)**: ✔️ Completed (Receiver verification, Admin approvals).
- **Phase 3 (Anti-Fake System)**: ✔️ Completed (Duplicate image hashing, qualitative feedback).
- **Phase 4 & 5 (AI & Smart Matching)**: ✔️ Completed (AI priority engine, capacity matching).
- **Phase 6 (Notification System)**: ✔️ Completed (Real-time in-app notification bell).

This means we are officially ready to begin **Phase 7: Impact Analytics & Reporting**! 🚀

## Goal Description

Enhance the existing dashboards for Donors, NGOs, and Admins to include rich, data-driven analytics and visual charts. All metrics will be dynamically calculated from the live MongoDB database to accurately reflect the platform's real-world impact (meals redistributed, food waste reduced).

## Proposed Changes

### Backend API Updates

#### [MODIFY] `backend/main.py`
We will add new analytics endpoints or expand the existing dashboard data endpoints to serve aggregated metrics:
- **Global Metrics / Admin Analytics**: Add aggregations for `donations per month`, `food categories breakdown`, `total meals recovered`, `total active users`, etc.
- **Donor Analytics**: Add aggregations for `total meals donated by user`, `completed donations`, etc.
- **NGO Analytics**: Add aggregations for `total meals received by user`, `completed collections`, etc.

### Frontend Dashboard Updates

#### [MODIFY] `frontend/package.json`
- Install a charting library (e.g., `recharts` or `chart.js`) to render beautiful, responsive graphs.

#### [MODIFY] `frontend/src/pages/DonorDashboard.jsx`
- Introduce a "My Impact" section displaying a summary card of total meals donated.
- Add a chart visualizing their donation history over time.

#### [MODIFY] `frontend/src/pages/NgoDashboard.jsx`
- Introduce a "Community Impact" section displaying total meals received.
- Add a pie chart visualizing the types of food categories they've collected.

#### [MODIFY] `frontend/src/pages/AdminDashboard.jsx`
- Completely revamp the "Platform Statistics" section.
- Add a Line Chart for "Donations per Month".
- Add a Bar Chart for "Food Categories".
- Add metrics for "Verified Organizations" vs "Pending", and "Suspended Donors".

## Open Questions
1. **Charting Library**: I plan to use `recharts` (a very popular and clean React charting library) for the frontend graphs. Does this sound good to you?
2. **Metrics Formula**: For "Meals Redistributed" / "Meals Donated", I will sum up the `servings` field of all donations marked as `Collected`. Does that align with your expectation?

## Verification Plan
- Create test donations and mark them as collected.
- Verify that the charts correctly update and render real data on all three dashboards.
- Ensure no fabricated statistics are used, adhering strictly to Phase 7 requirements.
