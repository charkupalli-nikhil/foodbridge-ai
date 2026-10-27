import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import API from "../api/axios";
import "./Dashboard.css";
import NotificationBell from "../components/NotificationBell";
import CameraCaptureModal from "../components/CameraCaptureModal";

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

  // Live camera capture states
  const [isCameraModalOpen, setIsCameraModalOpen] = useState(false);
  const [cameraTarget, setCameraTarget] = useState("food"); // "food" | "packaging"
  const [captureToken, setCaptureToken] = useState("");
  const [captureCoords, setCaptureCoords] = useState({ lat: null, lng: null });
  const [pickupCoords, setPickupCoords] = useState({ lat: null, lng: null });
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);

  const [verificationState, setVerificationState] = useState({
    status: "idle", // "idle" | "verifying" | "accepted" | "rejected" | "unverified"
    verdict: "",
    confidence: null,
    detectedFood: "",
    reason: "",
    fssaiDisclaimer: "",
    imageOriginality: null,
    originalityReasons: [],
  });

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
  const handleOpenCameraModal = async (target = "food") => {
    setCameraTarget(target);
    if (target === "food") {
      try {
        const res = await API.post("/donations/capture-session");
        if (res.data?.captureToken) {
          setCaptureToken(res.data.captureToken);
        }
      } catch (err) {
        console.warn("[Camera Session] Could not obtain capture token:", err);
      }
    }
    setIsCameraModalOpen(true);
  };

  const verifyAndSetFoodImage = async (file, captureMethod = "live_camera", meta = {}) => {
    setFoodImageFile(file);
    setFoodImagePreview(URL.createObjectURL(file));

    setVerificationState({
      status: "verifying",
      verdict: "",
      confidence: null,
      detectedFood: "",
      reason: "",
      fssaiDisclaimer: "",
      imageOriginality: null,
      originalityReasons: [],
    });

    try {
      const verifyFormData = new FormData();
      verifyFormData.append("file", file);
      verifyFormData.append("foodName", formData.foodName.trim());
      verifyFormData.append("category", formData.category);
      if (captureToken) {
        verifyFormData.append("captureToken", captureToken);
      }
      verifyFormData.append("captureMethod", captureMethod);
      if (meta?.captureLat != null) {
        verifyFormData.append("captureLat", meta.captureLat);
      }
      if (meta?.captureLng != null) {
        verifyFormData.append("captureLng", meta.captureLng);
      }

      const response = await API.post("/donations/verify-image", verifyFormData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const res = response.data;
      setVerificationState({
        status: (res.verdict || "Unverified").toLowerCase(),
        verdict: res.verdict,
        confidence: res.confidence,
        detectedFood: res.detectedFood,
        reason: res.rejectionReason,
        fssaiDisclaimer:
          res.screeningDisclaimer ||
          "AI-assisted visual screening aligned with FSSAI guidance. Visual screening only; not a laboratory or medical certification.",
        imageOriginality: res.imageOriginality || "Likely Original",
        originalityReasons: res.originalityReasons || [],
      });
    } catch (err) {
      console.error("Food image pre-verification failed:", err);
      const detail =
        err.response?.data?.detail ||
        "Food image verification failed. Please upload a clear photo of edible food.";
      setVerificationState({
        status: "rejected",
        verdict: "Rejected",
        confidence: 0,
        detectedFood: "",
        reason: detail,
        fssaiDisclaimer: "Visual screening failed to verify food authenticity.",
        imageOriginality: "Suspicious",
        originalityReasons: [detail],
      });
    }
  };

  const handleCameraCaptured = (blob, metadata) => {
    if (cameraTarget === "packaging") {
      const file = new File([blob], `live_packaging_capture_${Date.now()}.jpg`, {
        type: "image/jpeg",
      });
      setPackagingImageFile(file);
      setPackagingImagePreview(URL.createObjectURL(file));
      return;
    }

    const file = new File([blob], `live_food_capture_${Date.now()}.jpg`, {
      type: "image/jpeg",
    });
    setCaptureCoords({
      lat: metadata?.captureLat || null,
      lng: metadata?.captureLng || null,
    });
    verifyAndSetFoodImage(file, "live_camera", metadata);
  };

  const handleFoodImageChange = (event) => {
    const file = event.target.files[0];
    if (!file) {
      setFoodImageFile(null);
      setFoodImagePreview("");
      setVerificationState({
        status: "idle",
        verdict: "",
        confidence: null,
        detectedFood: "",
        reason: "",
        fssaiDisclaimer: "",
        imageOriginality: null,
        originalityReasons: [],
      });
      return;
    }

    verifyAndSetFoodImage(file, "gallery_upload");
  };

  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setIsDetectingLocation(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        setPickupCoords({ lat: latitude, lng: longitude });

        // Reverse geocode via OSM Nominatim
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
            {
              headers: { "User-Agent": "FoodBridgeAI/1.0" },
            }
          );
          if (res.ok) {
            const data = await res.json();
            if (data.display_name) {
              setFormData((prev) => ({
                ...prev,
                location: data.display_name,
              }));
              setIsDetectingLocation(false);
              return;
            }
          }
        } catch (e) {
          console.warn("[Reverse Geocode] error:", e);
        }

        setFormData((prev) => ({
          ...prev,
          location: `Lat: ${latitude.toFixed(4)}, Lng: ${longitude.toFixed(4)}`,
        }));
        setIsDetectingLocation(false);
      },
      (err) => {
        console.error("GPS detection failed:", err);
        alert("Could not access GPS location. Please check your browser permissions.");
        setIsDetectingLocation(false);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
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

    if (!foodImageFile) {
      setMessage("Please upload a food image for AI inspection screening.");
      return;
    }

    if (verificationState.status === "verifying") {
      setMessage("Please wait for AI food quality screening to complete.");
      return;
    }

    if (verificationState.verdict !== "Accepted") {
      setMessage(
        verificationState.reason
          ? `Food image rejected: ${verificationState.reason}. Please upload a clear photo of edible food.`
          : "Please upload a valid food photo that passes AI visual quality screening."
      );
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
        captureToken: captureToken || undefined,
        captureMethod: captureToken ? "live_camera" : "gallery_upload",
        captureLat: captureCoords.lat,
        captureLng: captureCoords.lng,
        pickupLat: pickupCoords.lat,
        pickupLng: pickupCoords.lng,
      };

      await API.post("/donations", donationPayload);

      setMessage("Donation posted successfully with live food authenticity screening.");

      setFormData({
        foodName: "",
        category: "Cooked Meal",
        servings: "",
        preparationTime: "",
        pickupDeadline: "",
        location: savedUser.location || "",
        packagingCondition: "",
      });

      setCaptureToken("");
      setCaptureCoords({ lat: null, lng: null });
      setPickupCoords({ lat: null, lng: null });

      setFoodImageFile(null);
      setPackagingImageFile(null);
      setFoodImagePreview("");
      setPackagingImagePreview("");
      setVerificationState({
        status: "idle",
        verdict: "",
        confidence: null,
        detectedFood: "",
        reason: "",
        fssaiDisclaimer: "",
      });

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

          <div style={{ display: "flex", gap: "14px", flexWrap: "wrap", alignItems: "center" }}>
            <NotificationBell />
            <button className="view-home-button" onClick={loadDashboardData}>
              Refresh Donations
            </button>

            <Link to="/" className="view-home-button">
              View Homepage
            </Link>
          </div>
        </section>

        <div className="demo-information">
          <strong>Food redistribution platform:</strong> Surplus meals are screened
          for safety aligned with FSSAI guidance, matched with verified local
          receiver organizations, and scheduled for timely pickup.
        </div>

        {savedUser?.trustScore < 70 && (
           <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '16px', borderRadius: '8px', marginBottom: '20px', color: '#991b1b' }}>
             <strong>⚠️ Trust Score Warning:</strong> Your donor trust score has dropped to {savedUser.trustScore}/100 due to poor receiver feedback or duplicate image uploads. If it drops below 40, your account will be suspended.
           </div>
        )}
        {savedUser?.trustScore >= 70 && (
           <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '16px', borderRadius: '8px', marginBottom: '20px', color: '#166534' }}>
             <strong>🛡️ Trust Score: {savedUser.trustScore}/100</strong> - Excellent! Your high food quality and accurate listings are helping the community.
           </div>
        )}

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

        {statistics.monthlyDonations && statistics.monthlyDonations.length > 0 && (
          <section className="analytics-section" style={{ background: '#fff', padding: '24px', borderRadius: '12px', marginTop: '24px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#1e293b' }}>Monthly Donation Impact</h3>
            <div style={{ height: 300, marginTop: '20px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={statistics.monthlyDonations}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                  <XAxis dataKey="month" axisLine={false} tickLine={false} />
                  <YAxis axisLine={false} tickLine={false} />
                  <Tooltip cursor={{fill: 'transparent'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }} />
                  <Line type="monotone" dataKey="count" stroke="#16a34a" strokeWidth={3} dot={{r: 4, fill: '#16a34a'}} activeDot={{r: 6}} name="Donations" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

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
                <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
                  <input
                    type="text"
                    name="location"
                    value={formData.location}
                    onChange={handleInputChange}
                    placeholder="Example: Solapur, Maharashtra"
                    required
                    style={{ flex: 1 }}
                  />
                  <button
                    type="button"
                    className="btn-detect-loc"
                    onClick={handleDetectLocation}
                    disabled={isDetectingLocation}
                    title="Detect current GPS location"
                    style={{
                      background: "#f1f5f9",
                      border: "1px solid #cbd5e1",
                      borderRadius: "8px",
                      padding: "0 12px",
                      cursor: "pointer",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      color: "#334155",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {isDetectingLocation ? "Detecting..." : "📍 GPS"}
                  </button>
                </div>
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
                  Food Image <span style={{ color: "#ef4444" }}>*</span>
                  <div style={{ display: "flex", gap: "10px", marginTop: "6px", marginBottom: "8px", flexWrap: "wrap", alignItems: "center" }}>
                    <button
                      type="button"
                      className="btn-camera-trigger"
                      onClick={handleOpenCameraModal}
                      style={{
                        background: "#10b981",
                        color: "#fff",
                        border: "none",
                        padding: "8px 16px",
                        borderRadius: "8px",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        boxShadow: "0 2px 6px rgba(16, 185, 129, 0.3)",
                      }}
                    >
                      📷 Capture Live Photo
                    </button>
                    {import.meta.env.VITE_ALLOW_GALLERY_UPLOAD === "true" && (
                      <input
                        id="foodImage"
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={handleFoodImageChange}
                        style={{ maxWidth: "200px" }}
                      />
                    )}
                  </div>

                  {foodImagePreview && (
                    <img
                      className="donation-image-preview"
                      src={foodImagePreview}
                      alt="Food preview"
                    />
                  )}

                  {verificationState.status === "verifying" && (
                    <div className="verification-badge verifying">
                      ⏳ Screening image authenticity & quality with Google Gemini AI...
                    </div>
                  )}

                  {verificationState.status === "accepted" && (
                    <div className="verification-badge accepted">
                      <div className="badge-title">✅ Food Quality Verified</div>
                      <div className="badge-detail">
                        Detected: <strong>{verificationState.detectedFood || "Food"}</strong>
                      </div>
                      {verificationState.imageOriginality && (
                        <div style={{ marginTop: "6px", fontSize: "0.85rem", fontWeight: 600 }}>
                          🛡️ Authenticity:{" "}
                          <span
                            style={{
                              color:
                                verificationState.imageOriginality === "Likely Original"
                                  ? "#059669"
                                  : "#d97706",
                            }}
                          >
                            {verificationState.imageOriginality}
                          </span>
                        </div>
                      )}
                      <div className="badge-disclaimer">
                        ℹ️ {verificationState.fssaiDisclaimer}
                      </div>
                    </div>
                  )}

                  {verificationState.status === "rejected" && (
                    <div className="verification-badge rejected">
                      <div className="badge-title">❌ Image Verification Failed</div>
                      <div className="badge-detail">
                        {verificationState.reason || "Uploaded image does not appear to be edible food or is an unverified web/duplicate image."}
                      </div>
                      {verificationState.originalityReasons?.length > 0 && (
                        <div style={{ fontSize: "0.8rem", marginTop: "4px", color: "#991b1b" }}>
                          {verificationState.originalityReasons.join(" • ")}
                        </div>
                      )}
                      <div className="badge-tip">
                        Please take a live, original photograph of the prepared meal. Internet images, photos of screens, and non-food photos are strictly rejected.
                      </div>
                    </div>
                  )}

                  {verificationState.status === "unverified" && (
                    <div className="verification-badge unverified">
                      <div className="badge-title">⚠️ Image Unverified</div>
                      <div className="badge-detail">{verificationState.reason || "Unable to confirm food quality visually."}</div>
                    </div>
                  )}
                </label>

                <label>
                  <span>Packaging Image (Optional)</span>
                  <div style={{ display: "flex", gap: "10px", alignItems: "center", marginTop: "8px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn-camera-trigger"
                      onClick={() => handleOpenCameraModal("packaging")}
                      style={{
                        background: "#0284c7",
                        color: "#fff",
                        border: "none",
                        padding: "8px 16px",
                        borderRadius: "8px",
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        boxShadow: "0 2px 6px rgba(2, 132, 199, 0.3)",
                      }}
                    >
                      📷 Capture Packaging
                    </button>

                    {import.meta.env.VITE_ALLOW_GALLERY_UPLOAD === "true" && (
                      <input
                        id="packagingImage"
                        type="file"
                        accept="image/*"
                        capture="environment"
                        onChange={handlePackagingImageChange}
                        style={{ maxWidth: "200px" }}
                      />
                    )}

                    {packagingImagePreview && (
                      <button
                        type="button"
                        onClick={() => {
                          setPackagingImageFile(null);
                          setPackagingImagePreview("");
                        }}
                        style={{
                          background: "#f1f5f9",
                          color: "#dc2626",
                          border: "1px solid #fecaca",
                          padding: "6px 12px",
                          borderRadius: "6px",
                          fontSize: "0.85rem",
                          cursor: "pointer",
                          fontWeight: 600,
                        }}
                      >
                        ✕ Remove
                      </button>
                    )}
                  </div>

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
                disabled={loading || !foodImageFile || verificationState.status !== "accepted"}
                title={
                  !foodImageFile
                    ? "Please upload a food image first"
                    : verificationState.status !== "accepted"
                    ? "Wait for food quality screening to pass"
                    : "Post this donation"
                }
              >
                {loading
                  ? "Posting Donation..."
                  : verificationState.status === "verifying"
                  ? "Screening Image..."
                  : "Post Donation"}
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
                {donations.map((donation) => {
                  const remaining = donation.remainingServings ?? donation.servings;
                  const statusClass =
                    donation.status === "Collected"
                      ? "collected-status"
                      : donation.status === "Partially Accepted"
                      ? "partially-accepted-status"
                      : donation.status === "Accepted"
                      ? "accepted-status"
                      : "active-status";

                  return (
                    <div
                      className="donation-record"
                      key={donation.id}
                      id={`donation-${donation.id}`}
                    >
                      <div className="record-top">
                        <div>
                          <h3>{donation.foodName}</h3>
                          <p>{donation.category}</p>
                        </div>

                        <span
                          className={`priority-pill ${donation.priority?.toLowerCase()}`}
                        >
                          Priority: {donation.priority}
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
                          <strong>
                            {remaining} / {donation.servings} remaining
                          </strong>
                        </div>

                        <div>
                          <span>Status</span>
                          <strong className={statusClass}>
                            {donation.status}
                          </strong>
                        </div>

                        {donation.imageOriginality && (
                          <div>
                            <span>Originality</span>
                            <strong
                              style={{
                                color:
                                  donation.imageOriginality === "Likely Original"
                                    ? "#059669"
                                    : "#d97706",
                              }}
                            >
                              {donation.imageOriginality}
                            </strong>
                          </div>
                        )}
                      </div>

                      {donation.claims && donation.claims.length > 0 && (
                        <div className="donation-claims-box">
                          <h4 className="claims-title">Receiver Claims</h4>
                          <div className="claims-grid">
                            {donation.claims.map((claim) => (
                              <div key={claim.id} className="claim-card-mini">
                                <div className="claim-org-name">
                                  🏢 {claim.receiverOrgName || "Receiver Org"}
                                </div>
                                <div className="claim-details">
                                  <span>
                                    <strong>{claim.quantity}</strong> servings
                                  </span>
                                  <span
                                    className={`claim-status-badge ${claim.status
                                      .toLowerCase()
                                      .replace(/\s+/g, "-")}`}
                                  >
                                    {claim.status}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

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
                );
              })}
            </div>
          )}
          </div>
        </section>
      </main>

      {/* Live Camera Capture Modal */}
      <CameraCaptureModal
        isOpen={isCameraModalOpen}
        onClose={() => setIsCameraModalOpen(false)}
        onCapture={handleCameraCaptured}
        title={cameraTarget === "packaging" ? "Capture Packaging Photo" : "Capture Live Food Photo"}
        guidelineText={
          cameraTarget === "packaging"
            ? "Position the food container, box, or packaging clearly in the frame"
            : "Center the prepared food clearly under good lighting"
        }
      />
    </div>
  );
}

export default DonorDashboard;