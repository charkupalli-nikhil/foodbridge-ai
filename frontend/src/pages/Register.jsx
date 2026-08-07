import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Auth.css";

import { API_BASE_URL } from "../config";

const FOOD_TYPES = [
  "Cooked Food",
  "Packed Food",
  "Dry Ration",
  "Fruits & Vegetables",
  "Bakery Items",
  "Milk & Dairy",
  "Beverages",
];

async function getApiErrorMessage(response) {
  try {
    const errorData = await response.json();

    if (typeof errorData.detail === "string") {
      return errorData.detail;
    }

    if (Array.isArray(errorData.detail)) {
      return errorData.detail
        .map((errorItem) => errorItem.msg)
        .join(" ");
    }

    return "Unable to create your account.";
  } catch {
    return "Unable to create your account.";
  }
}

function saveAuthenticatedSession(authData) {
  localStorage.setItem("foodbridge_access_token", authData.accessToken);
  localStorage.setItem("foodbridge_user", JSON.stringify(authData.user));

  if (authData.user.role === "donor") {
    localStorage.setItem(
      "foodbridge_demo_donor",
      JSON.stringify(authData.user)
    );
  }

  if (authData.user.role === "ngo") {
    localStorage.setItem(
      "foodbridge_demo_ngo",
      JSON.stringify(authData.user)
    );
  }
}

