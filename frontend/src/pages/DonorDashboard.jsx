import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import API from "../api/axios";
import "./Dashboard.css";

function DonorDashboard() {
  const navigate = useNavigate();

  const savedUser = JSON.parse(localStorage.getItem("user") || "{}");

  const [statistics, setStatistics] = useState({
    activeDonations: 0,
    acceptedPickups: 0,
    completedPickups: 0,
    highPriorityDonations: 0,
    mealsSaved: 0,
  });

  const [donations, setDonations] = useState([]);

  const [formData, setFormData] = useState({
    foodName: "",
    category: "Cooked Meal",
    servings: "",
    preparationTime: "",
    pickupDeadline: "",
    location: savedUser.location || "",
    packagingCondition: "",
  });

  const [foodImageFile, setFoodImageFile] = useState(null);
  const [packagingImageFile, setPackagingImageFile] = useState(null);
  const [foodImagePreview, setFoodImagePreview] = useState("");
  const [packagingImagePreview, setPackagingImagePreview] = useState("");

  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [message, setMessage] = useState("");

  const backendBaseUrl = (
    API.defaults.baseURL ||
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:8000/api"
  ).replace(/\/api\/?$/, "");

  const getImageUrl = (imagePath) => {
    if (!imagePath) return "";
    if (imagePath.startsWith("http")) return imagePath;
    return `${backendBaseUrl}${imagePath}`;
  };

  const formatDateTime = (dateValue) => {
    if (!dateValue) return "Not available";

    return new Date(dateValue).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  };

  const loadDashboardData = async () => {
    try {
      setPageLoading(true);

      const [statisticsResponse, donationsResponse] = await Promise.all([
        API.get("/statistics/donor"),
        API.get("/donations/my"),
      ]);

      setStatistics(statisticsResponse.data);
      setDonations(donationsResponse.data);
      setMessage("");
    } catch (error) {
      console.error(error);
      setMessage("Unable to load dashboard data. Please login again.");
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleInputChange = (event) => {
    const { name, value } = event.target;

    setFormData((previousData) => ({
      ...previousData,
      [name]: value,
    }));
  };

  const handleFoodImageChange = (event) => {
    const file = event.target.files[0];

    if (!file) {
      setFoodImageFile(null);
      setFoodImagePreview("");
      return;
    }

    setFoodImageFile(file);
    setFoodImagePreview(URL.createObjectURL(file));
  };

  const handlePackagingImageChange = (event) => {
    const file = event.target.files[0];

    if (!file) {
      setPackagingImageFile(null);
      setPackagingImagePreview("");
      return;
    }

    setPackagingImageFile(file);
    setPackagingImagePreview(URL.createObjectURL(file));
  };

  const uploadImage = async (file, imageType) => {
    if (!file) return null;

    const uploadFormData = new FormData();
    uploadFormData.append("file", file);
    uploadFormData.append("image_type", imageType);

    const response = await API.post("/upload-image", uploadFormData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });

    return response.data.imageUrl;
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!formData.foodName.trim()) {
      setMessage("Please enter food name.");
      return;
    }

    if (!formData.servings || Number(formData.servings) <= 0) {
      setMessage("Please enter valid number of servings.");
      return;
    }

    if (!formData.preparationTime.trim()) {
      setMessage("Please enter preparation time.");
      return;
    }

    if (!formData.pickupDeadline) {
      setMessage("Please select pickup deadline.");
      return;
    }

    if (!formData.location.trim()) {
      setMessage("Please enter pickup location.");
      return;
    }

    if (!formData.packagingCondition.trim()) {
      setMessage("Please enter packaging condition.");
      return;
    }

    try {
      setLoading(true);
      setMessage("Uploading images and posting donation...");

      const foodImageUrl = await uploadImage(foodImageFile, "food");
      const packagingImageUrl = await uploadImage(
        packagingImageFile,
        "packaging"
      );

      const donationPayload = {
        foodName: formData.foodName.trim(),
        category: formData.category,
        servings: Number(formData.servings),
        preparationTime: formData.preparationTime.trim(),
        pickupDeadline: new Date(formData.pickupDeadline).toISOString(),
        location: formData.location.trim(),
        packagingCondition: formData.packagingCondition.trim(),
        foodImage: foodImageUrl,
        packagingImage: packagingImageUrl,
      };

      await API.post("/donations", donationPayload);

      setMessage("Donation posted successfully with images.");

      setFormData({
        foodName: "",
        category: "Cooked Meal",
        servings: "",
        preparationTime: "",
        pickupDeadline: "",
        location: savedUser.location || "",
        packagingCondition: "",
      });

      setFoodImageFile(null);
      setPackagingImageFile(null);
      setFoodImagePreview("");
      setPackagingImagePreview("");

      const foodInput = document.getElementById("foodImage");
      const packagingInput = document.getElementById("packagingImage");

      if (foodInput) foodInput.value = "";
      if (packagingInput) packagingInput.value = "";

      await loadDashboardData();
    } catch (error) {
      console.error(error);

      const errorMessage =
        error.response?.data?.detail ||
        "Unable to post donation. Please check backend and try again.";

      setMessage(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = (event) => {
    event.preventDefault();

    localStorage.removeItem("accessToken");
    localStorage.removeItem("token");
    localStorage.removeItem("user");

    navigate("/login");
  };

  return (
    <div className="dashboard-page">
      <aside className="dashboard-sidebar">
        <Link to="/" className="dashboard-brand">
          <span>🥗</span>
          <div>
            <h2>FoodBridge AI</h2>
            <p>Donor Portal</p>
          </div>
        </Link>

        <nav className="dashboard-navigation">
          <a href="#overview" className="active-dashboard-link">
            <span>▦</span>
            Overview
          </a>

          <a href="#post-donation">
            <span>🍱</span>
            Post Donation
          </a>

          <a href="#my-donations">
            <span>📦</span>
            My Donations
          </a>
        </nav>

        <div className="safety-note">
          <h3>Food Safety Reminder</h3>
          <p>
            Upload clear food and packaging images. Mention correct preparation
            time, pickup deadline and packaging condition before posting surplus
            food.
          </p>
        </div>

        <a href="#logout" className="logout-link" onClick={handleLogout}>
          ← Logout
        </a>
      </aside>

      <main className="dashboard-main">
        <section className="dashboard-header" id="overview">
          <div>
            <p className="dashboard-label">DONOR DASHBOARD</p>
            <h1>
              Welcome, {savedUser.fullName || savedUser.name || "Food Donor"}
            </h1>
            <span>
              {savedUser.organisation || "Registered Donor"} •{" "}
              {savedUser.location || "Food Donation Location"}
            </span>
          </div>

          <div style={{ display: "flex", gap: "14px", flexWrap: "wrap" }}>
            <button className="view-home-button" onClick={loadDashboardData}>
              Refresh Donations
            </button>

            <Link to="/" className="view-home-button">
              View Homepage
            </Link>
          </div>
        </section>

        <div className="demo-information">
          <strong>Secure donor workflow connected:</strong> Your donations are
          saved in MongoDB using your authenticated donor account. New listings
          include AI priority prediction, confidence information and uploaded
          food images.
        </div>

        <section className="dashboard-statistics">
          <div className="statistic-card">
            <div className="stat-icon green">🍱</div>
            <div>
              <p>Active Donations</p>
              <h2>{statistics.activeDonations}</h2>
            </div>
          </div>

          <div className="statistic-card">
            <div className="stat-icon orange">🤝</div>
            <div>
              <p>Accepted Pickups</p>
              <h2>{statistics.acceptedPickups}</h2>
            </div>
          </div>

          <div className="statistic-card">
            <div className="stat-icon blue">🚚</div>
            <div>
              <p>Completed Pickups</p>
              <h2>{statistics.completedPickups}</h2>
            </div>
          </div>

          <div className="statistic-card">
            <div className="stat-icon red">⚡</div>
            <div>
              <p>High Priority</p>
              <h2>{statistics.highPriorityDonations}</h2>
            </div>
          </div>

          <div className="statistic-card">
            <div className="stat-icon green">🍽️</div>
            <div>
              <p>Meals Saved</p>
              <h2>{statistics.mealsSaved}</h2>
            </div>
          </div>
        </section>

        <section className="dashboard-content-grid">
          <div className="donation-form-container" id="post-donation">
            <div className="dashboard-section-title">
              <div>
                <p>CREATE DONATION</p>
                <h2>Post New Food Donation</h2>
              </div>
            </div>

            {message && <div className="success-message">{message}</div>}

            <form className="donation-form" onSubmit={handleSubmit}>
              <div className="donation-form-row">
                <label>
                  Food Name
                  <input
                    type="text"
                    name="foodName"
                    value={formData.foodName}
                    onChange={handleInputChange}
                    placeholder="Example: Veg Biryani"
                    required
                  />
                </label>

                <label>
                  Food Category
                  <select
                    name="category"
                    value={formData.category}
                    onChange={handleInputChange}
                    required
                  >
                    <option value="Cooked Meal">Cooked Meal</option>
                    <option value="Packaged Food">Packaged Food</option>
                    <option value="Bakery">Bakery</option>
                    <option value="Fruits">Fruits</option>
                    <option value="Vegetables">Vegetables</option>
                    <option value="Dairy">Dairy</option>
                    <option value="Snacks">Snacks</option>
                  </select>
                </label>
              </div>

              <div className="donation-form-row">
                <label>
                  Servings
                  <input
                    type="number"
                    name="servings"
                    value={formData.servings}
                    onChange={handleInputChange}
                    placeholder="Example: 50"
                    min="1"
                    required
                  />
                </label>

                <label>
                  Preparation Time
                  <input
                    type="text"
                    name="preparationTime"
                    value={formData.preparationTime}
                    onChange={handleInputChange}
                    placeholder="Example: Prepared 1 hour ago"
                    required
                  />
                </label>
              </div>

              <label>
                Pickup Deadline
                <input
                  type="datetime-local"
                  name="pickupDeadline"
                  value={formData.pickupDeadline}
                  onChange={handleInputChange}
                  required
                />
              </label>

              <label>
                Pickup Location
                <input
                  type="text"
                  name="location"
                  value={formData.location}
                  onChange={handleInputChange}
                  placeholder="Example: Solapur, Maharashtra"
                  required
                />
              </label>

              <label>
                Packaging Condition
                <textarea
                  name="packagingCondition"
                  value={formData.packagingCondition}
                  onChange={handleInputChange}
                  placeholder="Example: Packed in clean covered containers"
                  required
                />
              </label>

              <div className="donation-form-row">
                <label>
                  Food Image
                  <input
                    id="foodImage"
                    type="file"
                    accept="image/*"
                    onChange={handleFoodImageChange}
                  />

                  {foodImagePreview && (
                    <img
                      className="donation-image-preview"
                      src={foodImagePreview}
                      alt="Food preview"
                    />
                  )}
                </label>

                <label>
                  Packaging Image
                  <input
                    id="packagingImage"
                    type="file"
                    accept="image/*"
                    onChange={handlePackagingImageChange}
                  />

                  {packagingImagePreview && (
                    <img
                      className="donation-image-preview"
                      src={packagingImagePreview}
                      alt="Packaging preview"
                    />
                  )}
                </label>
              </div>

              <button
                className="post-donation-button"
                type="submit"
                disabled={loading}
              >
                {loading ? "Posting Donation..." : "Post Donation"}
              </button>
            </form>
          </div>

          <div className="donation-list-container" id="my-donations">
            <div className="dashboard-section-title">
              <div>
                <p>DONATION HISTORY</p>
                <h2>My Donations</h2>
              </div>

              <span className="listing-count">
                {donations.length} {donations.length === 1 ? "Item" : "Items"}
              </span>
            </div>

            {pageLoading ? (
              <div className="empty-state">
                <h3>Loading donations...</h3>
                <p>Please wait while your donation records are loaded.</p>
              </div>
            ) : donations.length === 0 ? (
              <div className="empty-state">
                <h3>No donations posted yet</h3>
                <p>Your posted food donations will appear here.</p>
              </div>
            ) : (
              <div className="donation-list">
                {donations.map((donation) => (
                  <div className="donation-record" key={donation.id}>
                    <div className="record-top">
                      <div>
                        <h3>{donation.foodName}</h3>
                        <p>{donation.category}</p>
                      </div>

                      <span
                        className={`priority-pill ${donation.priority?.toLowerCase()}`}
                      >
                        AI Priority: {donation.priority}
                      </span>
                    </div>

                    {(donation.foodImage || donation.packagingImage) && (
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
                    )}

                    <div className="record-information">
                      <div>
                        <span>Servings</span>
                        <strong>{donation.servings}</strong>
                      </div>

                      <div>
                        <span>Status</span>
                        <strong
                          className={
                            donation.status === "Collected"
                              ? "collected-status"
                              : "active-status"
                          }
                        >
                          {donation.status}
                        </strong>
                      </div>

                      <div>
                        <span>AI Confidence</span>
                        <strong>
                          {donation.aiConfidence !== null &&
                          donation.aiConfidence !== undefined
                            ? `${donation.aiConfidence}%`
                            : "Not available"}
                        </strong>
                      </div>

                      <div>
                        <span>Prediction</span>
                        <strong>
                          {donation.predictionMethod || "rule_fallback"}
                        </strong>
                      </div>
                    </div>

                    <p className="record-location">
                      📍 <strong>Location:</strong> {donation.location}
                    </p>

                    <p className="record-deadline">
                      ⏰ <strong>Pickup Deadline:</strong>{" "}
                      {formatDateTime(donation.pickupDeadline)}
                    </p>

                    <p className="record-deadline">
                      📦 <strong>Packaging:</strong>{" "}
                      {donation.packagingCondition}
                    </p>

                    {donation.acceptedByOrganisation && (
                      <p className="record-location">
                        🤝 <strong>Accepted By:</strong>{" "}
                        {donation.acceptedByOrganisation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

export default DonorDashboard;