"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  Camera, Upload, ShieldCheck, Lock, Unlock, ArrowLeft, 
  RefreshCw, AlertCircle, Sparkles, Search, Check, 
  Image as ImageIcon, KeyRound, ArrowRight, ShieldAlert
} from "lucide-react";
import { getEventByCode, matchAttendeeSelfie, verifyEventPassword, EventData, MatchResponseData } from "@/lib/api";
import { AiScanningOverlay } from "@/components/AiScanningOverlay";

export default function ClientEventSelfiePage() {
  const params = useParams();
  const router = useRouter();
  const rawParam = (params?.code as string) || "";
  const eventCode = decodeURIComponent(rawParam).trim().toUpperCase();

  const [eventData, setEventData] = useState<EventData | null>(null);
  const [loadingEvent, setLoadingEvent] = useState(true);
  const [mounted, setMounted] = useState(false);

  // Password Unlock State
  const [isUnlocked, setIsUnlocked] = useState<boolean>(false);
  const [enteredPassword, setEnteredPassword] = useState("");
  const [verifyingPassword, setVerifyingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  // Selfie / Matching State
  const [privacyAgreed, setPrivacyAgreed] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Camera & File state
  const [useCamera, setUseCamera] = useState(true);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  // Load Event Info & check unlock state
  useEffect(() => {
    setMounted(true);
    async function fetchEvent() {
      try {
        const lookup = eventCode || rawParam;
        const data = await getEventByCode(lookup);
        setEventData(data);

        // Check if unlocked
        if (!data.is_protected) {
          setIsUnlocked(true);
        } else {
          const unlockedSession = 
            sessionStorage.getItem(`eventlens_unlocked_${eventCode}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${rawParam}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${data.id}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${data.event_code}`) === "true";
          setIsUnlocked(unlockedSession);
        }
      } catch (err: any) {
        console.warn("Event fetch notice:", err);
        setErrorMessage("Could not load event data from server. Please check connection.");
      } finally {
        setLoadingEvent(false);
      }
    }
    fetchEvent();
  }, [eventCode, rawParam]);

  // Handle Passcode Unlock
  const handleUnlockEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enteredPassword.trim()) return;

    setVerifyingPassword(true);
    setPasswordError("");

    try {
      const lookup = eventCode || rawParam;
      await verifyEventPassword(lookup, enteredPassword.trim());
      sessionStorage.setItem(`eventlens_unlocked_${eventCode}`, "true");
      sessionStorage.setItem(`eventlens_unlocked_${rawParam}`, "true");
      if (eventData) {
        sessionStorage.setItem(`eventlens_unlocked_${eventData.id}`, "true");
        sessionStorage.setItem(`eventlens_unlocked_${eventData.event_code}`, "true");
      }
      setIsUnlocked(true);
    } catch (err: any) {
      setPasswordError(err.message || "Incorrect passcode. Please check and try again.");
    } finally {
      setVerifyingPassword(false);
    }
  };

  // Start Camera Feed
  const startWebcam = async () => {
    try {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 720 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      setUseCamera(true);
      setErrorMessage("");
    } catch (err) {
      console.warn("Webcam access error:", err);
      setUseCamera(false);
    }
  };

  useEffect(() => {
    if (isUnlocked && useCamera && !capturedBlob) {
      startWebcam();
    }
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [isUnlocked, useCamera, capturedBlob]);

  // High-Fidelity Client-Side Optimization for AI Face Recognition (< 150KB payload)
  const compressImageForAI = async (blobOrFile: Blob | File, maxDim = 1080, quality = 0.90): Promise<Blob> => {
    return new Promise((resolve) => {
      const img = new Image();
      const url = URL.createObjectURL(blobOrFile);
      img.onload = () => {
        URL.revokeObjectURL(url);
        let { width, height } = img;
        if (width > maxDim || height > maxDim) {
          if (width > height) {
            height = Math.round((height * maxDim) / width);
            width = maxDim;
          } else {
            width = Math.round((width * maxDim) / height);
            height = maxDim;
          }
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.imageSmoothingEnabled = true;
          ctx.imageSmoothingQuality = "high";
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob(
            (blob) => resolve(blob || blobOrFile),
            "image/jpeg",
            quality
          );
        } else {
          resolve(blobOrFile);
        }
      };
      img.onerror = () => resolve(blobOrFile);
      img.src = url;
    });
  };

  // Capture Shutter Action
  const handleCaptureShutter = async () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const maxDim = 1080;
    let vw = video.videoWidth || 720;
    let vh = video.videoHeight || 720;
    if (vw > maxDim || vh > maxDim) {
      if (vw > vh) {
        vh = Math.round((vh * maxDim) / vw);
        vw = maxDim;
      } else {
        vw = Math.round((vw * maxDim) / vh);
        vh = maxDim;
      }
    }
    canvas.width = vw;
    canvas.height = vh;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (blob) {
          setCapturedBlob(blob);
          setPreviewUrl(URL.createObjectURL(blob));
          if (stream) {
            stream.getTracks().forEach((track) => track.stop());
            setStream(null);
          }
        }
      },
      "image/jpeg",
      0.90
    );
  };

  // Retake Photo
  const handleRetake = () => {
    setCapturedBlob(null);
    setPreviewUrl(null);
    setErrorMessage("");
    setUseCamera(true);
    startWebcam();
  };

  // File Upload Fallback with Automatic Mobile Compression
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const compressed = await compressImageForAI(file, 800, 0.85);
      setCapturedBlob(compressed);
      setPreviewUrl(URL.createObjectURL(compressed));
    } catch {
      setCapturedBlob(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
    setUseCamera(false);
    setErrorMessage("");
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
  };

  // Submit Search Request
  const handleSearchPhotos = async () => {
    if (!capturedBlob || !privacyAgreed) return;

    setErrorMessage("");
    setIsScanning(true);

    try {
      // Ensure payload is compressed to <100KB for instantaneous Wi-Fi transfer
      const optimizedBlob = await compressImageForAI(capturedBlob, 800, 0.85);
      const selfieFile = new File([optimizedBlob], "selfie.jpg", { type: "image/jpeg" });
      const targetEventId = eventData?.id && !eventData.id.startsWith("mock-") ? eventData.id : eventCode;

      const result: MatchResponseData = await matchAttendeeSelfie(targetEventId, selfieFile);

      // Save match results to sessionStorage under multiple keys for resilient retrieval
      sessionStorage.setItem(`eventlens_matches_${eventCode}`, JSON.stringify(result));
      sessionStorage.setItem(`eventlens_matches_${rawParam}`, JSON.stringify(result));
      sessionStorage.setItem(`eventlens_matches_${encodeURIComponent(eventCode)}`, JSON.stringify(result));

      router.push(`/event/${encodeURIComponent(eventCode)}/gallery?tab=selfie`);
    } catch (err: any) {
      console.error("Match error:", err);
      setErrorMessage(err.message || "No face detected in selfie. Please ensure good lighting and try again.");
    } finally {
      setIsScanning(false);
    }
  };

  if (!mounted) {
    return null;
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] p-4 md:p-8 flex flex-col items-center justify-center relative" suppressHydrationWarning>
      <AiScanningOverlay isScanning={isScanning} selfiePreviewUrl={previewUrl} />

      <canvas ref={canvasRef} className="hidden" />

      <div className="w-full max-w-xl mx-auto flex flex-col items-center" suppressHydrationWarning>
        {/* Header Navigation */}
        <div className="w-full flex justify-between items-center mb-6" suppressHydrationWarning>
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2 text-xs font-semibold text-[#c7c4d7] hover:text-white bg-white/5 hover:bg-white/10 px-3.5 py-2 rounded-xl border border-white/10 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Home
          </button>
          <div className="flex items-center gap-2 bg-[#131b2e] px-3 py-1.5 rounded-full border border-white/10 text-xs font-bold text-[#7bd0ff]" suppressHydrationWarning>
            {eventData?.is_protected ? (
              <Lock className="w-3.5 h-3.5 text-[#ffb4ab]" />
            ) : (
              <Unlock className="w-3.5 h-3.5 text-[#7bd0ff]" />
            )}
            <span>Event: {eventCode}</span>
          </div>
        </div>

        {/* Title */}
        <div className="text-center mb-6" suppressHydrationWarning>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white mb-2 tracking-tight">
            {loadingEvent ? "Loading Event..." : eventData?.title || `Event Gallery (${eventCode})`}
          </h1>
          <p className="text-sm text-[#c7c4d7]">
            {eventData?.is_protected && !isUnlocked
              ? "This gallery is protected. Enter the event passcode to unlock downloads & photos."
              : "Capture or upload a selfie to instantly match your photos with AI, or browse full gallery."}
          </p>
        </div>

        {/* --- STATE 1: PASSWORD UNLOCK SCREEN --- */}
        {!isUnlocked && eventData?.is_protected ? (
          <div className="w-full glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 flex flex-col items-center shadow-2xl relative" suppressHydrationWarning>
            <div className="w-16 h-16 rounded-2xl bg-[#8083ff]/15 text-[#c0c1ff] flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(192,193,255,0.2)]">
              <Lock className="w-8 h-8 text-[#ffb4ab]" />
            </div>

            <h3 className="text-xl font-bold text-white mb-1">Passcode Required</h3>
            <p className="text-xs text-[#908fa0] text-center max-w-sm mb-6">
              The organizer has protected this event. Please enter the access password provided by your host.
            </p>

            <form onSubmit={handleUnlockEvent} className="w-full flex flex-col gap-4">
              <div className="relative flex items-center">
                <KeyRound className="absolute left-4 w-5 h-5 text-[#908fa0]" />
                <input
                  type="password"
                  value={enteredPassword}
                  onChange={(e) => setEnteredPassword(e.target.value)}
                  placeholder="Enter Event Passcode"
                  required
                  autoFocus
                  className="w-full bg-[#131b2e] border border-white/15 rounded-2xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-[#c0c1ff] focus:ring-2 focus:ring-[#8083ff]/40 text-sm font-medium placeholder:text-[#908fa0]/60 transition-all"
                />
              </div>

              {passwordError && (
                <div className="p-3 bg-[#93000a]/40 border border-[#ffb4ab]/40 rounded-xl text-xs text-[#ffdad6] flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-[#ffb4ab] shrink-0" />
                  <span>{passwordError}</span>
                </div>
              )}

              <button
                type="submit"
                disabled={verifyingPassword || !enteredPassword.trim()}
                className="w-full bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-sm sm:text-base py-3.5 rounded-2xl hover:opacity-95 transition-all shadow-[0_0_25px_rgba(192,193,255,0.4)] active:scale-98 flex items-center justify-center gap-2 cursor-pointer"
              >
                {verifyingPassword ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Verifying Passcode...
                  </>
                ) : (
                  <>
                    <Unlock className="w-4 h-4" /> Unlock Event Gallery
                  </>
                )}
              </button>
            </form>
          </div>
        ) : (
          /* --- STATE 2: EVENT ACTION HUB & SELFIE MATCH --- */
          <div className="w-full flex flex-col gap-6">
            {/* Quick Action: Browse Full Gallery or Find My Photos */}
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => router.push(`/event/${eventCode}/gallery?tab=selfie`)}
                className="p-4 rounded-2xl bg-[#131b2e]/80 border border-[#c0c1ff]/40 hover:border-[#c0c1ff] text-left transition-all group"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-[#c0c1ff] mb-1">
                  <Sparkles className="w-4 h-4 text-[#7bd0ff]" /> Option 1
                </div>
                <h4 className="text-sm font-bold text-white group-hover:text-[#c0c1ff] transition-colors">
                  Find My Photos
                </h4>
                <p className="text-[11px] text-[#908fa0] mt-0.5">Snap a selfie for AI face matching</p>
              </button>

              <button
                onClick={() => router.push(`/event/${eventCode}/gallery?tab=all`)}
                className="p-4 rounded-2xl bg-[#131b2e]/50 border border-white/10 hover:border-white/30 text-left transition-all group"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-[#dae2fd] mb-1">
                  <ImageIcon className="w-4 h-4 text-[#dae2fd]" /> Option 2
                </div>
                <h4 className="text-sm font-bold text-white group-hover:text-[#dae2fd] transition-colors">
                  Browse All Photos
                </h4>
                <p className="text-[11px] text-[#908fa0] mt-0.5">View & download full gallery</p>
              </button>
            </div>

            {/* Camera Viewport Section */}
            <div className="w-full glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 flex flex-col items-center shadow-2xl relative">
              <div className="relative mb-6">
                {/* Viewport Frame */}
                <div className="camera-viewport bg-[#131b2e] relative flex items-center justify-center overflow-hidden border-2 border-[#c0c1ff]">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Captured Selfie" className="w-full h-full object-cover" />
                  ) : useCamera ? (
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      className="w-full h-full object-cover transform -scale-x-100"
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center p-6 text-center text-[#908fa0]">
                      <Upload className="w-12 h-12 text-[#c0c1ff] mb-2" />
                      <span className="text-xs">No camera active. Select a photo file below.</span>
                    </div>
                  )}

                  <div className="camera-overlay" />
                  <div className="focus-ring" />
                </div>

                {/* Target Reticle Status Badges */}
                <div className="absolute -bottom-3.5 left-1/2 -translate-x-1/2 flex gap-2 w-max z-20">
                  {previewUrl ? (
                    <div className="px-3.5 py-1 rounded-full flex items-center gap-1.5 bg-emerald-500/20 border border-emerald-500/40 text-xs font-semibold text-emerald-200 shadow-lg">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Face Validated & Ready</span>
                    </div>
                  ) : (
                    <div className="glass-panel px-3 py-1 rounded-full flex items-center gap-1.5 border border-white/10 text-xs font-semibold text-white shadow-lg">
                      <Sparkles className="w-3.5 h-3.5 text-[#7bd0ff]" />
                      <span>Align Face Within Frame</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Shutter / Retake Controls */}
              <div className="flex flex-col items-center gap-3 w-full mb-6">
                {!previewUrl ? (
                  <div className="flex items-center gap-4">
                    {useCamera && (
                      <button
                        onClick={handleCaptureShutter}
                        className="w-20 h-20 rounded-full border-4 border-white/20 flex items-center justify-center hover:border-[#c0c1ff] transition-colors active:scale-95 group relative shadow-[0_0_30px_rgba(192,193,255,0.3)]"
                        title="Take Photo"
                      >
                        <div className="w-16 h-16 rounded-full bg-white group-hover:bg-[#c0c1ff] transition-colors flex items-center justify-center">
                          <Camera className="w-8 h-8 text-[#0b1326]" />
                        </div>
                      </button>
                    )}
                    <label className="cursor-pointer text-xs text-[#c0c1ff] hover:text-white font-semibold flex items-center gap-1.5 underline-offset-4 hover:underline bg-white/5 hover:bg-white/10 px-4 py-2.5 rounded-xl border border-white/10 transition-colors">
                      <Upload className="w-4 h-4" /> Upload Selfie File
                      <input type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />
                    </label>
                  </div>
                ) : (
                  <button
                    onClick={handleRetake}
                    className="text-xs text-[#7bd0ff] hover:text-white font-semibold flex items-center gap-1.5 bg-white/5 hover:bg-white/10 px-4 py-2 rounded-xl border border-white/10 transition-colors"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Retake / Choose Different Photo
                  </button>
                )}
              </div>

              {/* Error Banner */}
              {errorMessage && (
                <div className="w-full bg-[#93000a]/40 border border-[#ffb4ab]/40 rounded-xl p-3.5 mb-6 text-xs text-[#ffdad6] flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-[#ffb4ab] shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {/* Privacy Checkbox & Submit */}
              <div className="w-full pt-4 border-t border-white/10 flex flex-col gap-5">
                <label className="flex items-start gap-3 cursor-pointer group">
                  <div className="relative flex items-center pt-0.5">
                    <input
                      type="checkbox"
                      checked={privacyAgreed}
                      onChange={(e) => setPrivacyAgreed(e.target.checked)}
                      className="peer sr-only"
                    />
                    <div className="w-5 h-5 rounded-md border-2 border-white/30 peer-checked:bg-[#8083ff] peer-checked:border-[#c0c1ff] transition-all flex items-center justify-center bg-[#131b2e]">
                      {privacyAgreed && <Check className="w-3.5 h-3.5 text-[#1000a9] font-bold" />}
                    </div>
                  </div>
                  <span className="text-xs text-[#c7c4d7] group-hover:text-white transition-colors leading-relaxed">
                    I agree to process my selfie strictly for instant face matching. Zero raw selfies stored.
                  </span>
                </label>

                <button
                  onClick={handleSearchPhotos}
                  disabled={!capturedBlob || !privacyAgreed || isScanning}
                  className={`w-full py-4 rounded-2xl font-extrabold text-sm sm:text-base flex items-center justify-center gap-2 transition-all shadow-lg ${
                    capturedBlob && privacyAgreed && !isScanning
                      ? "bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] hover:opacity-95 shadow-[0_0_25px_rgba(192,193,255,0.4)] active:scale-98 cursor-pointer"
                      : "bg-[#171f33] text-[#908fa0] cursor-not-allowed border border-white/10"
                  }`}
                >
                  <Search className="w-5 h-5" />
                  Find My Photos & Downloads
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="mt-6 flex items-center gap-2 text-xs text-[#7bd0ff] opacity-80">
          <ShieldCheck className="w-4 h-4" /> Zero-Storage Privacy Guarantee Active
        </div>
      </div>
    </div>
  );
}
