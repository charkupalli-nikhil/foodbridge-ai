import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./Dashboard.css";
import "./ReceiverVerification.css";
import { API_BASE_URL } from "../config";

function getStoredUser() {
  const storedUser =
    localStorage.getItem("user") || localStorage.getItem("foodbridge_user");
  if (!storedUser) return null;
  try {
    return JSON.parse(storedUser);
  } catch {
    return null;
  }
}

function clearSession() {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  localStorage.removeItem("foodbridge_access_token");
  localStorage.removeItem("foodbridge_user");
}

async function readErrorMessage(response) {
  try {
    const errorData = await response.json();
    if (typeof errorData.detail === "string") return errorData.detail;
    if (Array.isArray(errorData.detail)) return errorData.detail.map((error) => error.msg).join(" ");
    return "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

function ReceiverVerification() {
  const navigate = useNavigate();
  const [userProfile, setUserProfile] = useState(getStoredUser());
  const [isLoading, setIsLoading] = useState(true);
  const [uploadingDoc, setUploadingDoc] = useState("");
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

  const fetchProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await authenticatedRequest("/auth/me");
      if (!response.ok) throw new Error("Failed to load user profile");
      const data = await response.json();
      setUserProfile(data);
      // Update local storage
      localStorage.setItem("foodbridge_user", JSON.stringify(data));
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [authenticatedRequest]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleFileUpload = async (event, documentType) => {
    const file = event.target.files[0];
    if (!file) return;

    setUploadingDoc(documentType);
    setErrorMessage("");
    setSuccessMessage("");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);

    try {
      const response = await authenticatedRequest("/users/me/verification-documents", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const msg = await readErrorMessage(response);
        throw new Error(msg);
      }

      setSuccessMessage("Document uploaded successfully.");
      await fetchProfile();
    } catch (err) {
      setErrorMessage(err.message || "Failed to upload document.");
    } finally {
      setUploadingDoc("");
    }
  };

  const handleLogout = () => {
    clearSession();
  };

  const isVerified = userProfile?.verificationStatus === "verified";
  
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
          <Link to="/ngo-dashboard">
            <span>▦</span> Overview
          </Link>
          <Link to="/ngo-verification" className="active-dashboard-link">
            <span>🛡️</span> Verification
          </Link>
        </nav>

        <Link to="/login" className="logout-link" onClick={handleLogout}>
          ← Logout
        </Link>
      </aside>

      <main className="dashboard-main verification-main">
        <header className="dashboard-header">
          <div>
            <p className="dashboard-label">TRUST & SECURITY</p>
            <h1>Organization Verification</h1>
          </div>
          <div className="ngo-header-actions">
            <Link to="/ngo-dashboard" className="view-home-button">
              Back to Dashboard
            </Link>
          </div>
        </header>

        {successMessage && <div className="verification-success-message">{successMessage}</div>}
        {errorMessage && <div className="verification-error-message">{errorMessage}</div>}

        {isLoading ? (
          <p className="loading-text">Loading verification status...</p>
        ) : (
          <div className="verification-content">
            <section className="status-section">
              <h2>Verification Status</h2>
              <div className={`status-badge ${userProfile.verificationStatus}`}>
                {userProfile.verificationStatus === "pending" && "🟡 Pending Review"}
                {userProfile.verificationStatus === "verified" && "✅ Verified"}
                {userProfile.verificationStatus === "rejected" && "🔴 Verification Rejected"}
              </div>
              
              {userProfile.verificationStatus === "pending" && (
                <p className="status-description">Your documents are currently being reviewed by the administrator. You will be notified once approved.</p>
              )}
              {userProfile.verificationStatus === "rejected" && (
                <div className="rejection-reason">
                  <strong>Reason for rejection:</strong>
                  <p>{userProfile.rejectionReason || "Please review and re-upload clear, valid documents."}</p>
                </div>
              )}
            </section>

            <section className="documents-section">
              <h2>Required Documents</h2>
              <p className="section-subtitle">Upload the following documents to verify your organization.</p>
              
              <div className="document-card">
                <div className="doc-info">
                  <h3>Registration Certificate</h3>
                  <p>Official NGO/Organization registration certificate.</p>
                  {userProfile.registrationCertificate ? (
                    <span className="doc-status uploaded">✓ Uploaded</span>
                  ) : (
                    <span className="doc-status missing">✗ Missing</span>
                  )}
                </div>
                {!isVerified && (
                  <div className="doc-action">
                    <label className={`upload-button ${uploadingDoc === "registrationCertificate" ? "disabled" : ""}`}>
                      {uploadingDoc === "registrationCertificate" ? "Uploading..." : (userProfile.registrationCertificate ? "Replace" : "Upload")}
                      <input 
                        type="file" 
                        accept=".pdf,.jpg,.jpeg,.png,.webp" 
                        onChange={(e) => handleFileUpload(e, "registrationCertificate")} 
                        disabled={uploadingDoc === "registrationCertificate"}
                      />
                    </label>
                  </div>
                )}
              </div>

              <div className="document-card">
                <div className="doc-info">
                  <h3>Government ID</h3>
                  <p>Valid Government ID of the primary contact person.</p>
                  {userProfile.governmentId ? (
                    <span className="doc-status uploaded">✓ Uploaded</span>
                  ) : (
                    <span className="doc-status missing">✗ Missing</span>
                  )}
                </div>
                {!isVerified && (
                  <div className="doc-action">
                    <label className={`upload-button ${uploadingDoc === "governmentId" ? "disabled" : ""}`}>
                      {uploadingDoc === "governmentId" ? "Uploading..." : (userProfile.governmentId ? "Replace" : "Upload")}
                      <input 
                        type="file" 
                        accept=".pdf,.jpg,.jpeg,.png,.webp" 
                        onChange={(e) => handleFileUpload(e, "governmentId")}
                        disabled={uploadingDoc === "governmentId"}
                      />
                    </label>
                  </div>
                )}
              </div>

              <div className="document-card">
                <div className="doc-info">
                  <h3>Organization Logo</h3>
                  <p>High quality logo for your organization profile (Image only).</p>
                  {userProfile.organizationLogo ? (
                    <span className="doc-status uploaded">✓ Uploaded</span>
                  ) : (
                    <span className="doc-status missing">✗ Missing</span>
                  )}
                </div>
                {!isVerified && (
                  <div className="doc-action">
                    <label className={`upload-button ${uploadingDoc === "organizationLogo" ? "disabled" : ""}`}>
                      {uploadingDoc === "organizationLogo" ? "Uploading..." : (userProfile.organizationLogo ? "Replace" : "Upload")}
                      <input 
                        type="file" 
                        accept=".jpg,.jpeg,.png,.webp" 
                        onChange={(e) => handleFileUpload(e, "organizationLogo")}
                        disabled={uploadingDoc === "organizationLogo"}
                      />
                    </label>
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

export default ReceiverVerification;
