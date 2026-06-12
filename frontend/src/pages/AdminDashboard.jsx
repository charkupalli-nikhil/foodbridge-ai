import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Dashboard.css";
import "./AdminDashboard.css";

import { API_BASE_URL } from "../config";

const emptyStatistics = {
  totalUsers: 0,
  totalDonors: 0,
  totalNgos: 0,
  totalDonations: 0,
  activeDonations: 0,
  acceptedPickups: 0,
  completedPickups: 0,
  totalMealsRecovered: 0,
};

function getStoredAdmin() {
  const storedUser =
    localStorage.getItem("user") || localStorage.getItem("foodbridge_user");

  if (!storedUser) {
    return {
      fullName: "FoodBridge Administrator",
      organisation: "FoodBridge Control Centre",
      location: "",
    };
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return {
      fullName: "FoodBridge Administrator",
      organisation: "FoodBridge Control Centre",
      location: "",
    };
  }
}

function clearSession() {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("token");
  localStorage.removeItem("user");

  localStorage.removeItem("foodbridge_access_token");
  localStorage.removeItem("foodbridge_user");
  localStorage.removeItem("foodbridge_demo_donor");
  localStorage.removeItem("foodbridge_demo_ngo");
  localStorage.removeItem("foodbridge_demo_admin");
}