function Register() {
  const navigate = useNavigate();

  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    organisation: "",
    role: "",
    organizationType: "",
    description: "",
    capacity: "",
    operatingHours: "",
    acceptedFoodTypes: [],
    location: "",
    contactNumber: "",
    password: "",
    safetyAgreement: false,
  });

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;

    setFormData((previousData) => ({
      ...previousData,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleFoodTypeChange = (event) => {
    const { value, checked } = event.target;

    setFormData((previousData) => ({
      ...previousData,
      acceptedFoodTypes: checked
        ? [...previousData.acceptedFoodTypes, value]
        : previousData.acceptedFoodTypes.filter(
            (foodType) => foodType !== value
          ),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    try {
      setErrorMessage("");
      setIsSubmitting(true);

      // Prevent submission if NGO hasn't selected any food types
      if (
        formData.role === "ngo" &&
        formData.acceptedFoodTypes.length === 0
      ) {
        setErrorMessage(
          "Please select at least one accepted food type."
        );
        setIsSubmitting(false);
        return;
      }

      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...formData,
          capacity: formData.capacity ? Number(formData.capacity) : null,
        }),
      });

      if (!response.ok) {
        const message = await getApiErrorMessage(response);
        throw new Error(message);
      }

      const authData = await response.json();

      saveAuthenticatedSession(authData);

      if (authData.user.role === "donor") {
        navigate("/donor-dashboard");
        return;
      }

      navigate("/ngo-dashboard");
    } catch (error) {
      setErrorMessage(error.message || "Unable to create your account.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <section className="auth-info">
        <Link to="/" className="auth-brand">
          <span>🍃</span>
          <div>
            <h2>FoodBridge AI</h2>
            <p>Rescue food. Serve communities.</p>
          </div>
        </Link>

        <div className="auth-message">
          <p className="auth-label">JOIN THE NETWORK</p>
          <h1>Turn surplus food into meaningful support.</h1>
          <p className="auth-text">
            Create your account as a food donor or a verified receiver organization
            such as an NGO, orphanage, old age home, shelter home, community kitchen,
            or food bank, and help ensure surplus food reaches people in need instead
            of being wasted.
          </p>

          <div className="auth-benefits">
            <div>
              <span>✓</span>
              Register your organisation
            </div>
            <div>
              <span>✓</span>
              Post or receive food donations
            </div>
            <div>
              <span>✓</span>
              Record measurable social impact
            </div>
          </div>
        </div>
      </section>

      <section className="auth-form-area">
        <div className="auth-card register-card">
          <div className="auth-card-header">
            <h2>Create Account</h2>
            <p>Register as a food donor or verified receiver organization.</p>
          </div>

          {errorMessage && (
            <div
              role="alert"
              style={{
                marginBottom: "21px",
                padding: "13px 15px",
                borderRadius: "10px",
                border: "1px solid #fecaca",
                background: "#fee2e2",
                color: "#b91c1c",
                fontSize: "14px",
                fontWeight: "600",
                lineHeight: "1.5",
              }}
            >
              {errorMessage}
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="form-row">
              <label htmlFor="full-name">
                Full Name
                <input
                  id="full-name"
                  name="fullName"
                  type="text"
                  placeholder="Enter your full name"
                  value={formData.fullName}
                  onChange={handleChange}
                  required
                />
              </label>

              <label htmlFor="register-email">
                Email Address
                <input
                  id="register-email"
                  name="email"
                  type="email"
                  placeholder="example@email.com"
                  value={formData.email}
                  onChange={handleChange}
                  required
                />
              </label>
            </div>

            <div className="form-row">
              <label htmlFor="organisation-name">
                Organisation Name / Individual Name
                <input
                  id="organisation-name"
                  name="organisation"
                  type="text"
                  placeholder="Enter your name or organization name"
                  value={formData.organisation}
                  onChange={handleChange}
                  required
                />
              </label>

              <label htmlFor="register-role">
                Register As
                <select
                  id="register-role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                  required
                >
                  <option value="" disabled>
                    Select your role
                  </option>
                  <option value="donor">Food Donor</option>
                  <option value="ngo">Receiver Organization</option>
                </select>
              </label>
            </div>

            {formData.role === "ngo" && (
              <>
                <label htmlFor="organization-type">
                  Organization Type
                  <select
                    id="organization-type"
                    name="organizationType"
                    value={formData.organizationType}
                    onChange={handleChange}
                    required
                  >
                    <option value="" disabled>
                      Select Organization Type
                    </option>
                    <option value="NGO">NGO</option>
                    <option value="Orphanage">Orphanage</option>
                    <option value="Old Age Home">Old Age Home</option>
                    <option value="Shelter Home">Shelter Home</option>
                    <option value="Community Kitchen">Community Kitchen</option>
                    <option value="Food Bank">Food Bank</option>
                    <option value="Religious Trust">Religious Trust</option>
                    <option value="Other">Other</option>
                  </select>
                </label>

                <label htmlFor="organization-description">
                  About Organization
                  <textarea
                    id="organization-description"
                    name="description"
                    placeholder="Briefly describe your organization and the people you support..."
                    value={formData.description}
                    onChange={handleChange}
                    rows={4}
                    maxLength={500}
                    style={{
                      resize: "vertical",
                      minHeight: "100px",
                    }}
                  />
                </label>

                <label htmlFor="capacity">
                  Daily Meal Capacity
                  <input
                    id="capacity"
                    name="capacity"
                    type="number"
                    min={1}
                    placeholder="Example: 250"
                    value={formData.capacity}
                    onChange={handleChange}
                  />
                </label>

                <label htmlFor="operating-hours">
                  Operating Hours
                  <input
                    id="operating-hours"
                    name="operatingHours"
                    type="text"
                    placeholder="9:00 AM - 7:00 PM"
                    value={formData.operatingHours}
                    onChange={handleChange}
                  />
                </label>

                <div className="food-types-section">
                  <label htmlFor="food-types">Accepted Food Types</label>
                  <div
                    id="food-types"
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(2, 1fr)",
                      gap: "10px",
                      marginTop: "10px",
                    }}
                  >
                    {FOOD_TYPES.map((foodType) => (
                      <label
                        key={foodType}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          fontWeight: "400",
                        }}
                      >
                        <input
                          type="checkbox"
                          value={foodType}
                          checked={formData.acceptedFoodTypes.includes(
                            foodType
                          )}
                          onChange={handleFoodTypeChange}
                        />
                        {foodType}
                      </label>
                    ))}
                  </div>
                </div>
              </>
            )}

            <label htmlFor="register-location">
              {formData.role === "ngo" ? "Operating Location" : "Location / City"}
              <input
                id="register-location"
                name="location"
                type="text"
                placeholder="Enter city or operating area"
                value={formData.location}
                onChange={handleChange}
                required
              />
            </label>

            <div className="form-row">
              <label htmlFor="contact-number">
                Contact Number
                <input
                  id="contact-number"
                  name="contactNumber"
                  type="tel"
                  minLength="10"
                  maxLength="15"
                  placeholder="Enter mobile number"
                  value={formData.contactNumber}
                  onChange={handleChange}
                  required
                />
              </label>

              <label htmlFor="register-password">
                Password
                <input
                  id="register-password"
                  name="password"
                  type="password"
                  minLength="6"
                  placeholder="Minimum 6 characters"
                  value={formData.password}
                  onChange={handleChange}
                  required
                />
              </label>
            </div>

            <label className="terms-option">
              <input
                name="safetyAgreement"
                type="checkbox"
                checked={formData.safetyAgreement}
                onChange={handleChange}
                required
              />
              <span>
                I agree that food quality verification and safe distribution
                procedures remain the responsibility of the participating
                organisation.
              </span>
            </label>

            <button
              className="auth-submit"
              type="submit"
              disabled={isSubmitting}
              style={{
                opacity: isSubmitting ? 0.7 : 1,
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              {isSubmitting ? "Creating Account..." : "Create Account"}
            </button>
          </form>

          <p className="auth-switch">
            Already registered? <Link to="/login">Login here</Link>
          </p>

          <Link to="/" className="back-link">
            ← Back to Home
          </Link>
        </div>
      </section>
    </div>
  );
}

export default Register;