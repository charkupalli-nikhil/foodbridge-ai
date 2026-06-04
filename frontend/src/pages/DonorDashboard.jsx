import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Dashboard.css";

import { API_BASE_URL } from "../config";

const emptyDonationForm = {
  foodName: "",
  category: "",
  servings: "",
  preparationTime: "",
  pickupDeadline: "",
  location: "",
  packagingCondition: "",
};

const emptyStatistics = {
  activeDonations: 0,
  acceptedPickups: 0,
  completedPickups: 0,
  highPriorityDonations: 0,
  mealsSaved: 0,
};

function getStoredUser() {
  const storedUser = localStorage.getItem("foodbridge_user");

  if (!storedUser) {
    return {
      fullName: "Food Donor",
      organisation: "Registered Food Donor",
      location: "",
    };
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return {
      fullName: "Food Donor",
      organisation: "Registered Food Donor",
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

function getMinimumDeadline() {
  const now = new Date();
  const localTime = new Date(now.getTime() - now.getTimezoneOffset() * 60000);

  return localTime.toISOString().slice(0, 16);
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

function DonorDashboard() {
  const navigate = useNavigate();

  const [donor] = useState(getStoredUser);
  const [donations, setDonations] = useState([]);
  const [statistics, setStatistics] = useState(emptyStatistics);
  const [formData, setFormData] = useState(emptyDonationForm);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

      const [donationsResponse, statisticsResponse] = await Promise.all([
        authenticatedRequest("/donations/my"),
        authenticatedRequest("/statistics/donor"),
      ]);

      if (!donationsResponse.ok) {
        const message = await readErrorMessage(donationsResponse);
        throw new Error(message);
      }

      if (!statisticsResponse.ok) {
        const message = await readErrorMessage(statisticsResponse);
        throw new Error(message);
      }

      const donationData = await donationsResponse.json();
      const statisticsData = await statisticsResponse.json();

      setDonations(donationData);
      setStatistics(statisticsData);
    } catch (error) {
      setErrorMessage(
        error.message ||
          "Unable to load your donor dashboard from the backend."
      );
    } finally {
      setIsLoading(false);
    }
  }, [authenticatedRequest]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleInputChange = (event) => {
    const { name, value } = event.target;

    setFormData((previousData) => ({
      ...previousData,
      [name]: value,
    }));
  };

  const showSuccessMessage = (message) => {
    setSuccessMessage(message);

    window.setTimeout(() => {
      setSuccessMessage("");
    }, 5000);
  };

  const handleDonationSubmit = async (event) => {
    event.preventDefault();

    try {
      setIsSubmitting(true);
      setErrorMessage("");
      setSuccessMessage("");

      const response = await authenticatedRequest("/donations", {
        method: "POST",
        body: JSON.stringify({
          ...formData,
          servings: Number(formData.servings),
        }),
      });

      if (!response.ok) {
        const message = await readErrorMessage(response);
        throw new Error(message);
      }

      const createdDonation = await response.json();

      setFormData(emptyDonationForm);

      showSuccessMessage(
        `Donation posted successfully. Backend assigned ${createdDonation.priority} priority.`
      );

      await loadDashboardData();
    } catch (error) {
      setErrorMessage(error.message || "Unable to post your donation.");
    } finally {
      setIsSubmitting(false);
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
            <p>Donor Portal</p>
          </div>
        </Link>

        <nav className="dashboard-navigation">
          <a className="active-dashboard-link" href="#overview">
            <span>▦</span> Overview
          </a>

          <a href="#add-donation">
            <span>＋</span> Add Donation
          </a>

          <a href="#my-donations">
            <span>🍱</span> My Donations
          </a>
        </nav>

        <div className="safety-note">
          <h3>Safety Reminder</h3>
          <p>
            FoodBridge assigns pickup priority only. Food safety verification
            must be completed by the responsible organisations.
          </p>
        </div>

        <Link to="/login" className="logout-link" onClick={handleLogout}>
          ← Logout
        </Link>
      </aside>

      <main className="dashboard-main">
        <header className="dashboard-header" id="overview">
          <div>
            <p className="dashboard-label">DONOR DASHBOARD</p>
            <h1>Welcome, {donor.fullName}</h1>
            <span>
              {donor.organisation}
              {donor.location ? ` • ${donor.location}` : ""}
            </span>
          </div>

          <Link to="/" className="view-home-button">
            View Homepage
          </Link>
        </header>

        <section className="demo-information">
          <strong>Secure account connected:</strong> Your donations are stored
          in MongoDB and protected through your authenticated donor account.
        </section>

        {errorMessage && (
          <div
            style={{
              marginBottom: "22px",
              padding: "14px 17px",
              borderRadius: "10px",
              background: "#fee2e2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              fontWeight: "600",
              fontSize: "14px",
              lineHeight: "1.5",
            }}
          >
            {errorMessage}
          </div>
        )}

        <section className="dashboard-statistics">
          <article className="statistic-card">
            <div className="stat-icon green">🍱</div>

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
              <p>Meals Saved</p>
              <h2>{statistics.mealsSaved}</h2>
            </div>
          </article>
        </section>

        <section className="dashboard-content-grid">
          <article className="donation-form-container" id="add-donation">
            <div className="dashboard-section-title">
              <div>
                <p>NEW LISTING</p>
                <h2>Add Food Donation</h2>
              </div>
            </div>

            {successMessage && (
              <div className="success-message">{successMessage}</div>
            )}

            <form className="donation-form" onSubmit={handleDonationSubmit}>
              <div className="donation-form-row">
                <label htmlFor="food-name">
                  Food Name
                  <input
                    id="food-name"
                    name="foodName"
                    type="text"
                    placeholder="Example: Veg Biryani"
                    value={formData.foodName}
                    onChange={handleInputChange}
                    required
                  />
                </label>

                <label htmlFor="food-category">
                  Food Category
                  <select
                    id="food-category"
                    name="category"
                    value={formData.category}
                    onChange={handleInputChange}
                    required
                  >
                    <option value="" disabled>
                      Select category
                    </option>
                    <option value="Cooked Meal">Cooked Meal</option>
                    <option value="Packaged Food">Packaged Food</option>
                    <option value="Bakery">Bakery</option>
                    <option value="Fruits">Fruits</option>
                  </select>
                </label>
              </div>

              <div className="donation-form-row">
                <label htmlFor="servings">
                  Number of Servings
                  <input
                    id="servings"
                    name="servings"
                    type="number"
                    min="1"
                    placeholder="Example: 60"
                    value={formData.servings}
                    onChange={handleInputChange}
                    required
                  />
                </label>

                <label htmlFor="preparation-time">
                  Preparation Time
                  <input
                    id="preparation-time"
                    name="preparationTime"
                    type="text"
                    placeholder="Prepared 20 minutes ago"
                    value={formData.preparationTime}
                    onChange={handleInputChange}
                    required
                  />
                </label>
              </div>

              <label htmlFor="pickup-deadline">
                Pickup Deadline
                <input
                  id="pickup-deadline"
                  name="pickupDeadline"
                  type="datetime-local"
                  min={getMinimumDeadline()}
                  value={formData.pickupDeadline}
                  onChange={handleInputChange}
                  required
                />
              </label>

              <label htmlFor="pickup-location">
                Pickup Location
                <input
                  id="pickup-location"
                  name="location"
                  type="text"
                  placeholder="Example: WIT College Canteen, Solapur"
                  value={formData.location}
                  onChange={handleInputChange}
                  required
                />
              </label>

              <label htmlFor="packaging-condition">
                Packaging Condition
                <textarea
                  id="packaging-condition"
                  name="packagingCondition"
                  placeholder="Example: Packed in clean covered containers"
                  value={formData.packagingCondition}
                  onChange={handleInputChange}
                  rows="3"
                  required
                />
              </label>

              <button
                className="post-donation-button"
                type="submit"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Posting Donation..." : "Post Food Donation"}
              </button>
            </form>
          </article>

          <article className="donation-list-container" id="my-donations">
            <div className="dashboard-section-title">
              <div>
                <p>YOUR ACTIVITY</p>
                <h2>My Donations</h2>
              </div>

              <span className="listing-count">
                {donations.length} Listings
              </span>
            </div>

            {isLoading ? (
              <p>Loading your donations...</p>
            ) : (
              <div className="donation-list">
                {donations.length === 0 && (
                  <p>
                    You have not posted any secure donations yet. Add your
                    first food listing using the form.
                  </p>
                )}

                {donations.map((donation) => (
                  <article className="donation-record" key={donation.id}>
                    <div className="record-top">
                      <div>
                        <h3>{donation.foodName}</h3>
                        <p>{donation.category}</p>
                      </div>

                      <span
                        className={`priority-pill ${donation.priority.toLowerCase()}`}
                      >
                        {donation.priority}
                      </span>
                    </div>

                    <div className="record-information">
                      <div>
                        <span>Servings</span>
                        <strong>{donation.servings}</strong>
                      </div>

                      <div>
                        <span>Status</span>
                        <strong
                          className={
                            donation.status === "Active"
                              ? "active-status"
                              : "collected-status"
                          }
                        >
                          {donation.status}
                        </strong>
                      </div>
                    </div>

                    <p className="record-location">📍 {donation.location}</p>

                    <p className="record-deadline">
                      Pickup deadline: {formatDateTime(donation.pickupDeadline)}
                    </p>

                    {donation.status === "Active" && (
                      <p className="record-deadline">
                        Waiting for an NGO partner to accept this request.
                      </p>
                    )}

                    {donation.status === "Accepted" && (
                      <p className="record-deadline">
                        Accepted by:{" "}
                        {donation.acceptedByOrganisation || "NGO Partner"}
                      </p>
                    )}

                    {donation.status === "Collected" && (
                      <p className="record-deadline">
                        Collection completed by:{" "}
                        {donation.acceptedByOrganisation || "NGO Partner"}
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

export default DonorDashboard;