function formatDateTime(value) {
  if (!value) {
    return "Not available";
  }

  return new Date(value).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatAiConfidence(value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  const numericValue = Number(value);

  if (Number.isNaN(numericValue)) {
    return "Not available";
  }

  if (Number.isInteger(numericValue)) {
    return `${numericValue}%`;
  }

  return `${numericValue.toFixed(2)}%`;
}

function formatPredictionMethod(value) {
  if (!value) {
    return "Legacy Record";
  }

  if (value === "ml_model") {
    return "ML Model";
  }

  if (value === "rule_fallback") {
    return "Rule Fallback";
  }

  if (value === "rule_fallback_after_ml_error") {
    return "Fallback After ML Error";
  }

  return value
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function getPriorityClass(priority) {
  if (!priority) {
    return "medium";
  }

  return priority.toLowerCase();
}

function getBackendBaseUrl() {
  return API_BASE_URL.replace(/\/api\/?$/, "");
}

function getImageUrl(imagePath) {
  if (!imagePath) {
    return "";
  }

  if (imagePath.startsWith("http")) {
    return imagePath;
  }

  return `${getBackendBaseUrl()}${imagePath}`;
}

function DonationImages({ donation }) {
  if (!donation.foodImage && !donation.packagingImage) {
    return null;
  }

  return (
    <div className="donation-images">
      {donation.foodImage && (
        <div>
          <p className="image-label">Food Image</p>
          <img
            className="donation-image"
            src={getImageUrl(donation.foodImage)}
            alt={donation.foodName}
          />
        </div>
      )}

      {donation.packagingImage && (
        <div>
          <p className="image-label">Packaging Image</p>
          <img
            className="donation-image"
            src={getImageUrl(donation.packagingImage)}
            alt="Packaging"
          />
        </div>
      )}
    </div>
  );
}

async function readErrorMessage(response) {
  try {
    const errorData = await response.json();

    if (typeof errorData.detail === "string") {
      return errorData.detail;
    }

    if (Array.isArray(errorData.detail)) {
      return errorData.detail.map((error) => error.msg).join(" ");
    }

    return "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

function AdminDashboard() {
  const navigate = useNavigate();

  const [admin] = useState(getStoredAdmin);
  const [statistics, setStatistics] = useState(emptyStatistics);
  const [users, setUsers] = useState([]);
  const [donations, setDonations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const authenticatedRequest = useCallback(
    async (endpoint) => {
      const token =
        localStorage.getItem("accessToken") ||
        localStorage.getItem("token") ||
        localStorage.getItem("foodbridge_access_token");

      if (!token) {
        clearSession();
        navigate("/login", { replace: true });
        throw new Error("Please login again to continue.");
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.status === 401) {
        clearSession();
        navigate("/login", { replace: true });
        throw new Error("Your login session has expired. Please login again.");
      }

      return response;
    },
    [navigate]
  );

  const loadDashboardData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage("");

      const [statisticsResponse, usersResponse, donationsResponse] =
        await Promise.all([
          authenticatedRequest("/admin/statistics"),
          authenticatedRequest("/admin/users"),
          authenticatedRequest("/admin/donations"),
        ]);

      if (!statisticsResponse.ok) {
        const message = await readErrorMessage(statisticsResponse);
        throw new Error(message);
      }

      if (!usersResponse.ok) {
        const message = await readErrorMessage(usersResponse);
        throw new Error(message);
      }

      if (!donationsResponse.ok) {
        const message = await readErrorMessage(donationsResponse);
        throw new Error(message);
      }

      const statisticsData = await statisticsResponse.json();
      const userData = await usersResponse.json();
      const donationData = await donationsResponse.json();

      setStatistics(statisticsData);
      setUsers(userData);
      setDonations(donationData);
    } catch (error) {
      setErrorMessage(
        error.message || "Unable to load the administrator dashboard."
      );
    } finally {
      setIsLoading(false);
    }
  }, [authenticatedRequest]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleLogout = () => {
    clearSession();
  };

  return (
    <div className="dashboard-page">
      <aside className="dashboard-sidebar admin-sidebar">
        <Link to="/" className="dashboard-brand">
          <span>🍃</span>

          <div>
            <h2>FoodBridge AI</h2>
            <p>Admin Portal</p>
          </div>
        </Link>

        <nav className="dashboard-navigation">
          <a className="active-dashboard-link" href="#admin-overview">
            <span>▦</span> Overview
          </a>

          <a href="#platform-users">
            <span>👥</span> Platform Users
          </a>

          <a href="#platform-donations">
            <span>🍱</span> Donations
          </a>
        </nav>

        <div className="safety-note">
          <h3>Platform Monitoring</h3>
          <p>
            Monitor registered organisations, donation workflows, AI priority
            predictions, uploaded food images and recovered meal impact across
            the FoodBridge platform.
          </p>
        </div>

        <Link to="/login" className="logout-link" onClick={handleLogout}>
          ← Logout
        </Link>
      </aside>

      <main className="dashboard-main admin-dashboard-main">
        <header className="dashboard-header" id="admin-overview">
          <div>
            <p className="dashboard-label">ADMINISTRATOR DASHBOARD</p>
            <h1>Welcome, {admin.fullName}</h1>
            <span>
              {admin.organisation}
              {admin.location ? ` • ${admin.location}` : ""}
            </span>
          </div>

          <div className="admin-header-actions">
            <button
              className="admin-refresh-button"
              type="button"
              onClick={loadDashboardData}
            >
              Refresh Data
            </button>

            <Link to="/" className="view-home-button">
              View Homepage
            </Link>
          </div>
        </header>

        <section className="demo-information">
          <strong>Secure admin access:</strong> Platform information is loaded
          from MongoDB through administrator-only API endpoints protected by your
          authenticated login token. Donation records include uploaded food
          images, packaging images and machine-learning priority prediction
          details.
        </section>

        {errorMessage && (
          <div className="admin-error-message">{errorMessage}</div>
        )}

        <section className="admin-statistics-grid">
          <article className="statistic-card">
            <div className="stat-icon green">👥</div>

            <div>
              <p>Total Users</p>
              <h2>{statistics.totalUsers}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon blue">🏪</div>

            <div>
              <p>Food Donors</p>
              <h2>{statistics.totalDonors}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon green">🤝</div>

            <div>
              <p>NGO Partners</p>
              <h2>{statistics.totalNgos}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon orange">🍱</div>

            <div>
              <p>Total Donations</p>
              <h2>{statistics.totalDonations}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon green">📍</div>

            <div>
              <p>Active Donations</p>
              <h2>{statistics.activeDonations}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon red">🚚</div>

            <div>
              <p>Accepted Pickups</p>
              <h2>{statistics.acceptedPickups}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon blue">✓</div>

            <div>
              <p>Completed Pickups</p>
              <h2>{statistics.completedPickups}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon orange">🍽️</div>

            <div>
              <p>Meals Recovered</p>
              <h2>{statistics.totalMealsRecovered}</h2>
            </div>
          </article>
        </section>

        <section className="admin-content-grid">
          <article className="admin-panel" id="platform-users">
            <div className="dashboard-section-title">
              <div>
                <p>REGISTERED ACCOUNTS</p>
                <h2>Platform Users</h2>
              </div>

              <span className="listing-count">{users.length} Users</span>
            </div>

            {isLoading ? (
              <p className="admin-loading-text">Loading registered users...</p>
            ) : (
              <div className="admin-table-wrapper">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Role</th>
                      <th>Organisation</th>
                      <th>Location</th>
                      <th>Registered</th>
                    </tr>
                  </thead>

                  <tbody>
                    {users.length === 0 && (
                      <tr>
                        <td colSpan="5" className="admin-empty-row">
                          No registered users found.
                        </td>
                      </tr>
                    )}

                    {users.map((user) => (
                      <tr key={user.id}>
                        <td>
                          <strong>{user.fullName}</strong>
                          <span>{user.email}</span>
                        </td>

                        <td>
                          <span className={`admin-role-pill ${user.role}`}>
                            {user.role}
                          </span>
                        </td>

                        <td>{user.organisation}</td>
                        <td>{user.location}</td>
                        <td>{formatDateTime(user.createdAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </article>

          <article className="admin-panel" id="platform-donations">
            <div className="dashboard-section-title">
              <div>
                <p>DONATION MONITORING</p>
                <h2>All Donations</h2>
              </div>

              <span className="listing-count">
                {donations.length} Listings
              </span>
            </div>

            {isLoading ? (
              <p className="admin-loading-text">Loading donation activity...</p>
            ) : (
              <div className="admin-donation-list">
                {donations.length === 0 && (
                  <div className="admin-empty-state">
                    No food donations have been posted yet.
                  </div>
                )}

                {donations.map((donation) => (
                  <article className="admin-donation-card" key={donation.id}>
                    <div className="admin-donation-top">
                      <div>
                        <h3>{donation.foodName}</h3>
                        <p>
                          {donation.category} • {donation.donorOrganisation}
                        </p>
                      </div>

                      <div className="admin-card-pills">
                        <span
                          className={`priority-pill ${getPriorityClass(
                            donation.priority
                          )}`}
                        >
                          AI Priority: {donation.priority || "Medium"}
                        </span>

                        <span
                          className={`admin-status-pill ${donation.status.toLowerCase()}`}
                        >
                          {donation.status}
                        </span>
                      </div>
                    </div>

                    <DonationImages donation={donation} />

                    <div className="admin-donation-details">
                      <div>
                        <span>Servings</span>
                        <strong>{donation.servings}</strong>
                      </div>

                      <div>
                        <span>Donor</span>
                        <strong>{donation.donorName}</strong>
                      </div>

                      <div>
                        <span>Location</span>
                        <strong>{donation.location}</strong>
                      </div>

                      <div>
                        <span>Posted</span>
                        <strong>{formatDateTime(donation.createdAt)}</strong>
                      </div>

                      <div>
                        <span>Pickup Deadline</span>
                        <strong>
                          {formatDateTime(donation.pickupDeadline)}
                        </strong>
                      </div>

                      <div>
                        <span>Packaging</span>
                        <strong>{donation.packagingCondition}</strong>
                      </div>

                      <div>
                        <span>AI Confidence</span>
                        <strong>
                          {formatAiConfidence(donation.aiConfidence)}
                        </strong>
                      </div>

                      <div>
                        <span>Prediction Method</span>
                        <strong>
                          {formatPredictionMethod(donation.predictionMethod)}
                        </strong>
                      </div>
                    </div>

                    {donation.predictionFeatures && (
                      <p className="admin-assignment-text">
                        ML Features:{" "}
                        <strong>
                          {donation.predictionFeatures
                            .preparation_age_minutes ?? "N/A"}{" "}
                          min prepared age •{" "}
                          {donation.predictionFeatures
                            .pickup_window_minutes ?? "N/A"}{" "}
                          min pickup window • Packaging score{" "}
                          {donation.predictionFeatures.packaging_score ?? "N/A"}
                        </strong>
                      </p>
                    )}

                    {donation.acceptedByOrganisation && (
                      <p className="admin-assignment-text">
                        Assigned NGO:{" "}
                        <strong>{donation.acceptedByOrganisation}</strong>
                      </p>
                    )}
                  </article>
                ))}
              </div>
            )}
          </article>
        </section>
      </main>
    </div>
  );
}

export default AdminDashboard;