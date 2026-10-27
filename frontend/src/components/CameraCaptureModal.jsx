import React, { useState, useRef, useEffect, useCallback } from "react";
import "./CameraCaptureModal.css";

export default function CameraCaptureModal({
  isOpen,
  onClose,
  onCapture,
  title = "Live Camera Capture",
  guidelineText = "Center the prepared food clearly under good lighting",
}) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  const [stream, setStream] = useState(null);
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [cameraError, setCameraError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [coords, setCoords] = useState({ lat: null, lng: null });

  // Stop camera tracks cleanly
  const stopStream = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
  }, [stream]);

  // Request camera and GPS
  const startCamera = useCallback(async () => {
    setCameraError("");
    setIsLoading(true);
    setCapturedBlob(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }

    // Try reading device GPS coordinates concurrently
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
        },
        (err) => {
          console.warn("[GPS] Location capture note:", err.message);
        },
        { timeout: 8000, enableHighAccuracy: true }
      );
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error(
          "Camera access is not supported by your browser or requires a secure (HTTPS or localhost) connection."
        );
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });

      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err) {
      console.error("[Camera] Error:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        setCameraError(
          "Camera access was denied. Please allow camera permissions in your browser address bar to verify original food donations."
        );
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        setCameraError("No camera device was detected on your computer or phone.");
      } else {
        setCameraError(err.message || "Could not start camera stream.");
      }
    } finally {
      setIsLoading(false);
    }
  }, [previewUrl]);

  // Handle open/close
  useEffect(() => {
    if (isOpen) {
      startCamera();
    } else {
      stopStream();
    }
    return () => {
      stopStream();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [isOpen]);

  // Snap photo from live video onto canvas
  const handleSnap = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          setCapturedBlob(blob);
          const url = URL.createObjectURL(blob);
          setPreviewUrl(url);
          stopStream();
        }
      },
      "image/jpeg",
      0.9
    );
  };

  // Retake photo
  const handleRetake = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
    setCapturedBlob(null);
    startCamera();
  };

  // Confirm and deliver captured photo
  const handleConfirm = () => {
    if (!capturedBlob) return;
    onCapture(capturedBlob, {
      captureLat: coords.lat,
      captureLng: coords.lng,
    });
    stopStream();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="camera-modal-backdrop" onClick={onClose}>
      <div
        className="camera-modal-dialog"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="camera-modal-title"
      >
        <div className="camera-modal-header">
          <div className="camera-modal-title-group">
            <span className="camera-live-pulse" />
            <h3 id="camera-modal-title">{title}</h3>
          </div>
          <button
            type="button"
            className="camera-close-btn"
            onClick={onClose}
            aria-label="Close camera"
          >
            ✕
          </button>
        </div>

        <div className="camera-modal-body">
          {cameraError ? (
            <div className="camera-error-banner">
              <span className="camera-error-icon">⚠️</span>
              <p>{cameraError}</p>
              <button
                type="button"
                className="btn-retry-camera"
                onClick={startCamera}
              >
                Try Again
              </button>
            </div>
          ) : previewUrl ? (
            <div className="camera-preview-container">
              <img
                src={previewUrl}
                alt="Captured snapshot"
                className="camera-preview-img"
              />
              <div className="camera-preview-badge">Snapshot Ready</div>
            </div>
          ) : (
            <div className="camera-viewfinder-container">
              {isLoading && (
                <div className="camera-loading-overlay">
                  <div className="camera-spinner" />
                  <span>Starting camera...</span>
                </div>
              )}
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="camera-video-feed"
              />
              <div className="camera-crosshairs">
                <div className="crosshair-corner top-left" />
                <div className="crosshair-corner top-right" />
                <div className="crosshair-corner bottom-left" />
                <div className="crosshair-corner bottom-right" />
              </div>
              <div className="camera-guideline-text">
                {guidelineText}
              </div>
            </div>
          )}

          {/* Hidden offscreen canvas for snapshot rendering */}
          <canvas ref={canvasRef} style={{ display: "none" }} />
        </div>

        <div className="camera-modal-footer">
          {capturedBlob ? (
            <>
              <button
                type="button"
                className="btn-camera-retake"
                onClick={handleRetake}
              >
                🔄 Retake Photo
              </button>
              <button
                type="button"
                className="btn-camera-confirm"
                onClick={handleConfirm}
              >
                ✓ Use This Photo
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="btn-camera-cancel"
                onClick={onClose}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-camera-snap"
                onClick={handleSnap}
                disabled={isLoading || Boolean(cameraError) || !stream}
              >
                <span className="snap-inner-circle" />
                Capture Photo
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
