import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";
import { API_BASE_URL } from "../config";
import "./Dashboard.css";
import "./NgoDashboard.css";
import NotificationBell from "../components/NotificationBell";

const emptyStatistics = {
  availableDonations: 0,
  acceptedPickups: 0,
  completedPickups: 0,
  highPriorityAvailable: 0,
  mealsCollected: 0,
};

function getStoredUser() {
  const storedUser =
    localStorage.getItem("user") || localStorage.getItem("foodbridge_user");

  if (!storedUser) {
    return {
      fullName: "Receiver Coordinator",
      organisation: "Registered Receiver Organization",
      organizationType: "Receiver",
      location: "",
    };
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return {
      fullName: "Receiver Coordinator",
      organisation: "Registered Receiver Organization",
      organizationType: "Receiver",
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

function NgoDashboard() {
  const navigate = useNavigate();

  const [ngo] = useState(getStoredUser);
  const [availableDonations, setAvailableDonations] = useState([]);
  const [recommendedDonations, setRecommendedDonations] = useState([]);
  const [myPickups, setMyPickups] = useState([]);
  const [statistics, setStatistics] = useState(emptyStatistics);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const authenticatedRequest = useCallback(
    async (endpoint, options = {}) => {
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
      
      if (ngo?.verificationStatus !== "verified") {
        setIsLoading(false);
        return;
      }

      const [availableResponse, recommendedResponse, pickupsResponse, statisticsResponse] =
        await Promise.all([
          authenticatedRequest("/donations/available"),
          authenticatedRequest("/donations/recommended"),
          authenticatedRequest("/donations/my-pickups"),
          authenticatedRequest("/statistics/ngo"),
        ]);

      if (!availableResponse.ok) {
        const message = await readErrorMessage(availableResponse);
        throw new Error(message);
      }

      if (!recommendedResponse.ok) {
        const message = await readErrorMessage(recommendedResponse);
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
      const recommendedData = await recommendedResponse.json();
      const pickupData = await pickupsResponse.json();
      const statisticsData = await statisticsResponse.json();

      setAvailableDonations(availableData);
      setRecommendedDonations(recommendedData);
      setMyPickups(pickupData);
      setStatistics(statisticsData);
    } catch (error) {
      setErrorMessage(error.message || "Unable to load the receiver dashboard.");
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
        "Pickup accepted successfully. It is now assigned to your receiver account."
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

  const handleRateDonation = async (donationId, rating) => {
    try {
      setProcessingId(donationId);
      setErrorMessage("");

      const response = await authenticatedRequest(
        `/donations/${donationId}/feedback`,
        {
          method: "POST",
          body: JSON.stringify({ rating, comments: "Rated via NGO Dashboard" }),
        }
      );

      if (!response.ok) {
        const message = await readErrorMessage(response);
        throw new Error(message);
      }

      showSuccessMessage("Feedback submitted! Donor trust score updated.");
      await loadDashboardData();
    } catch (error) {
      setErrorMessage(error.message || "Unable to submit feedback.");
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
            <p>Receiver Portal</p>
          </div>
        </Link>

        <nav className="dashboard-navigation">
          <Link to="/ngo-dashboard" className="active-dashboard-link">
            <span>▦</span> Overview
          </Link>

          <Link to="/ngo-verification">
            <span>🛡️</span> Verification
          </Link>

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
            FoodBridge AI predicts pickup priority using donation details. Your
            receiver organisation must still verify food condition and safe handling
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
            <p className="dashboard-label">RECEIVER DASHBOARD</p>
            <h1>Welcome, {ngo.fullName}</h1>
            <div className="receiver-subtitle">
              <strong>{ngo.organisation}</strong>

              <div
                style={{
                  color: "#64748b",
                  marginTop: "4px",
                  fontSize: "14px",
                }}
              >
                {ngo.organizationType || "Receiver Organization"}

                {ngo.location ? ` • ${ngo.location}` : ""}
              </div>
            </div>
          </div>

          <div className="ngo-header-actions" style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <NotificationBell />
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
          <strong>Secure receiver workflow connected:</strong> Available donations
          and assigned pickups are read from MongoDB using your authenticated NGO
          account. New listings include AI priority prediction, confidence
          information, food images and packaging images.
        </section>

        {successMessage && (
          <div className="ngo-success-message">{successMessage}</div>
        )}

        {errorMessage && <div className="ngo-error-message">{errorMessage}</div>}

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

        {statistics.categoryBreakdown && statistics.categoryBreakdown.length > 0 && (
          <section className="analytics-section" style={{ background: '#fff', padding: '24px', borderRadius: '12px', marginTop: '24px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#1e293b', marginBottom: '8px' }}>Food Categories Handled</h3>
            <div style={{ height: 300, marginTop: '20px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statistics.categoryBreakdown}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="count"
                    nameKey="category"
                    label
                  >
                    {statistics.categoryBreakdown.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658'][index % 7]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {ngo?.verificationStatus !== "verified" ? (
          <section style={{background: '#fffbeb', padding: '40px 20px', borderRadius: '12px', border: '1px solid #fde68a', textAlign: 'center', marginTop: '20px'}}>
            <h2 style={{color: '#92400e', marginBottom: '12px', fontSize: '1.5rem'}}>Organization Under Verification</h2>
            <p style={{color: '#b45309', fontSize: '1.1rem', maxWidth: '600px', margin: '0 auto'}}>
              Your organization is currently under verification. Please wait for administrator approval to access donation requests and coordinate collections.
            </p>
          </section>
        ) : (
        <section className="ngo-content-grid">
          {recommendedDonations.length > 0 && (
            <article className="ngo-panel" id="recommended-donations" style={{ border: '2px solid #8b5cf6', background: '#f5f3ff' }}>
              <div className="dashboard-section-title">
                <div>
                  <p style={{ color: '#7c3aed', fontWeight: 'bold' }}>✨ SMART MATCHING</p>
                  <h2 style={{ color: '#5b21b6' }}>Recommended For You</h2>
                </div>
                <span className="listing-count" style={{ background: '#7c3aed', color: 'white' }}>
                  {recommendedDonations.length} Matches
                </span>
              </div>

              <div className="ngo-donation-list">
                {recommendedDonations.map((donation) => (
                  <article className="ngo-donation-card" key={`rec-${donation.id}`} style={{ border: '1px solid #c4b5fd' }}>
                    <div className="ngo-card-top">
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <h3 style={{ margin: 0 }}>{donation.foodName}</h3>
                          {donation.matchScore && (
                            <span style={{ background: '#8b5cf6', color: 'white', padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 'bold' }}>
                              {donation.matchScore}% Match
                            </span>
                          )}
                        </div>
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

                    <DonationImages donation={donation} />

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
                        <span>Prediction Method</span>
                        <strong>
                          {formatPredictionMethod(donation.predictionMethod)}
                        </strong>
                      </div>
                    </div>

                    <p className="ngo-location">
                      📍 {donation.location}
                      {donation.distanceKm !== undefined && donation.distanceKm !== null && (
                        <span style={{ color: '#059669', fontWeight: 'bold', marginLeft: '6px' }}>
                          ({donation.distanceKm} km away)
                        </span>
                      )}
                    </p>

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

                    {donation.imageAnalysis && (
                      <div style={{ marginTop: '8px', marginBottom: '12px', padding: '10px 14px', background: donation.imageAnalysis.isSpoiled ? '#fef2f2' : '#f0fdf4', borderRadius: '8px', border: `1px solid ${donation.imageAnalysis.isSpoiled ? '#fecaca' : '#bbf7d0'}` }}>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: donation.imageAnalysis.isSpoiled ? '#991b1b' : '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '1.2rem' }}>{donation.imageAnalysis.isSpoiled ? '⚠️' : '📷'}</span>
                          <span>
                            <strong>Quality Assessment:</strong> Freshness indicator: {donation.imageAnalysis.freshnessIndicator} | Visual condition: {donation.imageAnalysis.visualCondition}
                          </span>
                        </p>
                      </div>
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
            </article>
          )}

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

                    <DonationImages donation={donation} />

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
                        <span>Prediction Method</span>
                        <strong>
                          {formatPredictionMethod(donation.predictionMethod)}
                        </strong>
                      </div>
                    </div>

                    <p className="ngo-location">
                      📍 {donation.location}
                      {donation.distanceKm !== undefined && donation.distanceKm !== null && (
                        <span style={{ color: '#059669', fontWeight: 'bold', marginLeft: '6px' }}>
                          ({donation.distanceKm} km away)
                        </span>
                      )}
                    </p>

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

                    {donation.imageAnalysis && (
                      <div style={{ marginTop: '8px', marginBottom: '12px', padding: '10px 14px', background: donation.imageAnalysis.isSpoiled ? '#fef2f2' : '#f0fdf4', borderRadius: '8px', border: `1px solid ${donation.imageAnalysis.isSpoiled ? '#fecaca' : '#bbf7d0'}` }}>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: donation.imageAnalysis.isSpoiled ? '#991b1b' : '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '1.2rem' }}>{donation.imageAnalysis.isSpoiled ? '⚠️' : '📷'}</span>
                          <span>
                            <strong>Quality Assessment:</strong> Freshness indicator: {donation.imageAnalysis.freshnessIndicator} | Visual condition: {donation.imageAnalysis.visualCondition}
                          </span>
                        </p>
                      </div>
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

              <span className="listing-count">{myPickups.length} Requests</span>
            </div>

            <div className="ngo-donation-list">
              {myPickups.length === 0 && !isLoading && (
                <div className="ngo-empty-state">
                  <h3>No assigned pickups</h3>
                  <p>Accept an available food donation to begin collection.</p>
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

                  <DonationImages donation={donation} />

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
                      <span>Prediction Method</span>
                      <strong>
                        {formatPredictionMethod(donation.predictionMethod)}
                      </strong>
                    </div>
                  </div>

                  <p className="ngo-location">
                    📍 {donation.location}
                    {donation.distanceKm !== undefined && donation.distanceKm !== null && (
                      <span style={{ color: '#059669', fontWeight: 'bold', marginLeft: '6px' }}>
                        ({donation.distanceKm} km away)
                      </span>
                    )}
                  </p>

                  <p className="ngo-deadline">
                    Pickup before: {formatDateTime(donation.pickupDeadline)}
                  </p>

                  <p className="ngo-packaging">
                    <strong>Packaging:</strong> {donation.packagingCondition}
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

                  {donation.imageAnalysis && (
                    <div style={{ marginTop: '8px', marginBottom: '12px', padding: '10px 14px', background: donation.imageAnalysis.isSpoiled ? '#fef2f2' : '#f0fdf4', borderRadius: '8px', border: `1px solid ${donation.imageAnalysis.isSpoiled ? '#fecaca' : '#bbf7d0'}` }}>
                      <p style={{ margin: 0, fontSize: '0.85rem', color: donation.imageAnalysis.isSpoiled ? '#991b1b' : '#166534', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ fontSize: '1.2rem' }}>{donation.imageAnalysis.isSpoiled ? '⚠️' : '📷'}</span>
                        <span>
                          <strong>Quality Assessment:</strong> Freshness indicator: {donation.imageAnalysis.freshnessIndicator} | Visual condition: {donation.imageAnalysis.visualCondition}
                        </span>
                      </p>
                    </div>
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

                  {donation.status === "Collected" && !donation.feedback && (
                    <div style={{ marginTop: '16px', padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <p style={{ margin: '0 0 10px 0', fontWeight: 'bold' }}>Rate Food Quality:</p>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        {[1, 2, 3, 4, 5].map(star => (
                          <button
                            key={star}
                            onClick={() => handleRateDonation(donation.id, star)}
                            disabled={processingId === donation.id}
                            style={{ 
                              padding: '6px 12px', 
                              border: '1px solid #cbd5e1', 
                              borderRadius: '4px',
                              background: 'white',
                              cursor: 'pointer'
                            }}
                          >
                            {star} ⭐
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {donation.feedback && (
                    <p style={{ color: '#16a34a', fontWeight: 'bold', marginTop: '12px' }}>
                      ✓ Rated {donation.feedback.rating} stars
                    </p>
                  )}
                </article>
              ))}
            </div>
          </article>
        </section>
        )}
      </main>
    </div>
  );
}

export default NgoDashboard;