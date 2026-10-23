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

  const [ngo, setNgo] = useState(getStoredUser);
  const [availableDonations, setAvailableDonations] = useState([]);
  const [recommendedDonations, setRecommendedDonations] = useState([]);
  const [myPickups, setMyPickups] = useState([]);
  const [statistics, setStatistics] = useState(emptyStatistics);
  const [isLoading, setIsLoading] = useState(true);
  const [processingId, setProcessingId] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // Sort and location matching states
  const [sortOrder, setSortOrder] = useState("match");
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);
  const [newLocationAddress, setNewLocationAddress] = useState(ngo?.location || "");
  const [isUpdatingLocation, setIsUpdatingLocation] = useState(false);

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

  const loadDashboardData = useCallback(async (currentSort = sortOrder) => {
    try {
      setIsLoading(true);
      setErrorMessage("");
      
      if (ngo?.verificationStatus !== "verified") {
        setIsLoading(false);
        return;
      }

      const [availableResponse, recommendedResponse, pickupsResponse, statisticsResponse] =
        await Promise.all([
          authenticatedRequest(`/donations/available?sort=${currentSort}`),
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
  }, [authenticatedRequest, ngo?.verificationStatus, sortOrder]);

  useEffect(() => {
    loadDashboardData(sortOrder);
  }, [loadDashboardData, sortOrder]);

  const handleUpdateLocation = async (e) => {
    e.preventDefault();
    if (!newLocationAddress.trim()) return;

    try {
      setIsUpdatingLocation(true);
      const res = await authenticatedRequest("/users/me/location", {
        method: "PATCH",
        body: JSON.stringify({ location: newLocationAddress.trim() }),
      });

      if (!res.ok) {
        const err = await readErrorMessage(res);
        throw new Error(err);
      }

      const updatedUser = await res.json();
      setNgo(updatedUser);
      localStorage.setItem("user", JSON.stringify(updatedUser));
      setIsLocationModalOpen(false);
      showSuccessMessage("Location updated successfully! Matching distance recalculated.");
      await loadDashboardData(sortOrder);
    } catch (err) {
      alert("Failed to update location: " + err.message);
    } finally {
      setIsUpdatingLocation(false);
    }
  };

  const handleGpsDetectLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
            { headers: { "User-Agent": "FoodBridgeAI/1.0" } }
          );
          if (res.ok) {
            const data = await res.json();
            if (data.display_name) {
              setNewLocationAddress(data.display_name);
              return;
            }
          }
        } catch (e) {
          console.warn("[Reverse Geocode] error:", e);
        }
        setNewLocationAddress(`Lat: ${latitude.toFixed(4)}, Lng: ${longitude.toFixed(4)}`);
      },
      (err) => alert("Could not access GPS: " + err.message),
      { timeout: 8000, enableHighAccuracy: true }
    );
  };

  const showSuccessMessage = (message) => {
    setSuccessMessage(message);

    window.setTimeout(() => {
      setSuccessMessage("");
    }, 5000);
  };

  const [acceptModal, setAcceptModal] = useState({
    isOpen: false,
    donation: null,
    quantity: 1,
    error: "",
  });

  const openAcceptModal = (donation) => {
    const remaining = donation.remainingServings ?? donation.servings;
    const capacity = ngo?.capacity ? Number(ngo.capacity) : 0;
    const defaultQty = capacity > 0 ? Math.min(remaining, capacity) : remaining;
    setAcceptModal({
      isOpen: true,
      donation,
      quantity: Math.max(1, defaultQty),
      error: "",
    });
  };

  const handleAcceptDonation = async (donationId, quantity) => {
    try {
      setProcessingId(donationId);
      setErrorMessage("");

      const response = await authenticatedRequest(
        `/donations/${donationId}/accept`,
        {
          method: "PATCH",
          body: JSON.stringify({ quantity: Number(quantity) }),
        }
      );

      if (!response.ok) {
        const message = await readErrorMessage(response);
        throw new Error(message);
      }

      setAcceptModal({ isOpen: false, donation: null, quantity: 1, error: "" });
      showSuccessMessage(
        `Successfully accepted ${quantity} servings. It is now assigned to your receiver account.`
      );

      await loadDashboardData();
    } catch (error) {
      setErrorMessage(error.message || "Unable to accept this pickup.");
    } finally {
      setProcessingId("");
    }
  };

  const handleMarkCollected = async (claimId, donationId) => {
    try {
      const targetId = claimId || donationId;
      setProcessingId(targetId);
      setErrorMessage("");

      const url = claimId ? `/claims/${claimId}/collect` : `/donations/${donationId}/collect`;
      const response = await authenticatedRequest(url, {
        method: "PATCH",
      });

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
          <h3>Food Safety Reminder</h3>
          <p>
            Surplus food listings undergo visual screening aligned with FSSAI guidelines.
            Your organization should inspect food condition upon pickup.
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
                  marginTop: "6px",
                  fontSize: "14px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  flexWrap: "wrap",
                }}
              >
                <span>{ngo.organizationType || "Receiver Organization"}</span>
                <span>•</span>
                <span>📍 {ngo.location || "Location not set"}</span>
                <button
                  type="button"
                  onClick={() => {
                    setNewLocationAddress(ngo.location || "");
                    setIsLocationModalOpen(true);
                  }}
                  style={{
                    background: "#e0f2fe",
                    border: "1px solid #bae6fd",
                    borderRadius: "6px",
                    color: "#0369a1",
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    padding: "3px 8px",
                    cursor: "pointer",
                  }}
                >
                  Change Location
                </button>
              </div>
            </div>
          </div>

          <div className="ngo-header-actions" style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <NotificationBell />
            <button
              className="refresh-donations-button"
              type="button"
              onClick={() => loadDashboardData(sortOrder)}
            >
              Refresh Donations
            </button>

            <Link to="/" className="view-home-button">
              View Homepage
            </Link>
          </div>
        </header>

        <section className="demo-information">
          <strong>Food redistribution platform:</strong> Available donations are
          geographically matched to your organization based on proximity and handling capacity,
          allowing efficient scheduling and pickup coordination.
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
                {recommendedDonations.map((donation) => {
                  const total = donation.servings;
                  const remaining = donation.remainingServings ?? total;
                  const claimed = total - remaining;
                  const percentClaimed = Math.round((claimed / total) * 100);

                  return (
                    <article
                      className="ngo-donation-card"
                      key={`rec-${donation.id}`}
                      id={`donation-${donation.id}`}
                      style={{ border: "1px solid #c4b5fd" }}
                    >
                      <div className="ngo-card-top">
                        <div>
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                            }}
                          >
                            <h3 style={{ margin: 0 }}>{donation.foodName}</h3>
                            {donation.matchScore && (
                              <span
                                style={{
                                  background: "#8b5cf6",
                                  color: "white",
                                  padding: "2px 8px",
                                  borderRadius: "12px",
                                  fontSize: "0.75rem",
                                  fontWeight: "bold",
                                }}
                              >
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
                          Priority: {donation.priority || "Medium"}
                        </span>
                      </div>

                      <DonationImages donation={donation} />

                      {donation.match && (
                        <div
                          className="ngo-match-box"
                          style={{
                            margin: "10px 0",
                            background: "#f8fafc",
                            padding: "10px 12px",
                            borderRadius: "10px",
                            border: "1px solid #e2e8f0",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "6px",
                            }}
                          >
                            <span
                              style={{
                                fontSize: "0.85rem",
                                fontWeight: 600,
                                color: "#1e293b",
                              }}
                            >
                              Match Score:{" "}
                              <strong
                                style={{
                                  color:
                                    donation.match.matchPercent >= 80
                                      ? "#059669"
                                      : donation.match.matchPercent >= 50
                                      ? "#d97706"
                                      : "#dc2626",
                                }}
                              >
                                {donation.match.matchPercent}%
                              </strong>
                            </span>
                            <span
                              style={{
                                fontSize: "0.8rem",
                                color: "#64748b",
                                fontWeight: 500,
                              }}
                            >
                              🚗 {donation.match.distanceKm} km · ~
                              {donation.match.estimatedTravelMinutes} min drive
                            </span>
                          </div>
                          <div
                            style={{
                              height: "6px",
                              width: "100%",
                              background: "#e2e8f0",
                              borderRadius: "3px",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                height: "100%",
                                width: `${donation.match.matchPercent}%`,
                                background: donation.match.feasible
                                  ? donation.match.matchPercent >= 80
                                    ? "linear-gradient(90deg, #10b981, #059669)"
                                    : donation.match.matchPercent >= 50
                                    ? "linear-gradient(90deg, #f59e0b, #d97706)"
                                    : "#ef4444"
                                  : "#94a3b8",
                                borderRadius: "3px",
                                transition: "width 0.3s ease",
                              }}
                            />
                          </div>

                          {donation.match.feasible === false && (
                            <div
                              style={{
                                marginTop: "6px",
                                fontSize: "0.78rem",
                                color: "#b91c1c",
                                fontWeight: 600,
                              }}
                            >
                              ⚠️ {donation.match.feasibilityReason ||
                                "Cannot reach before pickup deadline"}
                            </div>
                          )}

                          {donation.match.directionsUrl && (
                            <div style={{ marginTop: "6px", textAlign: "right" }}>
                              <a
                                href={donation.match.directionsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  fontSize: "0.8rem",
                                  color: "#2563eb",
                                  textDecoration: "none",
                                  fontWeight: 600,
                                }}
                              >
                                🗺️ Directions in Google Maps ↗
                              </a>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="servings-progress-wrapper">
                        <div className="servings-progress-header">
                          <span>
                            <strong>{remaining}</strong> / {total} servings
                            available
                          </span>
                          <span>
                            {claimed > 0
                              ? `${claimed} claimed (${percentClaimed}%)`
                              : "Full quantity"}
                          </span>
                        </div>
                        <div className="servings-progress-track">
                          <div
                            className="servings-progress-fill"
                            style={{ width: `${percentClaimed}%` }}
                          />
                        </div>
                      </div>

                      <div className="ngo-donation-details">
                        <div>
                          <span>Servings</span>
                          <strong>
                            {remaining} of {total} left
                          </strong>
                        </div>

                        <div>
                          <span>Status</span>
                          <strong
                            className={
                              donation.status === "Partially Accepted"
                                ? "partially-accepted-status"
                                : "active-status"
                            }
                          >
                            {donation.status}
                          </strong>
                        </div>
                      </div>

                      {donation.foodVerdict && (
                        <div className="ngo-fssai-pill">
                          <span>
                            🛡️ Food Screening:{" "}
                            <strong>{donation.foodVerdict}</strong> (
                            {donation.detectedFood || "Food"})
                          </span>
                          <small>
                            {donation.fssaiDisclaimer ||
                              "Visual screening aligned with FSSAI guidance. Not a lab certification."}
                          </small>
                        </div>
                      )}

                      <p className="ngo-location">
                        📍 {donation.location}
                        {donation.distanceKm !== undefined &&
                          donation.distanceKm !== null && (
                            <span
                              style={{
                                color: "#059669",
                                fontWeight: "bold",
                                marginLeft: "6px",
                              }}
                            >
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

                      <button
                        className="accept-donation-button"
                        type="button"
                        disabled={processingId === donation.id}
                        onClick={() => openAcceptModal(donation)}
                      >
                        {processingId === donation.id
                          ? "Processing..."
                          : "Accept Pickup Request"}
                      </button>
                    </article>
                  );
                })}
              </div>
            </article>
          )}

          <article className="ngo-panel" id="available-donations">
            <div className="dashboard-section-title">
              <div>
                <p>DONATION LISTINGS</p>
                <h2>Available Donations</h2>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <label style={{ fontSize: "0.85rem", color: "#475569", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
                  Sort by:
                  <select
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value)}
                    style={{
                      padding: "5px 10px",
                      borderRadius: "6px",
                      border: "1px solid #cbd5e1",
                      background: "#fff",
                      fontSize: "0.85rem",
                      color: "#1e293b",
                      cursor: "pointer",
                    }}
                  >
                    <option value="match">Best Match (Recommended)</option>
                    <option value="distance">Distance (Nearest First)</option>
                    <option value="priority">Priority (High First)</option>
                    <option value="newest">Newest First</option>
                  </select>
                </label>
                <span className="listing-count">
                  {availableDonations.length} Available
                </span>
              </div>
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

                {availableDonations.map((donation) => {
                  const total = donation.servings;
                  const remaining = donation.remainingServings ?? total;
                  const claimed = total - remaining;
                  const percentClaimed = Math.round((claimed / total) * 100);

                  return (
                    <article
                      className="ngo-donation-card"
                      key={donation.id}
                      id={`donation-${donation.id}`}
                    >
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
                          Priority: {donation.priority || "Medium"}
                        </span>
                      </div>

                      <DonationImages donation={donation} />

                      {donation.match && (
                        <div
                          className="ngo-match-box"
                          style={{
                            margin: "10px 0",
                            background: "#f8fafc",
                            padding: "10px 12px",
                            borderRadius: "10px",
                            border: "1px solid #e2e8f0",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "6px",
                            }}
                          >
                            <span
                              style={{
                                fontSize: "0.85rem",
                                fontWeight: 600,
                                color: "#1e293b",
                              }}
                            >
                              Match Score:{" "}
                              <strong
                                style={{
                                  color:
                                    donation.match.matchPercent >= 80
                                      ? "#059669"
                                      : donation.match.matchPercent >= 50
                                      ? "#d97706"
                                      : "#dc2626",
                                }}
                              >
                                {donation.match.matchPercent}%
                              </strong>
                            </span>
                            <span
                              style={{
                                fontSize: "0.8rem",
                                color: "#64748b",
                                fontWeight: 500,
                              }}
                            >
                              🚗 {donation.match.distanceKm} km · ~
                              {donation.match.estimatedTravelMinutes} min drive
                            </span>
                          </div>
                          <div
                            style={{
                              height: "6px",
                              width: "100%",
                              background: "#e2e8f0",
                              borderRadius: "3px",
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                height: "100%",
                                width: `${donation.match.matchPercent}%`,
                                background: donation.match.feasible
                                  ? donation.match.matchPercent >= 80
                                    ? "linear-gradient(90deg, #10b981, #059669)"
                                    : donation.match.matchPercent >= 50
                                    ? "linear-gradient(90deg, #f59e0b, #d97706)"
                                    : "#ef4444"
                                  : "#94a3b8",
                                borderRadius: "3px",
                                transition: "width 0.3s ease",
                              }}
                            />
                          </div>

                          {donation.match.feasible === false && (
                            <div
                              style={{
                                marginTop: "6px",
                                fontSize: "0.78rem",
                                color: "#b91c1c",
                                fontWeight: 600,
                              }}
                            >
                              ⚠️ {donation.match.feasibilityReason ||
                                "Cannot reach before pickup deadline"}
                            </div>
                          )}

                          {donation.match.directionsUrl && (
                            <div style={{ marginTop: "6px", textAlign: "right" }}>
                              <a
                                href={donation.match.directionsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  fontSize: "0.8rem",
                                  color: "#2563eb",
                                  textDecoration: "none",
                                  fontWeight: 600,
                                }}
                              >
                                🗺️ Directions in Google Maps ↗
                              </a>
                            </div>
                          )}
                        </div>
                      )}

                      <div className="servings-progress-wrapper">
                        <div className="servings-progress-header">
                          <span>
                            <strong>{remaining}</strong> / {total} servings
                            available
                          </span>
                          <span>
                            {claimed > 0
                              ? `${claimed} claimed (${percentClaimed}%)`
                              : "Full quantity"}
                          </span>
                        </div>
                        <div className="servings-progress-track">
                          <div
                            className="servings-progress-fill"
                            style={{ width: `${percentClaimed}%` }}
                          />
                        </div>
                      </div>

                      <div className="ngo-donation-details">
                        <div>
                          <span>Servings</span>
                          <strong>
                            {remaining} of {total} left
                          </strong>
                        </div>

                        <div>
                          <span>Status</span>
                          <strong
                            className={
                              donation.status === "Partially Accepted"
                                ? "partially-accepted-status"
                                : "active-status"
                            }
                          >
                            {donation.status}
                          </strong>
                        </div>
                      </div>

                      {donation.foodVerdict && (
                        <div className="ngo-fssai-pill">
                          <span>
                            🛡️ Food Screening:{" "}
                            <strong>{donation.foodVerdict}</strong> (
                            {donation.detectedFood || "Food"})
                          </span>
                          <small>
                            {donation.fssaiDisclaimer ||
                              "Visual screening aligned with FSSAI guidance. Not a lab certification."}
                          </small>
                        </div>
                      )}

                      <p className="ngo-location">
                        📍 {donation.location}
                        {donation.distanceKm !== undefined &&
                          donation.distanceKm !== null && (
                            <span
                              style={{
                                color: "#059669",
                                fontWeight: "bold",
                                marginLeft: "6px",
                              }}
                            >
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

                      <button
                        className="accept-donation-button"
                        type="button"
                        disabled={processingId === donation.id}
                        onClick={() => openAcceptModal(donation)}
                      >
                        {processingId === donation.id
                          ? "Processing..."
                          : "Accept Pickup Request"}
                      </button>
                    </article>
                  );
                })}
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

              {myPickups.map((item) => {
                const claimStatus = item.claimStatus || item.status;
                const statusClass =
                  claimStatus === "Collected"
                    ? "collected"
                    : claimStatus === "Accepted"
                    ? "accepted"
                    : "partially-accepted";

                const targetClaimId = item.claimId;
                const targetDonationId = item.donationId || item.id;
                const cardIdentifier = targetClaimId || targetDonationId;

                return (
                  <article
                    className="ngo-donation-card"
                    key={cardIdentifier}
                    id={`pickup-${cardIdentifier}`}
                  >
                    <div className="ngo-card-top">
                      <div>
                        <h3>{item.foodName}</h3>
                        <p>{item.donorOrganisation}</p>
                      </div>

                      <span className={`workflow-status-pill ${statusClass}`}>
                        {claimStatus}
                      </span>
                    </div>

                    <DonationImages donation={item} />

                    <div className="ngo-donation-details">
                      <div>
                        <span>Claimed Servings</span>
                        <strong>
                          {item.claimedQuantity || item.servings} servings
                        </strong>
                      </div>

                      <div>
                        <span>Priority</span>
                        <strong>{item.priority || "Medium"}</strong>
                      </div>
                    </div>

                    <p className="ngo-location">
                      📍 {item.location}
                      {item.distanceKm !== undefined && item.distanceKm !== null && (
                        <span
                          style={{
                            color: "#059669",
                            fontWeight: "bold",
                            marginLeft: "6px",
                          }}
                        >
                          ({item.distanceKm} km away)
                        </span>
                      )}
                    </p>

                    <p className="ngo-deadline">
                      Pickup before: {formatDateTime(item.pickupDeadline)}
                    </p>

                    <p className="ngo-packaging">
                      <strong>Packaging:</strong> {item.packagingCondition}
                    </p>

                    {item.imageAnalysis && (
                      <div
                        style={{
                          marginTop: "8px",
                          marginBottom: "12px",
                          padding: "10px 14px",
                          background: item.imageAnalysis.isSpoiled
                            ? "#fef2f2"
                            : "#f0fdf4",
                          borderRadius: "8px",
                          border: `1px solid ${
                            item.imageAnalysis.isSpoiled ? "#fecaca" : "#bbf7d0"
                          }`,
                        }}
                      >
                        <p
                          style={{
                            margin: 0,
                            fontSize: "0.85rem",
                            color: item.imageAnalysis.isSpoiled
                              ? "#991b1b"
                              : "#166534",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <span style={{ fontSize: "1.2rem" }}>
                            {item.imageAnalysis.isSpoiled ? "⚠️" : "📷"}
                          </span>
                          <span>
                            <strong>Quality Assessment:</strong> Freshness
                            indicator: {item.imageAnalysis.freshnessIndicator} |
                            Visual condition: {item.imageAnalysis.visualCondition}
                          </span>
                        </p>
                      </div>
                    )}

                    {item.acceptedAt && (
                      <p className="ngo-deadline">
                        Accepted: {formatDateTime(item.acceptedAt)}
                      </p>
                    )}

                    {claimStatus === "Accepted" && (
                      <button
                        className="complete-pickup-button"
                        type="button"
                        disabled={processingId === cardIdentifier}
                        onClick={() =>
                          handleMarkCollected(targetClaimId, targetDonationId)
                        }
                      >
                        {processingId === cardIdentifier
                          ? "Updating..."
                          : "Mark Collection Completed"}
                      </button>
                    )}

                    {claimStatus === "Collected" && !item.feedback && (
                      <div
                        style={{
                          marginTop: "16px",
                          padding: "16px",
                          background: "#f8fafc",
                          borderRadius: "8px",
                          border: "1px solid #e2e8f0",
                        }}
                      >
                        <p
                          style={{
                            margin: "0 0 10px 0",
                            fontWeight: "bold",
                          }}
                        >
                          Rate Food Quality:
                        </p>
                        <div style={{ display: "flex", gap: "8px" }}>
                          {[1, 2, 3, 4, 5].map((star) => (
                            <button
                              key={star}
                              onClick={() =>
                                handleRateDonation(targetDonationId, star)
                              }
                              disabled={processingId === targetDonationId}
                              style={{
                                padding: "6px 12px",
                                border: "1px solid #cbd5e1",
                                borderRadius: "4px",
                                background: "white",
                                cursor: "pointer",
                              }}
                            >
                              {star} ⭐
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    {item.feedback && (
                      <p
                        style={{
                          color: "#16a34a",
                          fontWeight: "bold",
                          marginTop: "12px",
                        }}
                      >
                        ✓ Rated {item.feedback.rating} stars
                      </p>
                    )}
                  </article>
                );
              })}
            </div>
          </article>
        </section>
        )}
      </main>

      {/* Partial Acceptance Modal */}
      {acceptModal.isOpen && acceptModal.donation && (() => {
        const donation = acceptModal.donation;
        const remaining = donation.remainingServings ?? donation.servings;
        const capacity = ngo?.capacity ? Number(ngo.capacity) : 0;
        const qty = Number(acceptModal.quantity);
        const isOverRemaining = qty > remaining;
        const isOverCapacity = capacity > 0 && qty > capacity;
        const isUnderMin = qty < 1;
        const hasError = isOverRemaining || isOverCapacity || isUnderMin;

        return (
          <div
            className="accept-modal-overlay"
            onClick={() => setAcceptModal({ ...acceptModal, isOpen: false })}
          >
            <div
              className="accept-modal-card"
              onClick={(e) => e.stopPropagation()}
            >
              <h3>Accept Food Pickup</h3>
              <p className="accept-modal-subtitle">
                {donation.foodName} • {donation.category}
              </p>

              <div className="modal-info-box">
                <div>
                  <span>Available: </span>
                  <strong>{remaining} servings</strong>
                </div>
                <div>
                  <span>Your Daily Capacity: </span>
                  <strong>
                    {capacity > 0 ? `${capacity} meals/day` : "Unspecified"}
                  </strong>
                </div>
              </div>

              <div className="modal-field">
                <label htmlFor="servings-to-claim">
                  Servings to Accept / Claim:
                </label>
                <input
                  id="servings-to-claim"
                  className="modal-input"
                  type="number"
                  min="1"
                  max={remaining}
                  value={acceptModal.quantity}
                  onChange={(e) =>
                    setAcceptModal({
                      ...acceptModal,
                      quantity: e.target.value,
                    })
                  }
                />

                <div className="modal-quick-buttons">
                  {capacity > 0 && (
                    <button
                      type="button"
                      className="quick-btn"
                      onClick={() =>
                        setAcceptModal({
                          ...acceptModal,
                          quantity: Math.min(remaining, capacity),
                        })
                      }
                    >
                      Accept Maximum ({Math.min(remaining, capacity)})
                    </button>
                  )}
                  <button
                    type="button"
                    className="quick-btn"
                    disabled={capacity > 0 && remaining > capacity}
                    title={
                      capacity > 0 && remaining > capacity
                        ? "Exceeds your organization's daily capacity limit"
                        : "Accept all available servings"
                    }
                    onClick={() =>
                      setAcceptModal({
                        ...acceptModal,
                        quantity: remaining,
                      })
                    }
                  >
                    Accept All Remaining ({remaining})
                  </button>
                </div>

                {isOverRemaining && (
                  <p className="modal-warning">
                    ⚠️ Cannot request more than the {remaining} remaining servings.
                  </p>
                )}
                {isOverCapacity && (
                  <p className="modal-warning">
                    ⚠️ Requested quantity exceeds your organization's capacity limit of {capacity} servings.
                  </p>
                )}
                {isUnderMin && (
                  <p className="modal-warning">
                    ⚠️ Quantity must be at least 1.
                  </p>
                )}
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="modal-cancel-btn"
                  onClick={() =>
                    setAcceptModal({ ...acceptModal, isOpen: false })
                  }
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="modal-submit-btn"
                  disabled={hasError || processingId === donation.id}
                  onClick={() => handleAcceptDonation(donation.id, qty)}
                >
                  {processingId === donation.id
                    ? "Confirming..."
                    : `Confirm Acceptance (${qty} servings)`}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {isLocationModalOpen && (
        <div className="camera-modal-backdrop" onClick={() => setIsLocationModalOpen(false)}>
          <div className="camera-modal-dialog" style={{ maxWidth: "460px", background: "#fff", padding: "24px", borderRadius: "12px", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)" }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 12px 0", color: "#1e293b", fontSize: "1.25rem", fontWeight: 700 }}>Update Organization Location</h3>
            <p style={{ margin: "0 0 16px 0", color: "#64748b", fontSize: "0.9rem", lineHeight: 1.5 }}>
              Update your registered address to receive accurate distance calculations, road travel ETAs, and proximity matches.
            </p>
            <form onSubmit={handleUpdateLocation}>
              <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
                <input
                  type="text"
                  value={newLocationAddress}
                  onChange={(e) => setNewLocationAddress(e.target.value)}
                  placeholder="Enter city, neighborhood, or address"
                  required
                  style={{ flex: 1, padding: "10px 12px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.9rem" }}
                />
                <button
                  type="button"
                  onClick={handleGpsDetectLocation}
                  style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "0 14px", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600, whiteSpace: "nowrap", color: "#0f172a" }}
                >
                  📍 Use GPS
                </button>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <button
                  type="button"
                  onClick={() => setIsLocationModalOpen(false)}
                  style={{ background: "#f1f5f9", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "8px 16px", cursor: "pointer", fontWeight: 600, color: "#475569" }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdatingLocation}
                  style={{ background: "#0284c7", color: "#fff", border: "none", borderRadius: "8px", padding: "8px 18px", cursor: "pointer", fontWeight: 600 }}
                >
                  {isUpdatingLocation ? "Saving..." : "Save Location"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default NgoDashboard;