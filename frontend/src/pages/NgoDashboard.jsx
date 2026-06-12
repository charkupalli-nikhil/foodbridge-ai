import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Dashboard.css";
import "./NgoDashboard.css";

import { API_BASE_URL } from "../config";

const emptyStatistics = {
  availableDonations: 0,
  acceptedPickups: 0,
  completedPickups: 0,
  highPriorityAvailable: 0,
  mealsCollected: 0,
};

function getStoredUser() {
  const storedUser = localStorage.getItem("foodbridge_user");

  if (!storedUser) {
    return {
      fullName: "NGO Coordinator",
      organisation: "Registered NGO Partner",
      location: "",
    };
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return {
      fullName: "NGO Coordinator",
      organisation: "Registered NGO Partner",
      location: "",
    };
  }
}

function clearSession() {
  localStorage.removeItem("foodbridge_access_token");
  localStorage.removeItem("foodbridge_user");
  localStorage.removeItem("foodbridge_demo_donor");
  localStorage.removeItem("foodbridge_demo_ngo");
}

function formatDateTime(value) {
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

function NgoDashboard() {
  const navigate = useNavigate();

  const [ngo] = useState(getStoredUser);
  const [availableDonations, setAvailableDonations] = useState([]);
  const [myPickups, setMyPickups] = useState([]);
  const [statistics, setStatistics] = useState(emptyStatistics);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const authenticatedRequest = useCallback(
    async (endpoint, options = {}) => {
      const token = localStorage.getItem("foodbridge_access_token");

      if (!token) {
        clearSession();
        navigate("/login", { replace: true });
        throw new Error("Please login again to continue.");
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
          Authorization: `Bearer ${token}`,
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers,
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

      const [availableResponse, pickupsResponse, statisticsResponse] =
        await Promise.all([
          authenticatedRequest("/donations/available"),
          authenticatedRequest("/donations/my-pickups"),
          authenticatedRequest("/statistics/ngo"),
        ]);

      if (!availableResponse.ok) {
        const message = await readErrorMessage(availableResponse);
        throw new Error(message);
      }

      if (!pickupsResponse.ok) {
        const message = await readErrorMessage(pickupsResponse);
        throw new Error(message);
      }

      if (!statisticsResponse.ok) {
        const message = await readErrorMessage(statisticsResponse);
        throw new Error(message);
      }

      const availableData = await availableResponse.json();
      const pickupData = await pickupsResponse.json();
      const statisticsData = await statisticsResponse.json();

      setAvailableDonations(availableData);
      setMyPickups(pickupData);
      setStatistics(statisticsData);
    } catch (error) {
      setErrorMessage(error.message || "Unable to load the NGO dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [authenticatedRequest]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const showSuccessMessage = (message) => {
    setSuccessMessage(message);

    window.setTimeout(() => {
      setSuccessMessage("");
    }, 5000);
  };

  const handleAcceptDonation = async (donationId) => {
    try {
      setProcessingId(donationId);
      setErrorMessage("");

      const response = await authenticatedRequest(
        `/donations/${donationId}/accept`,
        {
          method: "PATCH",
        }
      );

      if (!response.ok) {
        const message = await readErrorMessage(response);
        throw new Error(message);
      }

      showSuccessMessage(
        "Pickup accepted successfully. It is now assigned to your NGO account."
      );

      await loadDashboardData();
    } catch (error) {
      setErrorMessage(error.message || "Unable to accept this pickup.");
    } finally {
      setProcessingId("");
    }
  };

  const handleMarkCollected = async (donationId) => {
    try {
      setProcessingId(donationId);
      setErrorMessage("");

      const response = await authenticatedRequest(
        `/donations/${donationId}/collect`,
        {
          method: "PATCH",
        }
      );

      if (!response.ok) {
        const message = await readErrorMessage(response);
        throw new Error(message);
      }

      showSuccessMessage(
        "Pickup marked as collected. The meals are now included in your impact total."
      );

      await loadDashboardData();
    } catch (error) {
      setErrorMessage(error.message || "Unable to complete this pickup.");
    } finally {
      setProcessingId("");
    }
  };

  const handleLogout = () => {
    clearSession();
  };

  return (
    <div className="dashboard-page">
      <aside className="dashboard-sidebar">
        <Link to="/" className="dashboard-brand">
          <span>🍃</span>

          <div>
            <h2>FoodBridge AI</h2>
            <p>NGO Portal</p>
          </div>
        </Link>

        <nav className="dashboard-navigation">
          <a className="active-dashboard-link" href="#ngo-overview">
            <span>▦</span> Overview
          </a>

          <a href="#available-donations">
            <span>📍</span> Available Food
          </a>

          <a href="#my-pickups">
            <span>🚚</span> My Pickups
          </a>
        </nav>

        <div className="safety-note">
          <h3>AI Priority Support</h3>
          <p>
            FoodBridge AI predicts pickup priority using donation details.
            Your organisation must still verify food condition and safe handling
            before distribution.
          </p>
        </div>

        <Link to="/login" className="logout-link" onClick={handleLogout}>
          ← Logout
        </Link>
      </aside>

      <main className="dashboard-main ngo-dashboard-main">
        <header className="dashboard-header" id="ngo-overview">
          <div>
            <p className="dashboard-label">NGO DASHBOARD</p>
            <h1>Welcome, {ngo.fullName}</h1>
            <span>
              {ngo.organisation}
              {ngo.location ? ` • ${ngo.location}` : ""}
            </span>
          </div>

          <div className="ngo-header-actions">
            <button
              className="refresh-donations-button"
              type="button"
              onClick={loadDashboardData}
            >
              Refresh Donations
            </button>

            <Link to="/" className="view-home-button">
              View Homepage
            </Link>
          </div>
        </header>

        <section className="demo-information">
          <strong>Secure NGO workflow connected:</strong> Available donations
          and assigned pickups are read from MongoDB using your authenticated
          NGO account. New listings include AI priority prediction and
          confidence information.
        </section>

        {successMessage && (
          <div className="ngo-success-message">{successMessage}</div>
        )}

        {errorMessage && (
          <div className="ngo-error-message">{errorMessage}</div>
        )}

        <section className="dashboard-statistics">
          <article className="statistic-card">
            <div className="stat-icon green">🍱</div>

            <div>
              <p>Available Donations</p>
              <h2>{statistics.availableDonations}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon red">⚡</div>

            <div>
              <p>High Priority</p>
              <h2>{statistics.highPriorityAvailable}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon blue">🚚</div>

            <div>
              <p>Accepted Pickups</p>
              <h2>{statistics.acceptedPickups}</h2>
            </div>
          </article>

          <article className="statistic-card">
            <div className="stat-icon orange">🍽️</div>

            <div>
              <p>Meals Collected</p>
              <h2>{statistics.mealsCollected}</h2>
            </div>
          </article>
        </section>

        <section className="ngo-content-grid">
          <article className="ngo-panel" id="available-donations">
            <div className="dashboard-section-title">
              <div>
                <p>AI-PRIORITISED REQUESTS</p>
                <h2>Available Donations</h2>
              </div>

              <span className="listing-count">
                {availableDonations.length} Available
              </span>
            </div>

            {isLoading ? (
              <p className="ngo-loading-text">
                Loading available donations from backend...
              </p>
            ) : (
              <div className="ngo-donation-list">
                {availableDonations.length === 0 && (
                  <div className="ngo-empty-state">
                    <h3>No active donations available</h3>
                    <p>New secure donor listings will appear here.</p>
                  </div>
                )}

                {availableDonations.map((donation) => (
                  <article className="ngo-donation-card" key={donation.id}>
                    <div className="ngo-card-top">
                      <div>
                        <h3>{donation.foodName}</h3>
                        <p>
                          {donation.category} • {donation.donorOrganisation}
                        </p>
                      </div>

                      <span
                        className={`priority-pill ${getPriorityClass(
                          donation.priority
                        )}`}
                      >
                        AI Priority: {donation.priority || "Medium"}
                      </span>
                    </div>

                    <div className="ngo-donation-details">
                      <div>
                        <span>Servings</span>
                        <strong>{donation.servings}</strong>
                      </div>

                      <div>
                        <span>Status</span>
                        <strong className="active-status">
                          {donation.status}
                        </strong>
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

                    <p className="ngo-location">📍 {donation.location}</p>

                    <p className="ngo-deadline">
                      Pickup before: {formatDateTime(donation.pickupDeadline)}
                    </p>

                    {donation.predictionFeatures && (
                      <p className="ngo-deadline">
                        ML features used:{" "}
                        {donation.predictionFeatures.preparation_age_minutes ??
                          "N/A"}{" "}
                        min prepared age •{" "}
                        {donation.predictionFeatures.pickup_window_minutes ??
                          "N/A"}{" "}
                        min pickup window • Packaging score{" "}
                        {donation.predictionFeatures.packaging_score ?? "N/A"}
                      </p>
                    )}

                    <p className="ngo-packaging">
                      <strong>Packaging:</strong> {donation.packagingCondition}
                    </p>

                    <button
                      className="accept-donation-button"
                      type="button"
                      disabled={processingId === donation.id}
                      onClick={() => handleAcceptDonation(donation.id)}
                    >
                      {processingId === donation.id
                        ? "Accepting Pickup..."
                        : "Accept Pickup Request"}
                    </button>
                  </article>
                ))}
              </div>
            )}
          </article>

          <article className="ngo-panel" id="my-pickups">
            <div className="dashboard-section-title">
              <div>
                <p>ASSIGNED TO YOU</p>
                <h2>My Pickups</h2>
              </div>

              <span className="listing-count">
                {myPickups.length} Requests
              </span>
            </div>

            <div className="ngo-donation-list">
              {myPickups.length === 0 && !isLoading && (
                <div className="ngo-empty-state">
                  <h3>No assigned pickups</h3>
                  <p>
                    Accept an available food donation to begin collection.
                  </p>
                </div>
              )}

              {myPickups.map((donation) => (
                <article className="ngo-donation-card" key={donation.id}>
                  <div className="ngo-card-top">
                    <div>
                      <h3>{donation.foodName}</h3>
                      <p>{donation.donorOrganisation}</p>
                    </div>

                    <span
                      className={`workflow-status-pill ${donation.status.toLowerCase()}`}
                    >
                      {donation.status}
                    </span>
                  </div>

                  <div className="ngo-donation-details">
                    <div>
                      <span>Servings</span>
                      <strong>{donation.servings}</strong>
                    </div>

                    <div>
                      <span>AI Priority</span>
                      <strong>{donation.priority || "Medium"}</strong>
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

                  <p className="ngo-location">📍 {donation.location}</p>

                  {donation.predictionFeatures && (
                    <p className="ngo-deadline">
                      ML features used:{" "}
                      {donation.predictionFeatures.preparation_age_minutes ??
                        "N/A"}{" "}
                      min prepared age •{" "}
                      {donation.predictionFeatures.pickup_window_minutes ??
                        "N/A"}{" "}
                      min pickup window • Packaging score{" "}
                      {donation.predictionFeatures.packaging_score ?? "N/A"}
                    </p>
                  )}

                  {donation.acceptedAt && (
                    <p className="ngo-deadline">
                      Accepted: {formatDateTime(donation.acceptedAt)}
                    </p>
                  )}

                  {donation.status === "Accepted" && (
                    <button
                      className="complete-pickup-button"
                      type="button"
                      disabled={processingId === donation.id}
                      onClick={() => handleMarkCollected(donation.id)}
                    >
                      {processingId === donation.id
                        ? "Updating..."
                        : "Mark Collection Completed"}
                    </button>
                  )}
                </article>
              ))}
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}

export default NgoDashboard;