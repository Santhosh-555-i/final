"use client";

import React, { useState, useEffect } from "react";
import { 
  Plus, UploadCloud, Image as ImageIcon, CheckCircle, 
  AlertCircle, Sparkles, RefreshCw, Cpu, Layers, Copy, 
  Check, Lock, Unlock, Link as LinkIcon, FolderSync, 
  ExternalLink, ShieldCheck, Download, UserCircle, LogOut,
  Mail, KeyRound, Shield, HelpCircle, Info, Trash2, Eye,
  Maximize2, X, Users, Sliders, Activity, Edit2, GitMerge,
  ShieldAlert, Clock, CheckSquare, Square
} from "lucide-react";
import { 
  createEvent, uploadBatchPhotos, listEvents, deleteEvent,
  importGoogleDrive, adminLogin, getAdminProfile, 
  getEventPhotos, deletePhoto, deletePhotosBatch, getFullImageUrl,
  getEventClusters, recomputeClusters, renamePersonCluster,
  mergePersonClusters, deletePersonBiometrics,
  getEventAuditLogs, deleteEventBiometrics,
  getEventSettings, updateEventSettings,
  syncDriveAdmin, getSyncStatus, getAdminStats, indexFacesAdmin,
  EventData, PhotoData, PersonCluster, AuditLogEntry, EventSettingsData,
  SyncTaskStatus, AdminStatsData
} from "@/lib/api";

const DESIGNATED_ADMIN_EMAIL = "santosh2005th@gmail.com";

