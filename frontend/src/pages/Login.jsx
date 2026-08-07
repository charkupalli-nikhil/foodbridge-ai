import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Auth.css";

import { API_BASE_URL } from "../config";

async function getApiErrorMessage(response) {
  try {
    const errorData = await response.json();

    if (typeof errorData.detail === "string") {
      return errorData.detail;
    }

    if (Array.isArray(errorData.detail)) {
      return errorData.detail.map((errorItem) => errorItem.msg).join(" ");
    }

    return "Unable to login to your account.";
  } catch {
    return "Unable to login to your account.";
  }
}

function saveAuthenticatedSession(authData) {
  localStorage.setItem("accessToken", authData.accessToken);
  localStorage.setItem("token", authData.accessToken);
  localStorage.setItem("user", JSON.stringify(authData.user));

  localStorage.setItem("foodbridge_access_token", authData.accessToken);
  localStorage.setItem("foodbridge_user", JSON.stringify(authData.user));

  if (authData.user.role === "donor") {
    localStorage.setItem("foodbridge_demo_donor", JSON.stringify(authData.user));
  }

  if (authData.user.role === "ngo") {
    localStorage.setItem("foodbridge_demo_ngo", JSON.stringify(authData.user));
  }

  if (authData.user.role === "admin") {
    localStorage.setItem("foodbridge_demo_admin", JSON.stringify(authData.user));
  }
}

function Login() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: "",
    password: "",
    role: "",
    rememberMe: false,
  });

  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value, type, checked } = event.target;

    setFormData((previousData) => ({
      ...previousData,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!formData.role) {
      setErrorMessage("Please select your login role.");
      return;
    }

    try {
      setErrorMessage("");
      setIsSubmitting(true);

      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: formData.email.trim(),
          password: formData.password,
          role: formData.role,
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

      if (authData.user.role === "ngo") {
        navigate("/ngo-dashboard");
        return;
      }

      if (authData.user.role === "admin") {
        navigate("/admin-dashboard");
        return;
      }

      navigate("/");
    } catch (error) {
      setErrorMessage(error.message || "Unable to login to your account.");
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
          <p className="auth-label">WELCOME BACK</p>

          <h1>Continue rescuing surplus food.</h1>

          <p className="auth-text">
            Login as a donor, NGO partner or administrator to manage food
            requests, coordinate collections and monitor platform impact.
          </p>

          <div className="auth-benefits">
            <div>
              <span>✓</span>
              Manage active food donations
            </div>

            <div>
              <span>✓</span>
              Accept nearby pickup requests
            </div>

            <div>
              <span>✓</span>
              Monitor recovered meal impact
            </div>
          </div>
        </div>
      </section>

      <section className="auth-form-area">
        <div className="auth-card">
          <div className="auth-card-header">
            <h2>Login</h2>
            <p>Enter your registered account details to continue.</p>
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
            <label htmlFor="login-email">
              Email Address
              <input
                id="login-email"
                name="email"
                type="email"
                placeholder="example@email.com"
                value={formData.email}
                onChange={handleChange}
                required
              />
            </label>

            <label htmlFor="login-password">
              Password
              <input
                id="login-password"
                name="password"
                type="password"
                minLength="6"
                placeholder="Enter your password"
                value={formData.password}
                onChange={handleChange}
                required
              />
            </label>

            <label htmlFor="login-role">
              Login As
              <select
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

            <div className="form-help-row">
              <label className="remember-option">
                <input
                  name="rememberMe"
                  type="checkbox"
                  checked={formData.rememberMe}
                  onChange={handleChange}
                />
                <span>Remember me</span>
              </label>

              <button className="forgot-button" type="button">
                Forgot Password?
              </button>
            </div>

            <button
              className="auth-submit"
              type="submit"
              disabled={isSubmitting}
              style={{
                opacity: isSubmitting ? 0.7 : 1,
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              {isSubmitting ? "Logging In..." : "Login to FoodBridge"}
            </button>
          </form>

          <p className="auth-switch">
            Do not have an account?{" "}
            <Link to="/register">Create an account</Link>
          </p>

          <Link to="/" className="back-link">
            ← Back to Home
          </Link>
        </div>
      </section>
    </div>
  );
}

export default Login;