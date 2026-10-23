import React, { useState, useEffect, useRef, useCallback } from "react";
import "./NotificationBell.css";
import { API_BASE_URL } from "../config";

function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef(null);

  const getAuthToken = () =>
    localStorage.getItem("accessToken") ||
    localStorage.getItem("token") ||
    localStorage.getItem("foodbridge_access_token");

  // Fetch only unread count for fast background polling
  const fetchUnreadCount = useCallback(async () => {
    const token = getAuthToken();
    if (!token) return;

    try {
      const response = await fetch(`${API_BASE_URL}/notifications/unread-count`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unreadCount || 0);
      }
    } catch (error) {
      console.warn("Failed to fetch unread notification count:", error);
    }
  }, []);

  // Fetch full notification list when dropdown opens
  const fetchNotifications = useCallback(async () => {
    const token = getAuthToken();
    if (!token) return;

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/notifications?limit=30`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
        const unread = data.filter((n) => !n.read && !n.isRead).length;
        setUnreadCount(unread);
      }
    } catch (error) {
      console.error("Failed to fetch notifications:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll count every 20 seconds
  useEffect(() => {
    fetchUnreadCount();
    const intervalId = setInterval(fetchUnreadCount, 20000);
    return () => clearInterval(intervalId);
  }, [fetchUnreadCount]);

  // When opening dropdown, fetch full list
  useEffect(() => {
    if (isOpen) {
      fetchNotifications();
    }
  }, [isOpen, fetchNotifications]);

  // Close dropdown on click outside
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

  const handleMarkAsRead = async (notification) => {
    const token = getAuthToken();
    if (!token) return;

    const notifId = notification.id || notification._id;

    // Optimistically mark as read
    setNotifications((prev) =>
      prev.map((n) =>
        (n.id === notifId || n._id === notifId) ? { ...n, read: true, isRead: true } : n
      )
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));

    try {
      await fetch(`${API_BASE_URL}/notifications/${notifId}/read`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (error) {
      console.error("Failed to mark notification as read:", error);
    }

    // Scroll to donation card if present
    const targetDonationId = notification.donationId;
    if (targetDonationId) {
      setIsOpen(false);
      setTimeout(() => {
        const card = document.getElementById(`donation-${targetDonationId}`);
        if (card) {
          card.scrollIntoView({ behavior: "smooth", block: "center" });
          card.classList.add("highlight-pulse");
          setTimeout(() => card.classList.remove("highlight-pulse"), 2500);
        }
      }, 100);
    }
  };

  const handleMarkAllRead = async () => {
    const token = getAuthToken();
    if (!token) return;

    setNotifications((prev) =>
      prev.map((n) => ({ ...n, read: true, isRead: true }))
    );
    setUnreadCount(0);

    try {
      await fetch(`${API_BASE_URL}/notifications/read-all`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (error) {
      console.error("Failed to mark all notifications read:", error);
    }
  };

  return (
    <div className="notification-container" ref={dropdownRef}>
      <button
        className="notification-bell-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="Notifications"
        aria-label="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="notification-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>

      {isOpen && (
        <div className="notification-dropdown">
          <div className="notification-header">
            <h3>Notifications</h3>
            {unreadCount > 0 && (
              <button
                className="mark-all-read-btn"
                onClick={handleMarkAllRead}
                type="button"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="notification-list">
            {isLoading ? (
              <div className="notification-loading">Loading...</div>
            ) : notifications.length === 0 ? (
              <div className="notification-empty">No notifications yet</div>
            ) : (
              notifications.map((notification) => {
                const notifId = notification.id || notification._id;
                const isUnread = !notification.read && !notification.isRead;
                return (
                  <div
                    key={notifId}
                    className={`notification-item ${isUnread ? "unread" : ""}`}
                    onClick={() => handleMarkAsRead(notification)}
                  >
                    <div className="notification-item-top">
                      <h4 className="notification-title">{notification.title}</h4>
                      {isUnread && <span className="unread-dot" />}
                    </div>
                    <p className="notification-message">{notification.message}</p>
                    <span className="notification-time">
                      {new Date(notification.createdAt).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationBell;