export default function AdminDashboardPage() {
  // Mounted State
  const [mounted, setMounted] = useState(false);

  // Admin Auth State
  const [isAdminLoggedIn, setIsAdminLoggedIn] = useState<boolean>(false);
  const [adminEmailInput, setAdminEmailInput] = useState(DESIGNATED_ADMIN_EMAIL);
  const [adminPasswordInput, setAdminPasswordInput] = useState("element2018");
  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [adminEmailDisplay, setAdminEmailDisplay] = useState(DESIGNATED_ADMIN_EMAIL);

  // Events State
  const [events, setEvents] = useState<EventData[]>([]);

  useEffect(() => {
    setMounted(true);
  }, []);
  const [selectedEvent, setSelectedEvent] = useState<EventData | null>(null);
  const [deletingEventId, setDeletingEventId] = useState<string | null>(null);
  const [adminStats, setAdminStats] = useState<AdminStatsData | null>(null);

  // Event Photos State (for "View Uploaded Photos" tab)
  const [eventPhotos, setEventPhotos] = useState<PhotoData[]>([]);
  const [loadingPhotos, setLoadingPhotos] = useState(false);
  const [previewPhoto, setPreviewPhoto] = useState<PhotoData | null>(null);
  const [deletingPhotoId, setDeletingPhotoId] = useState<string | null>(null);
  const [selectedAdminPhotoIds, setSelectedAdminPhotoIds] = useState<Set<string>>(new Set());
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);
  const [photoDeleteSuccessMsg, setPhotoDeleteSuccessMsg] = useState("");

  // Person Discovery & Clusters State
  const [clusters, setClusters] = useState<PersonCluster[]>([]);
  const [loadingClusters, setLoadingClusters] = useState(false);
  const [recomputingClusters, setRecomputingClusters] = useState(false);
  const [editingClusterId, setEditingClusterId] = useState<string | null>(null);
  const [editClusterName, setEditClusterName] = useState("");
  const [mergeTargetId, setMergeTargetId] = useState<string>("");
  const [mergingSourceCluster, setMergingSourceCluster] = useState<PersonCluster | null>(null);

  // Settings & Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [settingsData, setSettingsData] = useState<EventSettingsData>({
    event_id: "",
    similarity_threshold: 0.35,
    retention_days: 90,
    selfie_search_enabled: 1,
    downloads_enabled: 1,
  });
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsSuccessMsg, setSettingsSuccessMsg] = useState("");

  // New Event Form State
  const [newTitle, setNewTitle] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newDriveLink, setNewDriveLink] = useState("");
  const [creatingEvent, setCreatingEvent] = useState(false);
  const [createError, setCreateError] = useState("");

  // Upload Management Mode: "photos" | "clusters" | "drive" | "device" | "settings"
  const [uploadMode, setUploadMode] = useState<"photos" | "clusters" | "drive" | "device" | "settings">("photos");

  // Google Drive Import State
  const [driveUrlInput, setDriveUrlInput] = useState("");
  const [isDriveImporting, setIsDriveImporting] = useState(false);
  const [driveImportMsg, setDriveImportMsg] = useState("");
  const [driveImportError, setDriveImportError] = useState("");
  const [syncTask, setSyncTask] = useState<SyncTaskStatus | null>(null);
  const [isIndexingFaces, setIsIndexingFaces] = useState(false);
  const [indexFacesMsg, setIndexFacesMsg] = useState("");

  // Upload Batch State
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [processedCount, setProcessedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState("");
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState<string | null>(null);

  // Check persisted admin session on load & clear legacy mock caches
  useEffect(() => {
    try {
      localStorage.removeItem("eventlens_events_db");
      localStorage.removeItem("eventlens_photos_db");
    } catch {}
    const storedEmail = sessionStorage.getItem("eventlens_admin_email");
    if (storedEmail && storedEmail.toLowerCase() === DESIGNATED_ADMIN_EMAIL.toLowerCase()) {
      setIsAdminLoggedIn(true);
      setAdminEmailDisplay(storedEmail);
    }
  }, []);

  const fetchEventsList = async () => {
    try {
      const data = await listEvents();
      setEvents(data);
      if (data.length > 0) {
        if (!selectedEvent) {
          setSelectedEvent(data[0]);
          setDriveUrlInput(data[0].drive_link || "");
        } else {
          const updated = data.find((ev) => ev.id === selectedEvent.id);
          if (updated) {
            setSelectedEvent(updated);
          }
        }
      }
    } catch (err) {
      console.warn("Could not fetch events list:", err);
    }
  };

  const fetchEventPhotos = async (eventCode: string) => {
    setLoadingPhotos(true);
    try {
      const photos = await getEventPhotos(eventCode);
      setEventPhotos(photos);
    } catch (err) {
      console.warn("Could not fetch event photos:", err);
      setEventPhotos([]);
    } finally {
      setLoadingPhotos(false);
    }
  };

  const fetchClusters = async (eventId: string) => {
    setLoadingClusters(true);
    try {
      const c = await getEventClusters(eventId);
      setClusters(c);
    } catch (err) {
      console.warn("Could not fetch clusters:", err);
      setClusters([]);
    } finally {
      setLoadingClusters(false);
    }
  };

  const fetchSettingsAndLogs = async (eventId: string) => {
    setLoadingLogs(true);
    try {
      const s = await getEventSettings(eventId);
      setSettingsData(s);
      const logs = await getEventAuditLogs(eventId);
      setAuditLogs(logs);
    } catch (err) {
      console.warn("Could not fetch settings/logs:", err);
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    if (isAdminLoggedIn) {
      fetchEventsList();
    }
  }, [isAdminLoggedIn]);

  useEffect(() => {
    if (selectedEvent) {
      setDriveUrlInput(selectedEvent.drive_link || "");
      setDriveImportMsg("");
      setDriveImportError("");
      setUploadSuccessMsg("");
      fetchEventPhotos(selectedEvent.event_code);
      fetchClusters(selectedEvent.id);
      fetchSettingsAndLogs(selectedEvent.id);
    }
  }, [selectedEvent?.id]);

  // Handle Admin Login
  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminEmailInput.trim()) return;

    setIsLoggingIn(true);
    setLoginError("");

    try {
      const res = await adminLogin(adminEmailInput.trim(), adminPasswordInput.trim());
      sessionStorage.setItem("eventlens_admin_email", res.email);
      sessionStorage.setItem("eventlens_admin_token", res.token);
      setAdminEmailDisplay(res.email);
      setIsAdminLoggedIn(true);
    } catch (err: any) {
      setLoginError(err.message || "Failed to authenticate administrator");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleAdminLogout = () => {
    sessionStorage.removeItem("eventlens_admin_email");
    sessionStorage.removeItem("eventlens_admin_token");
    setIsAdminLoggedIn(false);
  };

  // Handle Event Creation
  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    setCreatingEvent(true);
    setCreateError("");
    try {
      const created = await createEvent(
        newTitle.trim(),
        newCode.trim() || undefined,
        newPassword.trim() || undefined,
        newDriveLink.trim() || undefined
      );
      setEvents((prev) => [created, ...prev]);
      setSelectedEvent(created);
      setDriveUrlInput(created.drive_link || "");
      setNewTitle("");
      setNewCode("");
      setNewPassword("");
      setNewDriveLink("");
      setUploadMode("photos");
    } catch (err: any) {
      setCreateError(err.message || "Failed to create event");
    } finally {
      setCreatingEvent(false);
    }
  };

  // Handle Event Deletion
  const handleDeleteEvent = async (eventId: string, eventTitle: string) => {
    if (!confirm(`Are you sure you want to permanently delete event "${eventTitle}"? This will erase all uploaded photos, detected faces, person clusters, and sharing links. This action cannot be undone.`)) {
      return;
    }

    setDeletingEventId(eventId);
    try {
      await deleteEvent(eventId);
      const remaining = events.filter((e) => e.id !== eventId);
      setEvents(remaining);
      if (selectedEvent?.id === eventId) {
        setSelectedEvent(remaining.length > 0 ? remaining[0] : null);
      }
      alert(`Event "${eventTitle}" was deleted successfully.`);
    } catch (err: any) {
      alert("Failed to delete event: " + (err.message || "Unknown error"));
    } finally {
      setDeletingEventId(null);
    }
  };

  const fetchEventStats = async (eventId: string) => {
    try {
      const stats = await getAdminStats(eventId);
      setAdminStats(stats);
    } catch (err) {
      console.warn("Could not fetch event stats:", err);
    }
  };

  // Handle Google Drive Link Import with Real-time Progress Tracking
  const handleDriveImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent || !driveUrlInput.trim()) return;

    setIsDriveImporting(true);
    setDriveImportMsg("");
    setDriveImportError("");
    setSyncTask({
      task_id: "init",
      event_id: selectedEvent.id,
      status: "downloading",
      progress_message: "Connecting to Google Drive folder...",
      current: 0,
      total: 0,
      faces_detected: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    });

    try {
      const res = await syncDriveAdmin(driveUrlInput.trim(), selectedEvent.id, selectedEvent.event_code);
      if (res.task_id) {
        const taskId = res.task_id;
        const pollInterval = setInterval(async () => {
          try {
            const status = await getSyncStatus(taskId);
            setSyncTask(status);

            if (status.status === "completed") {
              clearInterval(pollInterval);
              setIsDriveImporting(false);
              setDriveImportMsg(status.progress_message || "Successfully imported photos from Google Drive!");
              fetchEventPhotos(selectedEvent.event_code);
              fetchClusters(selectedEvent.id);
              fetchEventStats(selectedEvent.id);
              fetchEventsList();
            } else if (status.status === "failed") {
              clearInterval(pollInterval);
              setIsDriveImporting(false);
              setDriveImportError(status.error || "Failed to import from Google Drive.");
            }
          } catch (err) {
            console.warn("Poll status error:", err);
          }
        }, 1200);
      }
    } catch (err: any) {
      setIsDriveImporting(false);
      setDriveImportError(err.message || "Failed to initiate Google Drive sync.");
    }
  };

  // Handle Manual Face Indexing Trigger
  const handleIndexFaces = async (forceReindex = false) => {
    if (!selectedEvent) return;
    setIsIndexingFaces(true);
    setIndexFacesMsg("");
    try {
      const res = await indexFacesAdmin(selectedEvent.id, forceReindex);
      setIndexFacesMsg(res.message);
      fetchEventPhotos(selectedEvent.event_code);
      fetchClusters(selectedEvent.id);
      fetchEventStats(selectedEvent.id);
    } catch (err: any) {
      alert("Face indexing failed: " + err.message);
    } finally {
      setIsIndexingFaces(false);
    }
  };

  // Handle Single Photo Deletion
  const handleDeletePhoto = async (photoId: string) => {
    if (!confirm("Are you sure you want to delete this photo? This will remove its image and face biometric vectors from the gallery.")) return;
    setDeletingPhotoId(photoId);
    setPhotoDeleteSuccessMsg("");
    try {
      await deletePhoto(photoId);
      setEventPhotos((prev) => prev.filter((p) => p.id !== photoId));
      setSelectedAdminPhotoIds((prev) => {
        const next = new Set(prev);
        next.delete(photoId);
        return next;
      });
      setPhotoDeleteSuccessMsg("Photo deleted successfully.");
      setTimeout(() => setPhotoDeleteSuccessMsg(""), 3000);
      if (selectedEvent) {
        fetchEventsList();
        fetchClusters(selectedEvent.id);
        fetchEventStats(selectedEvent.id);
      }
    } catch (err: any) {
      alert("Delete photo failed: " + err.message);
    } finally {
      setDeletingPhotoId(null);
    }
  };

  // Handle Batch Photo Deletion
  const handleDeleteBatchPhotos = async () => {
    if (selectedAdminPhotoIds.size === 0) return;
    const count = selectedAdminPhotoIds.size;
    if (!confirm(`Are you sure you want to permanently delete ${count} selected photo(s)? This cannot be undone.`)) return;

    setIsBatchDeleting(true);
    setPhotoDeleteSuccessMsg("");
    try {
      const idsArray = Array.from(selectedAdminPhotoIds);
      const deletedCount = await deletePhotosBatch(idsArray);
      setEventPhotos((prev) => prev.filter((p) => !selectedAdminPhotoIds.has(p.id)));
      setSelectedAdminPhotoIds(new Set());
      setPhotoDeleteSuccessMsg(`Successfully deleted ${deletedCount} photo(s).`);
      setTimeout(() => setPhotoDeleteSuccessMsg(""), 4000);
      if (selectedEvent) {
        fetchEventsList();
        fetchClusters(selectedEvent.id);
        fetchEventStats(selectedEvent.id);
      }
    } catch (err: any) {
      alert("Batch delete failed: " + err.message);
    } finally {
      setIsBatchDeleting(false);
    }
  };

  const toggleAdminPhotoSelection = (photoId: string) => {
    setSelectedAdminPhotoIds((prev) => {
      const next = new Set(prev);
      if (next.has(photoId)) {
        next.delete(photoId);
      } else {
        next.add(photoId);
      }
      return next;
    });
  };

  const toggleSelectAllAdminPhotos = () => {
    if (selectedAdminPhotoIds.size === eventPhotos.length) {
      setSelectedAdminPhotoIds(new Set());
    } else {
      setSelectedAdminPhotoIds(new Set(eventPhotos.map((p) => p.id)));
    }
  };

  // Re-run AI clustering
  const handleRecluster = async () => {
    if (!selectedEvent) return;
    setRecomputingClusters(true);
    try {
      const updated = await recomputeClusters(selectedEvent.id);
      setClusters(updated);
    } catch (err) {
      console.error("Recluster failed:", err);
    } finally {
      setRecomputingClusters(false);
    }
  };

  // Rename Cluster
  const handleSaveClusterName = async (clusterId: string) => {
    if (!editClusterName.trim()) return;
    try {
      await renamePersonCluster(clusterId, editClusterName.trim());
      setClusters((prev) =>
        prev.map((c) => (c.cluster_id === clusterId ? { ...c, name: editClusterName.trim() } : c))
      );
      setEditingClusterId(null);
      setEditClusterName("");
    } catch (err) {
      console.error("Rename cluster failed:", err);
    }
  };

  // Merge Clusters
  const handleExecuteMerge = async () => {
    if (!mergingSourceCluster || !mergeTargetId) return;
    try {
      await mergePersonClusters(mergeTargetId, mergingSourceCluster.cluster_id);
      if (selectedEvent) fetchClusters(selectedEvent.id);
      setMergingSourceCluster(null);
      setMergeTargetId("");
    } catch (err) {
      console.error("Merge failed:", err);
    }
  };

  // Delete Person Biometrics
  const handleDeletePersonBiometrics = async (cluster: PersonCluster) => {
    if (!confirm(`Delete biometric facial data for '${cluster.name}'? Photo files will be preserved.`)) return;
    try {
      await deletePersonBiometrics(cluster.cluster_id);
      setClusters((prev) => prev.filter((c) => c.cluster_id !== cluster.cluster_id));
    } catch (err) {
      console.error("Delete person biometrics failed:", err);
    }
  };

  // Delete All Event Biometrics
  const handleDeleteAllEventBiometrics = async () => {
    if (!selectedEvent) return;
    if (!confirm(`Are you sure you want to permanently erase ALL biometric face vectors for '${selectedEvent.title}'? Original photos will be kept.`)) return;
    try {
      await deleteEventBiometrics(selectedEvent.id);
      fetchClusters(selectedEvent.id);
      alert("All facial biometrics for this event have been erased.");
    } catch (err) {
      console.error("Delete event biometrics failed:", err);
    }
  };

  // Save Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent) return;
    setSavingSettings(true);
    setSettingsSuccessMsg("");
    try {
      const res = await updateEventSettings(selectedEvent.id, {
        similarity_threshold: Number(settingsData.similarity_threshold),
        retention_days: Number(settingsData.retention_days),
        selfie_search_enabled: Boolean(settingsData.selfie_search_enabled),
        downloads_enabled: Boolean(settingsData.downloads_enabled),
      });
      setSettingsData(res);
      setSettingsSuccessMsg("Event privacy & search configuration saved!");
      setTimeout(() => setSettingsSuccessMsg(""), 3000);
    } catch (err: any) {
      alert("Failed to save settings: " + err.message);
    } finally {
      setSavingSettings(false);
    }
  };

  // Drag and Drop File Handlers
  const handleFileSelect = (filesList: FileList | null) => {
    if (!filesList) return;
    const selected = Array.from(filesList).filter((file) =>
      file.type.startsWith("image/")
    );
    setUploadFiles((prev) => [...prev, ...selected]);
    setUploadSuccessMsg("");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFileSelect(e.dataTransfer.files);
  };

  // Handle Batch Upload Execution
  const handleStartUpload = async () => {
    if (!selectedEvent || uploadFiles.length === 0) return;

    setIsUploading(true);
    setProcessedCount(0);
    setTotalCount(uploadFiles.length);
    setUploadSuccessMsg("");

    try {
      const results = await uploadBatchPhotos(
        selectedEvent.id,
        uploadFiles,
        (processed, total) => {
          setProcessedCount(processed);
          setTotalCount(total);
        }
      );

      const totalFaces = results.reduce((acc, curr) => acc + (curr.faces_detected || 0), 0);
      setUploadSuccessMsg(
        `Successfully uploaded ${results.length} photos and indexed ${totalFaces} face embeddings!`
      );
      setUploadFiles([]);
      fetchEventsList();
      fetchEventPhotos(selectedEvent.event_code);
      fetchClusters(selectedEvent.id);
      setUploadMode("photos");
    } catch (err: any) {
      console.error("Batch Upload Error:", err);
      setUploadSuccessMsg(`Upload failure: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const copyCodeToClipboard = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const copyGuestLink = (code: string) => {
    const link = `${window.location.origin}/event/${code}`;
    navigator.clipboard.writeText(link);
    setCopiedLink(code);
    setTimeout(() => setCopiedLink(null), 2000);
  };

  const progressPct = totalCount > 0 ? Math.round((processedCount / totalCount) * 100) : 0;

  if (!mounted) {
    return null;
  }

  // --- LOGIN GATE IF NOT AUTHENTICATED ---
  if (!isAdminLoggedIn) {
    return (
      <div className="min-h-[calc(100vh-4rem)] p-4 md:p-8 flex flex-col items-center justify-center relative" suppressHydrationWarning>
        <div className="w-full max-w-md mx-auto glass-panel rounded-3xl p-8 border border-white/10 shadow-[0_0_60px_rgba(0,0,0,0.6)] flex flex-col items-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#8083ff] to-[#c0c1ff] flex items-center justify-center mb-4 shadow-[0_0_25px_rgba(192,193,255,0.4)]">
            <Shield className="w-8 h-8 text-[#1000a9]" />
          </div>

          <h2 className="text-2xl font-extrabold text-white mb-1">Administrator Portal</h2>
          <p className="text-xs text-[#c7c4d7] mb-6">
            Authorized administrator access for <br />
            <span className="text-[#c0c1ff] font-bold font-mono">{DESIGNATED_ADMIN_EMAIL}</span>
          </p>

          <form onSubmit={handleAdminLogin} className="w-full flex flex-col gap-4 text-left">
            <div>
              <label className="text-xs font-semibold text-[#c7c4d7] mb-1 block">Admin Email Address</label>
              <div className="relative flex items-center">
                <Mail className="absolute left-3.5 w-4 h-4 text-[#908fa0]" />
                <input
                  type="email"
                  value={adminEmailInput}
                  onChange={(e) => setAdminEmailInput(e.target.value)}
                  placeholder="admin@example.com"
                  required
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl py-3 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[#c7c4d7] mb-1 block">Security Passcode</label>
              <div className="relative flex items-center">
                <KeyRound className="absolute left-3.5 w-4 h-4 text-[#908fa0]" />
                <input
                  type="password"
                  value={adminPasswordInput}
                  onChange={(e) => setAdminPasswordInput(e.target.value)}
                  placeholder="Passcode (default: element2018)"
                  required
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl py-3 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors"
                />
              </div>
            </div>

            {loginError && (
              <div className="p-3 bg-[#93000a]/40 border border-[#ffb4ab]/40 rounded-xl text-xs text-[#ffdad6] flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[#ffb4ab] shrink-0" />
                <span>{loginError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoggingIn}
              className="w-full bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-sm py-3.5 rounded-xl hover:opacity-95 transition-all shadow-[0_0_20px_rgba(192,193,255,0.4)] active:scale-98 flex items-center justify-center gap-2 cursor-pointer mt-2"
            >
              {isLoggingIn ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Verifying Credentials...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" /> Authorize Admin Dashboard
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-white/10 w-full text-center">
            <p className="text-[11px] text-[#908fa0]">
              Designated Super Admin: <span className="text-[#7bd0ff] font-semibold">{DESIGNATED_ADMIN_EMAIL}</span>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-12 py-10 min-h-[calc(100vh-4rem)]">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-10 pb-6 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <div className="inline-flex items-center gap-1.5 bg-[#8083ff]/15 text-[#c0c1ff] border border-[#c0c1ff]/30 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider">
              <Cpu className="w-3.5 h-3.5 text-[#7bd0ff]" /> Admin Hub
            </div>
            <div className="inline-flex items-center gap-1.5 bg-[#131b2e] text-[#dae2fd] border border-white/10 px-3 py-1 rounded-full text-xs font-semibold">
              <UserCircle className="w-3.5 h-3.5 text-[#7bd0ff]" />
              <span className="text-white font-mono">{adminEmailDisplay}</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-1" />
            </div>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white">Event & Face Intelligence</h1>
          <p className="text-sm text-[#c7c4d7] mt-1">
            Person Discovery, Face Clustering, Google Drive Sync, and Biometric Privacy Governance.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              fetchEventsList();
              if (selectedEvent) {
                fetchEventPhotos(selectedEvent.event_code);
                fetchClusters(selectedEvent.id);
                fetchSettingsAndLogs(selectedEvent.id);
              }
            }}
            className="flex items-center gap-2 bg-white/5 hover:bg-white/10 text-[#dae2fd] text-xs font-semibold px-4 py-2.5 rounded-xl border border-white/10 transition-colors cursor-pointer"
          >
            <RefreshCw className="w-4 h-4 text-[#7bd0ff]" /> Refresh
          </button>
          <button
            onClick={handleAdminLogout}
            className="flex items-center gap-1.5 bg-[#93000a]/30 hover:bg-[#93000a]/50 text-[#ffdad6] text-xs font-semibold px-3.5 py-2.5 rounded-xl border border-[#ffb4ab]/30 transition-colors cursor-pointer"
            title="Log out from Admin session"
          >
            <LogOut className="w-3.5 h-3.5" /> Logout
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Create Event & Active Events List */}
        <div className="flex flex-col gap-6">
          {/* Create Event Card */}
          <div className="glass-panel rounded-3xl p-6 border border-white/10 shadow-xl">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Plus className="w-5 h-5 text-[#8083ff]" /> Create New Event
            </h3>

            <form onSubmit={handleCreateEvent} className="flex flex-col gap-4">
              <div>
                <label className="text-xs font-semibold text-[#c7c4d7] mb-1 block">Event Title</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Maya & Santhosh Wedding 2026"
                  required
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors placeholder:text-[#908fa0]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[#c7c4d7] mb-1 block">
                  Event Code <span className="text-[#908fa0] font-normal">(Auto-generated if empty)</span>
                </label>
                <input
                  type="text"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                  placeholder="e.g. WEDDING2026"
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white uppercase focus:outline-none focus:border-[#c0c1ff] transition-colors placeholder:text-[#908fa0]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[#c7c4d7] mb-1 flex items-center justify-between">
                  <span>Event Access Password</span>
                  <span className="text-[#7bd0ff] text-[11px] font-normal">Protects downloads</span>
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="e.g. 123456 (Leave blank for public)"
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors placeholder:text-[#908fa0]"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[#c7c4d7] mb-1 flex items-center justify-between">
                  <span>Google Drive Link</span>
                  <span className="text-[#c0c1ff] text-[11px] font-normal">Auto-import</span>
                </label>
                <input
                  type="url"
                  value={newDriveLink}
                  onChange={(e) => setNewDriveLink(e.target.value)}
                  placeholder="https://drive.google.com/drive/folders/..."
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors placeholder:text-[#908fa0]"
                />
              </div>

              {createError && <p className="text-xs text-[#ffb4ab]">{createError}</p>}

              <button
                type="submit"
                disabled={creatingEvent}
                className="w-full bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-bold text-sm py-3 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-98 mt-1 cursor-pointer"
              >
                {creatingEvent ? "Creating Event..." : "Create Event"}
              </button>
            </form>
          </div>

          {/* Active Events Selector */}
          <div className="glass-panel rounded-3xl p-6 border border-white/10 shadow-xl flex-1">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Layers className="w-5 h-5 text-[#7bd0ff]" /> Your Events ({events.length})
            </h3>

            <div className="space-y-3 max-h-[360px] overflow-y-auto pr-1">
              {events.map((ev) => (
                <div
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer flex justify-between items-center ${
                    selectedEvent?.id === ev.id
                      ? "bg-[#171f33] border-[#c0c1ff] shadow-[0_0_15px_rgba(192,193,255,0.2)]"
                      : "bg-[#131b2e]/60 border-white/10 hover:border-white/20"
                  }`}
                >
                  <div className="flex-1 pr-2">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-bold text-white truncate">{ev.title}</h4>
                      {ev.is_protected && (
                        <span className="p-1 rounded bg-[#ffb4ab]/15 text-[#ffb4ab]" title="Password Protected">
                          <Lock className="w-3 h-3" />
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-[#908fa0]">
                      <span className="bg-[#8083ff]/20 text-[#c0c1ff] px-2 py-0.5 rounded font-mono font-bold">
                        {ev.event_code}
                      </span>
                      <span>&bull;</span>
                      <span>{ev.photo_count || 0} Photos</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        copyCodeToClipboard(ev.event_code);
                      }}
                      className="p-2 text-[#c7c4d7] hover:text-white bg-white/5 rounded-lg transition-colors"
                      title="Copy Event Code"
                    >
                      {copiedCode === ev.event_code ? <Check className="w-4 h-4 text-[#7bd0ff]" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <a
                      href={`/event/${ev.event_code}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="p-2 text-[#c7c4d7] hover:text-white bg-white/5 rounded-lg transition-colors"
                      title="Open Guest View"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteEvent(ev.id, ev.title);
                      }}
                      disabled={deletingEventId === ev.id}
                      className="p-2 text-[#ffb4ab] hover:text-[#ffdad6] hover:bg-[#93000a] bg-white/5 rounded-lg transition-colors cursor-pointer"
                      title="Delete Event"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Multi-tab Management Area */}
        <div className="lg:col-span-2 glass-panel rounded-3xl p-6 sm:p-8 border border-white/10 shadow-xl flex flex-col justify-between">
          <div>
            {/* Header & Target Event Info */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-4 border-b border-white/10">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <FolderSync className="w-6 h-6 text-[#c0c1ff]" /> Event Operations & Intelligence
                </h3>
                <p className="text-xs text-[#908fa0] mt-1">
                  Selected Event:{" "}
                  <span className="text-[#c0c1ff] font-bold">
                    {selectedEvent ? `${selectedEvent.title} (${selectedEvent.event_code})` : "Select an event on left"}
                  </span>
                </p>
              </div>

              {selectedEvent && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => copyGuestLink(selectedEvent.event_code)}
                    className="flex items-center gap-1.5 bg-[#8083ff]/15 hover:bg-[#8083ff]/25 text-[#c0c1ff] text-xs font-semibold px-3 py-1.5 rounded-xl border border-[#c0c1ff]/30 transition-colors"
                  >
                    {copiedLink === selectedEvent.event_code ? <Check className="w-3.5 h-3.5 text-[#7bd0ff]" /> : <LinkIcon className="w-3.5 h-3.5" />}
                    Copy Guest Link
                  </button>
                  <a
                    href={`/event/${selectedEvent.event_code}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 text-white text-xs font-semibold px-3 py-1.5 rounded-xl border border-white/10 transition-colors"
                  >
                    Preview Gallery <ExternalLink className="w-3.5 h-3.5 text-[#7bd0ff]" />
                  </a>
                </div>
              )}
            </div>

            {/* Event Stats Counter Cards */}
            {selectedEvent && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <div className="p-3.5 rounded-2xl bg-[#131b2e]/70 border border-white/10 flex flex-col">
                  <span className="text-[11px] font-medium text-[#908fa0] uppercase tracking-wider flex items-center gap-1.5">
                    <ImageIcon className="w-3.5 h-3.5 text-[#7bd0ff]" /> Total Photos
                  </span>
                  <span className="text-2xl font-extrabold text-white mt-1">
                    {adminStats?.total_photos ?? eventPhotos.length}
                  </span>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#131b2e]/70 border border-[#8083ff]/30 flex flex-col">
                  <span className="text-[11px] font-medium text-[#c0c1ff] uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-[#8083ff]" /> Faces Detected
                  </span>
                  <span className="text-2xl font-extrabold text-[#dae2fd] mt-1">
                    {adminStats?.total_faces_detected ?? eventPhotos.reduce((acc, p) => acc + (p.faces_detected || 1), 0)}
                  </span>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#131b2e]/70 border border-white/10 flex flex-col">
                  <span className="text-[11px] font-medium text-[#908fa0] uppercase tracking-wider flex items-center gap-1.5">
                    <Users className="w-3.5 h-3.5 text-[#7bd0ff]" /> Person Clusters
                  </span>
                  <span className="text-2xl font-extrabold text-white mt-1">
                    {clusters.length}
                  </span>
                </div>

                <div className="p-3.5 rounded-2xl bg-[#131b2e]/70 border border-white/10 flex flex-col">
                  <span className="text-[11px] font-medium text-[#908fa0] uppercase tracking-wider flex items-center gap-1.5">
                    {selectedEvent.is_protected ? <Lock className="w-3.5 h-3.5 text-[#ffb4ab]" /> : <Unlock className="w-3.5 h-3.5 text-[#7bd0ff]" />} Security
                  </span>
                  <span className="text-xs font-bold text-white mt-2">
                    {selectedEvent.is_protected ? "Passcode Active" : "Public Event"}
                  </span>
                </div>
              </div>
            )}

            {/* Mode Switcher Tabs (5 Tabs) */}
            <div className="flex flex-wrap border-b border-white/10 mb-6 gap-2 sm:gap-3">
              <button
                onClick={() => setUploadMode("photos")}
                className={`pb-3 px-3 sm:px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  uploadMode === "photos"
                    ? "border-[#c0c1ff] text-[#c0c1ff]"
                    : "border-transparent text-[#908fa0] hover:text-white"
                }`}
              >
                <ImageIcon className="w-4 h-4" /> Uploaded Photos ({eventPhotos.length})
              </button>

              <button
                onClick={() => setUploadMode("clusters")}
                className={`pb-3 px-3 sm:px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  uploadMode === "clusters"
                    ? "border-[#c0c1ff] text-[#c0c1ff]"
                    : "border-transparent text-[#908fa0] hover:text-white"
                }`}
              >
                <Users className="w-4 h-4 text-[#7bd0ff]" /> Person Discovery ({clusters.length})
              </button>

              <button
                onClick={() => setUploadMode("drive")}
                className={`pb-3 px-3 sm:px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  uploadMode === "drive"
                    ? "border-[#c0c1ff] text-[#c0c1ff]"
                    : "border-transparent text-[#908fa0] hover:text-white"
                }`}
              >
                <FolderSync className="w-4 h-4" /> Import Drive
              </button>

              <button
                onClick={() => setUploadMode("device")}
                className={`pb-3 px-3 sm:px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  uploadMode === "device"
                    ? "border-[#c0c1ff] text-[#c0c1ff]"
                    : "border-transparent text-[#908fa0] hover:text-white"
                }`}
              >
                <UploadCloud className="w-4 h-4" /> Upload Files
              </button>

              <button
                onClick={() => setUploadMode("settings")}
                className={`pb-3 px-3 sm:px-4 text-xs sm:text-sm font-bold flex items-center gap-1.5 border-b-2 transition-all cursor-pointer ${
                  uploadMode === "settings"
                    ? "border-[#c0c1ff] text-[#c0c1ff]"
                    : "border-transparent text-[#908fa0] hover:text-white"
                }`}
              >
                <Sliders className="w-4 h-4" /> Privacy & Governance
              </button>
            </div>

            {/* TAB 1: VIEW ALL UPLOADED PHOTOS IN WEBSITE */}
            {uploadMode === "photos" && (
              <div>
                {/* Deletion Toast Feedback */}
                {photoDeleteSuccessMsg && (
                  <div className="mb-4 p-3 rounded-2xl bg-[#00522b]/40 border border-[#2eed89]/50 text-[#c4eed0] text-xs font-semibold flex items-center justify-between animate-in fade-in">
                    <span className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-[#2eed89]" /> {photoDeleteSuccessMsg}
                    </span>
                    <button onClick={() => setPhotoDeleteSuccessMsg("")} className="p-1 hover:text-white">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {/* Toolbar & Multi-Select Controls */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-4 bg-[#131b2e]/60 p-3.5 rounded-2xl border border-white/10">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={toggleSelectAllAdminPhotos}
                      disabled={eventPhotos.length === 0}
                      className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 text-white text-xs font-semibold px-3 py-2 rounded-xl border border-white/10 transition-colors"
                    >
                      {selectedAdminPhotoIds.size === eventPhotos.length && eventPhotos.length > 0 ? (
                        <>
                          <CheckSquare className="w-3.5 h-3.5 text-[#c0c1ff]" /> Deselect All
                        </>
                      ) : (
                        <>
                          <Square className="w-3.5 h-3.5 text-[#908fa0]" /> Select All ({eventPhotos.length})
                        </>
                      )}
                    </button>

                    {selectedAdminPhotoIds.size > 0 && (
                      <button
                        onClick={handleDeleteBatchPhotos}
                        disabled={isBatchDeleting}
                        className="flex items-center gap-1.5 bg-[#93000a] hover:bg-[#ba1a1a] text-[#ffdad6] text-xs font-extrabold px-3.5 py-2 rounded-xl transition-all shadow-[0_0_15px_rgba(255,180,171,0.25)] cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        {isBatchDeleting ? "Deleting..." : `Delete (${selectedAdminPhotoIds.size}) Selected`}
                      </button>
                    )}
                  </div>

                  {eventPhotos.length > 0 && selectedEvent && (
                    <a
                      href={`/event/${selectedEvent.event_code}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[#7bd0ff] hover:underline flex items-center gap-1"
                    >
                      View Live Guest Gallery <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>

                {loadingPhotos ? (
                  <div className="py-16 text-center text-[#c7c4d7]">
                    <RefreshCw className="w-8 h-8 text-[#8083ff] animate-spin mx-auto mb-3" />
                    <p className="text-sm">Loading uploaded event photos...</p>
                  </div>
                ) : eventPhotos.length === 0 ? (
                  <div className="py-12 px-6 rounded-3xl bg-[#131b2e]/60 border border-white/10 text-center flex flex-col items-center">
                    <div className="w-14 h-14 rounded-2xl bg-[#8083ff]/15 text-[#c0c1ff] flex items-center justify-center mb-3">
                      <ImageIcon className="w-7 h-7 text-[#7bd0ff]" />
                    </div>
                    <h4 className="text-base font-bold text-white mb-1">No Photos Uploaded Yet</h4>
                    <p className="text-xs text-[#908fa0] max-w-sm mb-4">
                      Import photos from Google Drive or drag & drop files from your device.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-[520px] overflow-y-auto pr-1">
                    {eventPhotos.map((photo) => {
                      const imgUrl = getFullImageUrl(photo.thumbnail_url || photo.image_url);
                      const isSelected = selectedAdminPhotoIds.has(photo.id);
                      return (
                        <div
                          key={photo.id}
                          onClick={() => toggleAdminPhotoSelection(photo.id)}
                          className={`group relative rounded-xl overflow-hidden border bg-[#060e20] aspect-square shadow transition-all duration-200 cursor-pointer ${
                            isSelected
                              ? "border-[#c0c1ff] ring-2 ring-[#c0c1ff]/60 shadow-[0_0_20px_rgba(192,193,255,0.3)]"
                              : "border-white/10 hover:border-white/30"
                          }`}
                        >
                          <img
                            src={imgUrl}
                            alt="Uploaded Event Photo"
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                            loading="lazy"
                          />

                          {/* Top Action Bar */}
                          <div className="absolute top-2 left-2 right-2 flex justify-between items-center z-10">
                            {/* Selection Checkbox */}
                            <div
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleAdminPhotoSelection(photo.id);
                              }}
                              className={`w-6 h-6 rounded-lg flex items-center justify-center transition-all ${
                                isSelected
                                  ? "bg-[#c0c1ff] text-[#1000a9] shadow"
                                  : "bg-black/60 backdrop-blur-md text-white/50 border border-white/20 hover:text-white"
                              }`}
                            >
                              {isSelected ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : <Square className="w-3.5 h-3.5" />}
                            </div>

                            {/* Direct Delete Button */}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeletePhoto(photo.id);
                              }}
                              disabled={deletingPhotoId === photo.id}
                              className="p-1.5 bg-[#93000a]/90 hover:bg-[#ba1a1a] text-[#ffdad6] rounded-lg transition-all shadow opacity-80 group-hover:opacity-100 cursor-pointer"
                              title="Delete Photo Permanently"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          {/* Bottom Info & Action Bar */}
                          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent p-2 flex justify-between items-end opacity-0 group-hover:opacity-100 transition-opacity">
                            <span className="text-[10px] bg-black/60 backdrop-blur-md px-1.5 py-0.5 rounded text-[#7bd0ff] font-semibold border border-white/10">
                              {photo.faces_detected || 1} face(s)
                            </span>

                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPreviewPhoto(photo);
                                }}
                                className="p-1.5 bg-white/20 text-white rounded-lg backdrop-blur-md hover:bg-white/30 transition-colors"
                                title="Expand Photo"
                              >
                                <Maximize2 className="w-3.5 h-3.5" />
                              </button>
                              <a
                                href={getFullImageUrl(photo.image_url)}
                                target="_blank"
                                download
                                onClick={(e) => e.stopPropagation()}
                                className="p-1.5 bg-[#8083ff] text-[#1000a9] rounded-lg font-bold hover:bg-[#c0c1ff] transition-colors"
                                title="Download High-Res Original"
                              >
                                <Download className="w-3.5 h-3.5" />
                              </a>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: PERSON DISCOVERY & CLUSTERS */}
            {uploadMode === "clusters" && (
              <div>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-6">
                  <div>
                    <h4 className="text-sm font-bold text-white flex items-center gap-2">
                      <Users className="w-4 h-4 text-[#7bd0ff]" /> Auto-Discovered People Profiles
                    </h4>
                    <p className="text-xs text-[#908fa0] mt-0.5">
                      FaceNet AI automatically groups identical faces across all event photographs into distinct person clusters.
                    </p>
                  </div>
                  <button
                    onClick={handleRecluster}
                    disabled={recomputingClusters || !selectedEvent}
                    className="bg-[#8083ff]/15 hover:bg-[#8083ff]/25 text-[#c0c1ff] text-xs font-bold px-3.5 py-2 rounded-xl border border-[#c0c1ff]/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${recomputingClusters ? "animate-spin" : ""}`} />
                    {recomputingClusters ? "Re-Clustering..." : "Re-Run AI Clustering"}
                  </button>
                </div>

                {loadingClusters ? (
                  <div className="py-16 text-center text-[#c7c4d7]">
                    <RefreshCw className="w-8 h-8 text-[#8083ff] animate-spin mx-auto mb-3" />
                    <p className="text-sm">Analyzing FaceNet vectors & discovering people...</p>
                  </div>
                ) : clusters.length === 0 ? (
                  <div className="py-12 px-6 rounded-3xl bg-[#131b2e]/60 border border-white/10 text-center flex flex-col items-center">
                    <Users className="w-12 h-12 text-[#908fa0] mb-3" />
                    <h4 className="text-base font-bold text-white mb-1">No Person Clusters Found</h4>
                    <p className="text-xs text-[#908fa0] max-w-sm mb-4">
                      Upload or import event photos with faces to enable automatic person clustering.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1">
                    {clusters.map((cluster) => {
                      const thumb = getFullImageUrl(cluster.thumbnail_url);
                      return (
                        <div
                          key={cluster.cluster_id}
                          className="p-4 rounded-2xl bg-[#131b2e]/80 border border-white/10 hover:border-white/20 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                        >
                          <div className="flex items-center gap-4 flex-1">
                            <img
                              src={thumb}
                              alt={cluster.name}
                              className="w-14 h-14 rounded-2xl object-cover border border-white/15 shrink-0 bg-[#060e20]"
                            />
                            <div>
                              {editingClusterId === cluster.cluster_id ? (
                                <div className="flex items-center gap-2">
                                  <input
                                    type="text"
                                    value={editClusterName}
                                    onChange={(e) => setEditClusterName(e.target.value)}
                                    placeholder="Enter person name"
                                    className="bg-[#0b1326] border border-[#c0c1ff] rounded-lg px-2.5 py-1 text-xs text-white"
                                    autoFocus
                                  />
                                  <button
                                    onClick={() => handleSaveClusterName(cluster.cluster_id)}
                                    className="p-1 bg-[#8083ff] text-[#1000a9] rounded-md font-bold"
                                  >
                                    <Check className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    onClick={() => setEditingClusterId(null)}
                                    className="p-1 bg-white/10 text-white rounded-md"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              ) : (
                                <div className="flex items-center gap-2">
                                  <h4 className="text-sm font-bold text-white">{cluster.name}</h4>
                                  <button
                                    onClick={() => {
                                      setEditingClusterId(cluster.cluster_id);
                                      setEditClusterName(cluster.name);
                                    }}
                                    className="p-1 text-[#908fa0] hover:text-[#c0c1ff] transition-colors"
                                    title="Rename Person"
                                  >
                                    <Edit2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              )}
                              <p className="text-xs text-[#908fa0] mt-0.5">
                                Appears in <span className="text-[#7bd0ff] font-bold">{cluster.photo_count} photos</span> ({cluster.face_count} face detections)
                              </p>
                            </div>
                          </div>

                          {/* Photos Strip Preview */}
                          <div className="flex items-center gap-1.5 overflow-x-auto max-w-xs py-1">
                            {cluster.photos.slice(0, 4).map((p) => (
                              <img
                                key={p.photo_id}
                                src={getFullImageUrl(p.thumbnail_url || p.image_url)}
                                alt="Face Appearance"
                                className="w-9 h-9 rounded-lg object-cover border border-white/10 shrink-0"
                              />
                            ))}
                            {cluster.photos.length > 4 && (
                              <span className="text-[10px] text-[#908fa0] px-1.5 py-1 rounded bg-[#0b1326] border border-white/10">
                                +{cluster.photos.length - 4}
                              </span>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => setMergingSourceCluster(cluster)}
                              className="text-xs font-semibold px-2.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-[#c7c4d7] border border-white/10 transition-colors flex items-center gap-1 cursor-pointer"
                              title="Merge into another person profile"
                            >
                              <GitMerge className="w-3.5 h-3.5 text-[#7bd0ff]" /> Merge
                            </button>
                            <button
                              onClick={() => handleDeletePersonBiometrics(cluster)}
                              className="text-xs font-semibold p-2 rounded-xl bg-[#93000a]/20 hover:bg-[#93000a]/40 text-[#ffdad6] border border-[#ffb4ab]/20 transition-colors cursor-pointer"
                              title="Delete Person Biometrics (GDPR)"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: GOOGLE DRIVE IMPORT */}
            {uploadMode === "drive" && (
              <div className="flex flex-col gap-5">
                <div className="p-5 rounded-2xl bg-[#131b2e]/60 border border-white/10">
                  <h4 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                    <FolderSync className="w-4 h-4 text-[#7bd0ff]" /> Google Drive Import & Sync
                  </h4>
                  <p className="text-xs text-[#c7c4d7] mb-4">
                    Paste your Google Drive public folder link, file link, or folder ID below. Photos will download concurrently, extract 512-d FaceNet facial embeddings, and populate your event gallery with real-time progress.
                  </p>

                  <form onSubmit={handleDriveImport} className="flex flex-col sm:flex-row gap-3">
                    <input
                      type="text"
                      value={driveUrlInput}
                      onChange={(e) => setDriveUrlInput(e.target.value)}
                      placeholder="e.g. https://drive.google.com/drive/folders/1abc987654321xyz or Folder ID"
                      required
                      disabled={!selectedEvent || isDriveImporting}
                      className="flex-1 bg-[#0b1326] border border-white/15 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-[#c0c1ff] transition-colors placeholder:text-[#908fa0]"
                    />
                    <button
                      type="submit"
                      disabled={!selectedEvent || !driveUrlInput.trim() || isDriveImporting}
                      className={`font-bold text-sm px-6 py-3 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer ${
                        selectedEvent && driveUrlInput.trim() && !isDriveImporting
                          ? "bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] hover:opacity-95 shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95"
                          : "bg-white/10 text-[#908fa0] cursor-not-allowed"
                      }`}
                    >
                      {isDriveImporting ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin text-[#1000a9]" />
                          <span>Syncing & Indexing...</span>
                        </>
                      ) : (
                        <>
                          <FolderSync className="w-4 h-4" />
                          <span>Sync & Index Photos</span>
                        </>
                      )}
                    </button>
                  </form>

                  {/* Real-time Progress Bar & Indicator */}
                  {isDriveImporting && syncTask && (
                    <div className="mt-5 p-4 rounded-2xl bg-[#0b1326] border border-[#8083ff]/40 flex flex-col gap-3">
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-[#c0c1ff] font-semibold flex items-center gap-2">
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#7bd0ff]" />
                          {syncTask.progress_message || "Indexing event photos..."}
                        </span>
                        <span className="text-white font-mono font-bold">
                          {syncTask.total > 0
                            ? `${Math.round((syncTask.current / syncTask.total) * 100)}%`
                            : "Scanning..."}
                        </span>
                      </div>

                      {/* Progress Bar Track */}
                      <div className="w-full h-2.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[#8083ff] to-[#7bd0ff] transition-all duration-300 rounded-full shadow-[0_0_10px_rgba(128,131,255,0.6)]"
                          style={{
                            width: `${
                              syncTask.total > 0
                                ? Math.min(100, Math.round((syncTask.current / syncTask.total) * 100))
                                : 25
                            }%`,
                          }}
                        />
                      </div>

                      <div className="flex justify-between items-center text-[11px] text-[#908fa0]">
                        <span>
                          Photos: <strong className="text-white">{syncTask.current}</strong> / {syncTask.total || "..."}
                        </span>
                        <span>
                          Faces Detected: <strong className="text-[#7bd0ff]">{syncTask.faces_detected}</strong>
                        </span>
                      </div>
                    </div>
                  )}

                  <div className="mt-3 flex items-start gap-2 text-[11px] text-[#908fa0] bg-[#0b1326]/50 p-2.5 rounded-xl border border-white/5">
                    <Info className="w-4 h-4 text-[#7bd0ff] shrink-0 mt-0.5" />
                    <span>
                      <strong className="text-[#c0c1ff]">Google Drive Support:</strong> Works with public Drive folder links (set sharing to <em>"Anyone with the link can view"</em>) or authenticated Service Accounts.
                    </span>
                  </div>
                </div>

                {/* Manual Face Re-Index Trigger Card */}
                {selectedEvent && (
                  <div className="p-4 rounded-2xl bg-[#131b2e]/40 border border-white/10 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                    <div>
                      <h5 className="text-xs font-bold text-white flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-[#8083ff]" /> Re-Extract Face Vectors
                      </h5>
                      <p className="text-[11px] text-[#908fa0]">
                        Run 512-d FaceNet neural network indexing across all {eventPhotos.length} photos in gallery.
                      </p>
                    </div>
                    <button
                      onClick={() => handleIndexFaces(true)}
                      disabled={isIndexingFaces || eventPhotos.length === 0}
                      className={`text-xs font-bold px-4 py-2 rounded-xl border transition-all flex items-center gap-1.5 cursor-pointer shrink-0 ${
                        !isIndexingFaces && eventPhotos.length > 0
                          ? "bg-white/5 hover:bg-white/10 border-white/20 text-white"
                          : "bg-white/5 border-white/5 text-[#908fa0] cursor-not-allowed"
                      }`}
                    >
                      {isIndexingFaces ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Indexing Faces...
                        </>
                      ) : (
                        <>
                          <Cpu className="w-3.5 h-3.5 text-[#7bd0ff]" /> Run Face Indexing
                        </>
                      )}
                    </button>
                  </div>
                )}

                {indexFacesMsg && (
                  <div className="p-3.5 rounded-2xl bg-[#131b2e] border border-[#8083ff]/40 text-xs text-[#dae2fd] flex items-center gap-2.5">
                    <CheckCircle className="w-4 h-4 text-[#8083ff] shrink-0" />
                    <span>{indexFacesMsg}</span>
                  </div>
                )}

                {driveImportMsg && (
                  <div className="p-4 rounded-2xl bg-[#131b2e] border border-[#7bd0ff]/40 text-xs text-[#dae2fd] flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-[#7bd0ff] shrink-0" />
                    <span>{driveImportMsg}</span>
                  </div>
                )}

                {driveImportError && (
                  <div className="p-4 rounded-2xl bg-[#93000a]/40 border border-[#ffb4ab]/40 text-xs text-[#ffdad6] flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-[#ffb4ab] shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-semibold">{driveImportError}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: DEVICE BATCH UPLOAD */}
            {uploadMode === "device" && (
              <div>
                <div className="flex justify-between items-center mb-4">
                  <span className="text-xs text-[#908fa0]">
                    Select or drag-and-drop event images from your computer
                  </span>
                  {uploadFiles.length > 0 && (
                    <button
                      onClick={() => setUploadFiles([])}
                      className="text-xs text-[#ffb4ab] hover:underline cursor-pointer"
                    >
                      Clear Selection ({uploadFiles.length})
                    </button>
                  )}
                </div>

                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  className="border-2 border-dashed border-[#c0c1ff]/40 hover:border-[#c0c1ff] bg-[#131b2e]/50 hover:bg-[#131b2e] rounded-3xl p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center min-h-[200px] relative group"
                >
                  <input
                    type="file"
                    multiple
                    accept="image/*"
                    onChange={(e) => handleFileSelect(e.target.files)}
                    className="absolute inset-0 opacity-0 cursor-pointer"
                  />

                  <div className="w-14 h-14 rounded-2xl bg-[#8083ff]/15 text-[#c0c1ff] flex items-center justify-center mb-3 group-hover:scale-110 transition-transform shadow-[0_0_20px_rgba(192,193,255,0.2)]">
                    <UploadCloud className="w-7 h-7 text-[#7bd0ff]" />
                  </div>

                  <h4 className="text-base font-bold text-white mb-1">
                    Drag & Drop event photos here, or <span className="text-[#c0c1ff]">Browse Files</span>
                  </h4>
                  <p className="text-xs text-[#908fa0]">Supports high-res JPEG, PNG, WEBP files</p>
                </div>

                {uploadFiles.length > 0 && (
                  <div className="mt-4 p-4 rounded-2xl bg-[#131b2e] border border-white/10 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <ImageIcon className="w-5 h-5 text-[#7bd0ff]" />
                      <div>
                        <p className="text-sm font-bold text-white">{uploadFiles.length} Photos Selected</p>
                        <p className="text-xs text-[#908fa0]">Ready for ML face detection & 512-d FaceNet indexing</p>
                      </div>
                    </div>

                    <button
                      onClick={handleStartUpload}
                      disabled={isUploading}
                      className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-sm px-6 py-2.5 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 flex items-center gap-2 cursor-pointer"
                    >
                      <Cpu className="w-4 h-4" /> Start ML Upload
                    </button>
                  </div>
                )}

                {isUploading && (
                  <div className="mt-4 p-5 rounded-2xl bg-[#060e20] border border-[#c0c1ff]/30 shadow-2xl">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-xs font-bold text-[#c0c1ff] flex items-center gap-2">
                        <Cpu className="w-4 h-4 text-[#7bd0ff] animate-spin" />
                        Processing {processedCount} / {totalCount} photos (Face embeddings extracted)
                      </span>
                      <span className="text-xs font-bold text-white">{progressPct}%</span>
                    </div>
                    <div className="w-full bg-[#131b2e] h-2.5 rounded-full overflow-hidden border border-white/10">
                      <div
                        className="h-full bg-gradient-to-r from-[#8083ff] via-[#7bd0ff] to-[#c0c1ff] transition-all duration-300 rounded-full"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  </div>
                )}

                {uploadSuccessMsg && (
                  <div className="mt-4 p-4 rounded-2xl bg-[#131b2e] border border-[#7bd0ff]/40 text-xs text-[#dae2fd] flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-[#7bd0ff] shrink-0" />
                    <span>{uploadSuccessMsg}</span>
                  </div>
                )}
              </div>
            )}

            {/* TAB 5: PRIVACY, SECURITY & AUDIT GOVERNANCE */}
            {uploadMode === "settings" && (
              <div className="space-y-6">
                {/* Policy & Settings Card */}
                <div className="p-5 rounded-2xl bg-[#131b2e]/60 border border-white/10">
                  <h4 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-[#7bd0ff]" /> Face Search & Biometric Governance
                  </h4>

                  <form onSubmit={handleSaveSettings} className="space-y-4">
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <label className="text-xs font-semibold text-[#c7c4d7]">
                          FaceNet Similarity Match Threshold
                        </label>
                        <span className="text-xs font-bold text-[#c0c1ff] font-mono">
                          {settingsData.similarity_threshold} ({Math.round(settingsData.similarity_threshold * 100)}%)
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.20"
                        max="0.65"
                        step="0.01"
                        value={settingsData.similarity_threshold}
                        onChange={(e) => setSettingsData({ ...settingsData, similarity_threshold: parseFloat(e.target.value) })}
                        className="w-full accent-[#8083ff] cursor-pointer"
                      />
                      <span className="text-[11px] text-[#908fa0] block mt-0.5">
                        Higher values (0.45+) require tighter facial alignment. Lower values (0.30) yield higher recall for varying angles.
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                      <div>
                        <label className="text-xs font-semibold text-[#c7c4d7] mb-1 block">Biometric Data Retention</label>
                        <select
                          value={settingsData.retention_days}
                          onChange={(e) => setSettingsData({ ...settingsData, retention_days: parseInt(e.target.value) })}
                          className="w-full bg-[#0b1326] border border-white/15 rounded-xl px-3 py-2 text-xs text-white"
                        >
                          <option value="30">30 Days (Automatic Biometric Prune)</option>
                          <option value="90">90 Days (Standard Event Window)</option>
                          <option value="180">180 Days (Extended)</option>
                          <option value="365">365 Days (1 Year)</option>
                        </select>
                      </div>

                      <div className="flex flex-col justify-end">
                        <label className="flex items-center gap-2 cursor-pointer pb-2">
                          <input
                            type="checkbox"
                            checked={Boolean(settingsData.selfie_search_enabled)}
                            onChange={(e) => setSettingsData({ ...settingsData, selfie_search_enabled: e.target.checked ? 1 : 0 })}
                            className="accent-[#8083ff]"
                          />
                          <span className="text-xs text-white font-medium">Enable Selfie Face Matching</span>
                        </label>
                      </div>
                    </div>

                    {settingsSuccessMsg && (
                      <p className="text-xs text-emerald-400 font-semibold">{settingsSuccessMsg}</p>
                    )}

                    <div className="flex justify-between items-center pt-2">
                      <button
                        type="button"
                        onClick={handleDeleteAllEventBiometrics}
                        className="text-xs font-bold text-[#ffdad6] bg-[#93000a]/20 hover:bg-[#93000a]/40 px-3.5 py-2 rounded-xl border border-[#ffb4ab]/20 transition-colors flex items-center gap-1.5 cursor-pointer"
                      >
                        <ShieldAlert className="w-3.5 h-3.5" /> Erase All Event Biometrics (GDPR)
                      </button>

                      <button
                        type="submit"
                        disabled={savingSettings || !selectedEvent}
                        className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-bold text-xs px-5 py-2.5 rounded-xl hover:opacity-95 transition-all shadow cursor-pointer"
                      >
                        {savingSettings ? "Saving..." : "Save Settings"}
                      </button>
                    </div>
                  </form>
                </div>

                {/* Audit Logs Feed */}
                <div className="p-5 rounded-2xl bg-[#131b2e]/60 border border-white/10">
                  <h4 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[#7bd0ff]" /> Security & Activity Audit Log
                  </h4>
                  <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                    {auditLogs.length === 0 ? (
                      <p className="text-xs text-[#908fa0]">No activity recorded yet.</p>
                    ) : (
                      auditLogs.map((log) => (
                        <div key={log.id} className="p-2.5 rounded-xl bg-[#0b1326] border border-white/5 flex justify-between items-center text-xs">
                          <div>
                            <span className="text-[#c0c1ff] font-bold font-mono">{log.action}</span>
                            <span className="text-[#908fa0] text-[11px] block">{JSON.stringify(log.details)}</span>
                          </div>
                          <span className="text-[10px] text-[#908fa0] shrink-0 font-mono">
                            {new Date(log.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Danger Zone: Event Deletion */}
                {selectedEvent && (
                  <div className="p-5 rounded-2xl bg-[#93000a]/10 border border-[#ffb4ab]/30 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                    <div>
                      <h4 className="text-sm font-bold text-[#ffdad6] flex items-center gap-2">
                        <Trash2 className="w-4 h-4 text-[#ffb4ab]" /> Danger Zone: Delete Event
                      </h4>
                      <p className="text-xs text-[#c7c4d7] mt-1 max-w-md">
                        Permanently delete <strong>"{selectedEvent.title}"</strong> ({selectedEvent.event_code}). All uploaded photos, face vectors, and person albums will be erased immediately.
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDeleteEvent(selectedEvent.id, selectedEvent.title)}
                      disabled={deletingEventId === selectedEvent.id}
                      className="bg-[#93000a] hover:bg-[#ba1a1a] text-[#ffdad6] font-extrabold text-xs px-4 py-2.5 rounded-xl border border-[#ffb4ab]/40 transition-all shadow cursor-pointer shrink-0"
                    >
                      {deletingEventId === selectedEvent.id ? "Deleting Event..." : "Delete Entire Event"}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Merge Modal */}
      {mergingSourceCluster && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
          <div className="glass-panel rounded-3xl p-6 max-w-md w-full border border-white/15 shadow-2xl flex flex-col gap-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <GitMerge className="w-5 h-5 text-[#7bd0ff]" /> Merge Person Profile
            </h3>
            <p className="text-xs text-[#c7c4d7]">
              Merge <strong>{mergingSourceCluster.name}</strong> ({mergingSourceCluster.photo_count} photos) into another person cluster:
            </p>

            <select
              value={mergeTargetId}
              onChange={(e) => setMergeTargetId(e.target.value)}
              className="w-full bg-[#0b1326] border border-white/15 rounded-xl p-3 text-xs text-white"
            >
              <option value="">-- Select Target Person Profile --</option>
              {clusters
                .filter((c) => c.cluster_id !== mergingSourceCluster.cluster_id)
                .map((c) => (
                  <option key={c.cluster_id} value={c.cluster_id}>
                    {c.name} ({c.photo_count} photos)
                  </option>
                ))}
            </select>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setMergingSourceCluster(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-white/5 text-[#c7c4d7] hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteMerge}
                disabled={!mergeTargetId}
                className="px-5 py-2 rounded-xl text-xs font-bold bg-[#8083ff] text-[#1000a9] hover:bg-[#c0c1ff] disabled:opacity-50"
              >
                Confirm Merge
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Photo Preview Modal */}
      {previewPhoto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-2xl animate-in fade-in">
          <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col glass-modal rounded-3xl overflow-hidden border border-white/10 shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#0b1326]/60 backdrop-blur-md">
              <div className="flex items-center gap-3">
                <span className="text-xs text-[#c0c1ff] font-semibold">Photo ID: {previewPhoto.id.slice(0, 8)}...</span>
                <span className="text-xs text-[#7bd0ff] bg-[#131b2e] px-2 py-0.5 rounded border border-white/10">
                  {previewPhoto.faces_detected || 1} face(s) indexed
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    const pid = previewPhoto.id;
                    setPreviewPhoto(null);
                    handleDeletePhoto(pid);
                  }}
                  className="flex items-center gap-1.5 bg-[#93000a] hover:bg-[#ba1a1a] text-[#ffdad6] text-xs font-bold px-3 py-1.5 rounded-xl transition-colors shadow cursor-pointer"
                  title="Delete This Photo"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Delete Photo
                </button>
                <a
                  href={getFullImageUrl(previewPhoto.image_url)}
                  target="_blank"
                  download
                  className="flex items-center gap-1.5 bg-[#8083ff] text-[#1000a9] text-xs font-bold px-3 py-1.5 rounded-xl hover:bg-[#c0c1ff] transition-colors"
                >
                  <Download className="w-3.5 h-3.5" /> Download Original
                </a>
                <button
                  onClick={() => setPreviewPhoto(null)}
                  className="p-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-white transition-colors cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 bg-[#060e20] flex items-center justify-center p-4 min-h-[350px]">
              <img
                src={getFullImageUrl(previewPhoto.image_url)}
                alt="Event photo high resolution"
                className="max-h-[70vh] max-w-full object-contain rounded-xl shadow-xl"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
