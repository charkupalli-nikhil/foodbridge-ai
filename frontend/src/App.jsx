import { useEffect } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import DonorDashboard from "./pages/DonorDashboard";
import NgoDashboard from "./pages/NgoDashboard";
import AdminDashboard from "./pages/AdminDashboard";

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

function getStoredSession() {
  const token = localStorage.getItem("foodbridge_access_token");
  const storedUser = localStorage.getItem("foodbridge_user");

  if (!token || !storedUser) {
    return null;
  }

  try {
    return {
      token,
      user: JSON.parse(storedUser),
    };
  } catch {
    localStorage.removeItem("foodbridge_access_token");
    localStorage.removeItem("foodbridge_user");
    return null;
  }
}

function ProtectedRoute({ allowedRole, children }) {
  const session = getStoredSession();

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (session.user.role !== allowedRole) {
    if (session.user.role === "donor") {
      return <Navigate to="/donor-dashboard" replace />;
    }

    if (session.user.role === "ngo") {
      return <Navigate to="/ngo-dashboard" replace />;
    }

    if (session.user.role === "admin") {
      return <Navigate to="/admin-dashboard" replace />;
    }

    return <Navigate to="/" replace />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route
          path="/donor-dashboard"
          element={
            <ProtectedRoute allowedRole="donor">
              <DonorDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/ngo-dashboard"
          element={
            <ProtectedRoute allowedRole="ngo">
              <NgoDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin-dashboard"
          element={
            <ProtectedRoute allowedRole="admin">
              <AdminDashboard />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;