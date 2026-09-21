import React, { useState, useEffect, useRef, useCallback } from "react";
import "./NotificationBell.css";
import { API_BASE_URL } from "../config";

function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const fetchNotifications = useCallback(async () => {
    const token =
      localStorage.getItem("accessToken") ||
      localStorage.getItem("token") ||
      localStorage.getItem("foodbridge_access_token");

    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
      }
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const intervalId = setInterval(fetchNotifications, 15000); // Poll every 15 seconds
    return () => clearInterval(intervalId);
  }, [fetchNotifications]);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    } else {
      document.removeEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleMarkAsRead = async (notificationId) => {
    const token =
      localStorage.getItem("accessToken") ||
      localStorage.getItem("token") ||
      localStorage.getItem("foodbridge_access_token");

    if (!token) return;

    try {
      await fetch(`${API_BASE_URL}/notifications/${notificationId}/read`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      setNotifications((prev) => prev.filter((n) => n.id !== notificationId));
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }
  };

  const unreadCount = notifications.filter((n) => !n.isRead).length;

  return (
    <div className="notification-container" ref={dropdownRef}>
      <button
        className="notification-bell-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <h3>Notifications</h3>
          </div>
          <div className="notification-list">
            {notifications.length === 0 ? (
              <div className="notification-empty">
                No new notifications
              </div>
            ) : (
              notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`notification-item ${!notification.isRead ? "unread" : ""}`}
                  onClick={() => handleMarkAsRead(notification.id)}
                >
                  <h4 className="notification-title">{notification.title}</h4>
                  <p className="notification-message">{notification.message}</p>
                  <span className="notification-time">
                    {new Date(notification.createdAt).toLocaleString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
