export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    // In browser, use same-origin relative URL handled by Next.js rewrites proxy
    return "/api";
  }
  return process.env.BACKEND_INTERNAL_URL ? `${process.env.BACKEND_INTERNAL_URL}/api` : "http://127.0.0.1:8000/api";
}

export function getBackendUrl(): string {
  if (process.env.NEXT_PUBLIC_BACKEND_URL) {
    return process.env.NEXT_PUBLIC_BACKEND_URL;
  }
  if (typeof window !== "undefined") {
    return "";
  }
  return process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";
}

export const API_BASE_URL = "/api";
export const BACKEND_URL = "";

export interface EventData {
  id: string;
  title: string;
  event_code: string;
  created_at: string;
  photo_count: number;
  is_protected?: boolean;
  drive_link?: string;
}

export interface PhotoData {
  id: string;
  event_id: string;
  image_url: string;
  thumbnail_url: string;
  created_at: string;
  faces_detected: number;
}

export interface MatchResult {
  photo_id: string;
  image_url: string;
  thumbnail_url: string;
  similarity: number;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface MatchResponseData {
  count: number;
  matches: MatchResult[];
  message: string;
}

/**
 * Client-side high-speed image compression helper.
 * Downsamples selfies to 720px for sub-50ms network transmission and sub-second matching.
 */
export async function compressImage(file: File | Blob, maxDimension = 720, quality = 0.85): Promise<File> {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        let width = img.width;
        let height = img.height;

        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(file instanceof File ? file : new File([file], "selfie.jpg", { type: "image/jpeg" }));
          return;
        }

        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (blob) => {
            if (blob) {
              const compressedFile = new File([blob], "selfie.jpg", {
                type: "image/jpeg",
                lastModified: Date.now(),
              });
              resolve(compressedFile);
            } else {
              resolve(file instanceof File ? file : new File([file], "selfie.jpg", { type: "image/jpeg" }));
            }
          },
          "image/jpeg",
          quality
        );
      };
      img.onerror = () => resolve(file instanceof File ? file : new File([file], "selfie.jpg", { type: "image/jpeg" }));
      img.src = e.target?.result as string;
    };
    reader.onerror = () => resolve(file instanceof File ? file : new File([file], "selfie.jpg", { type: "image/jpeg" }));
    reader.readAsDataURL(file);
  });
}

/**
 * Normalizes photo image URLs to ensure clean same-origin paths
 * through Next.js proxy on all mobile, desktop, and tablet devices.
 */
export function getFullImageUrl(url: string): string {
  if (!url) return "/placeholder.jpg";
  if (url.startsWith("http://") || url.startsWith("https://")) {
    if (url.includes("/static/")) {
      const idx = url.indexOf("/static/");
      return url.substring(idx);
    }
    return url;
  }
  if (url.startsWith("/")) {
    return url;
  }
  return `/${url}`;
}

export async function createEvent(
  title: string,
  event_code?: string,
  password?: string,
  drive_link?: string
): Promise<EventData> {
  const base = getApiBaseUrl();
  const res = await fetch(`${base}/events/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title,
      event_code: event_code || null,
      password: password || null,
      drive_link: drive_link || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to create event");
  }
  return res.json();
}

export async function verifyEventPassword(
  event_code: string,
  password: string
): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${getApiBaseUrl()}/events/verify-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_code: event_code.trim().toUpperCase(),
      password: password.trim(),
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Invalid event password");
  }
  return res.json();
}

export async function importGoogleDrive(
  eventId: string,
  driveLink: string
): Promise<{ success: boolean; imported_count: number; total_faces: number; message: string }> {
  const res = await fetch(`${getApiBaseUrl()}/events/import-drive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: eventId,
      drive_link: driveLink.trim(),
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to import photos from Google Drive");
  }
  return res.json();
}

export async function getEventByCode(code: string): Promise<EventData> {
  const res = await fetch(`${getApiBaseUrl()}/events/${encodeURIComponent(code)}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Event not found");
  }
  return res.json();
}

export async function getEventPhotos(code: string, limit = 100, offset = 0): Promise<PhotoData[]> {
  const res = await fetch(
    `${getApiBaseUrl()}/events/${encodeURIComponent(code)}/photos?limit=${limit}&offset=${offset}`
  );
  if (!res.ok) {
    throw new Error("Failed to load event photos");
  }
  return res.json();
}

export async function listEvents(): Promise<EventData[]> {
  const res = await fetch(`${getApiBaseUrl()}/events`);
  if (!res.ok) {
    throw new Error("Failed to fetch events list");
  }
  return res.json();
}

export async function deleteEvent(eventIdOrCode: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/events/${encodeURIComponent(eventIdOrCode)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete event");
  }
}

export async function uploadBatchPhotos(
  eventId: string,
  files: File[],
  onProgress?: (processed: number, total: number) => void
): Promise<PhotoData[]> {
  const total = files.length;
  const BATCH_SIZE = 3;
  const allResults: PhotoData[] = [];

  for (let i = 0; i < total; i += BATCH_SIZE) {
    const batch = files.slice(i, i + BATCH_SIZE);
    const compressedBatch = await Promise.all(batch.map((f) => compressImage(f)));

    const formData = new FormData();
    formData.append("event_id", eventId);
    compressedBatch.forEach((f) => formData.append("files", f));

    const res = await fetch(`${getApiBaseUrl()}/photos/upload-batch`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to upload batch photos");
    }

    const batchRes: PhotoData[] = await res.json();
    allResults.push(...batchRes);

    if (onProgress) {
      onProgress(Math.min(i + BATCH_SIZE, total), total);
    }
  }

  return allResults;
}

export async function deletePhotosBatch(photoIds: string[]): Promise<number> {
  const res = await fetch(`${getApiBaseUrl()}/photos/delete-batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_ids: photoIds }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete batch photos");
  }
  const data = await res.json();
  return data.count || photoIds.length;
}

export async function syncDriveAdmin(
  driveLink: string,
  eventId?: string,
  eventCode?: string
): Promise<{ success: boolean; task_id: string; event_id: string; status: string; message: string }> {
  const res = await fetch(`${getApiBaseUrl()}/admin/sync-drive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      drive_link: driveLink.trim(),
      event_id: eventId || null,
      event_code: eventCode || null,
    }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to start Google Drive sync");
  }
  return res.json();
}

export interface SyncTaskStatus {
  task_id: string;
  event_id: string;
  status: "pending" | "downloading" | "indexing" | "completed" | "failed";
  progress_message: string;
  current: number;
  total: number;
  faces_detected: number;
  created_at: string;
  updated_at: string;
  error?: string | null;
}

export async function getSyncStatus(taskId: string): Promise<SyncTaskStatus> {
  const res = await fetch(`${getApiBaseUrl()}/admin/sync-status/${encodeURIComponent(taskId)}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Could not fetch sync status");
  }
  return res.json();
}

export interface AdminStatsData {
  event_id: string;
  event_code: string;
  title: string;
  total_photos: number;
  total_faces_detected: number;
  total_clusters: number;
  is_protected: boolean;
  drive_link?: string;
}

export async function getAdminStats(eventId: string): Promise<AdminStatsData> {
  const res = await fetch(`${getApiBaseUrl()}/admin/stats/${encodeURIComponent(eventId)}`);
  if (!res.ok) {
    throw new Error("Could not fetch event stats");
  }
  return res.json();
}

export async function indexFacesAdmin(
  eventId: string,
  forceReindex = false
): Promise<{ success: boolean; photos_processed: number; faces_detected: number; message: string }> {
  const res = await fetch(`${getApiBaseUrl()}/admin/index-faces`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId, force_reindex: forceReindex }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to index faces");
  }
  return res.json();
}

export async function searchFaceApi(
  eventIdOrCode: string,
  selfie: File | Blob | string,
  threshold = 0.68
): Promise<MatchResponseData> {
  if (typeof selfie === "string") {
    // Base64 JSON
    const res = await fetch(`${getApiBaseUrl()}/search-face`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event_id: eventIdOrCode,
        selfie_base64: selfie,
        threshold: threshold,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Face search failed");
    }
    return res.json();
  }

  // File / Blob multipart
  const compressedSelfie =
    selfie instanceof File
      ? await compressImage(selfie, 720, 0.85)
      : new File([selfie], "selfie.jpg", { type: "image/jpeg" });

  const formData = new FormData();
  formData.append("event_id", eventIdOrCode);
  formData.append("threshold", String(threshold));
  formData.append("selfie", compressedSelfie);

  const res = await fetch(`${getApiBaseUrl()}/search-face`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Face search failed");
  }

  return res.json();
}

export const matchAttendeeSelfie = searchFaceApi;

export async function adminLogin(
  email: string,
  password?: string
): Promise<{ success: boolean; email: string; role: string; token: string; message: string }> {
  const res = await fetch(`${getApiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim(), password: password?.trim() || "admin123" }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Admin authentication failed");
  }
  return res.json();
}

export async function getAdminProfile(): Promise<{ admin_email: string; role: string; status: string }> {
  const res = await fetch(`${getApiBaseUrl()}/auth/profile`);
  if (!res.ok) {
    throw new Error("Could not fetch admin profile");
  }
  return res.json();
}

export async function deletePhoto(photoId: string): Promise<boolean> {
  const res = await fetch(`${getApiBaseUrl()}/photos/${photoId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Failed to delete photo");
  }
  const data = await res.json();
  return data.success;
}

export async function downloadPhotosZip(photoUrls: string[]): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/photos/download-zip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(photoUrls),
  });

  if (!res.ok) {
    throw new Error("Failed to download zip package");
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `EventLens_Photos_${Date.now()}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// --- PERSON DISCOVERY & CLUSTERING APIS ---
export interface PersonCluster {
  cluster_id: string;
  event_id: string;
  name: string;
  thumbnail_url: string;
  face_count: number;
  photo_count: number;
  photos: {
    photo_id: string;
    image_url: string;
    thumbnail_url: string;
    bounding_box?: any;
    created_at?: string;
  }[];
}

export async function getEventClusters(eventId: string): Promise<PersonCluster[]> {
  const res = await fetch(`${getApiBaseUrl()}/clusters/event/${eventId}`);
  if (!res.ok) {
    throw new Error("Failed to fetch event clusters");
  }
  const data = await res.json();
  return data.clusters || [];
}

export async function recomputeClusters(eventId: string, threshold = 0.38): Promise<PersonCluster[]> {
  const res = await fetch(`${getApiBaseUrl()}/clusters/event/${eventId}/recluster?threshold=${threshold}`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error("Failed to recompute clusters");
  }
  const data = await res.json();
  return data.clusters || [];
}

export async function renamePersonCluster(clusterId: string, name: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/clusters/${clusterId}/name`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    throw new Error("Failed to rename person cluster");
  }
}

export async function mergePersonClusters(targetClusterId: string, sourceClusterId: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/clusters/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_cluster_id: targetClusterId, source_cluster_id: sourceClusterId }),
  });
  if (!res.ok) {
    throw new Error("Failed to merge person clusters");
  }
}

export async function deletePersonBiometrics(clusterId: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/clusters/${clusterId}/biometrics`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Failed to delete person biometrics");
  }
}

// --- SECURE TEMPORARY SHARING APIS ---
export interface ShareLinkResponse {
  success: boolean;
  token: string;
  share_url: string;
  expires_in_hours: number;
}

export interface SharedGalleryData {
  token: string;
  event_id: string;
  event_title: string;
  event_code: string;
  expires_at: string;
  photos: PhotoData[];
}

export async function createTemporaryShareLink(eventId: string, photoIds: string[], expiryHours = 48): Promise<ShareLinkResponse> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: eventId, photo_ids: photoIds, expiry_hours: expiryHours }),
  });
  if (!res.ok) {
    throw new Error("Failed to create temporary sharing link");
  }
  return res.json();
}

export async function getSharedGalleryPhotos(token: string): Promise<SharedGalleryData> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/${token}`);
  if (!res.ok) {
    throw new Error("This sharing link is invalid, expired, or has been revoked.");
  }
  return res.json();
}

export async function revokeTemporaryShareLink(token: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/${token}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Failed to revoke sharing link");
  }
}

// --- PRIVACY & AUDIT LOG APIS ---
export interface AuditLogEntry {
  id: string;
  event_id?: string;
  action: string;
  details: Record<string, any>;
  timestamp: string;
}

export interface EventSettingsData {
  event_id: string;
  similarity_threshold: number;
  retention_days: number;
  selfie_search_enabled: number;
  downloads_enabled: number;
}

export async function getEventAuditLogs(eventId: string): Promise<AuditLogEntry[]> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/audit-logs/${eventId}`);
  if (!res.ok) {
    return [];
  }
  const data = await res.json();
  return data.logs || [];
}

export async function deleteEventBiometrics(eventId: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/event/${eventId}/biometrics`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error("Failed to delete event biometrics");
  }
}

export async function getEventSettings(eventId: string): Promise<EventSettingsData> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/settings/${eventId}`);
  if (!res.ok) {
    return {
      event_id: eventId,
      similarity_threshold: 0.35,
      retention_days: 90,
      selfie_search_enabled: 1,
      downloads_enabled: 1,
    };
  }
  return res.json();
}

export async function updateEventSettings(
  eventId: string,
  settings: {
    similarity_threshold: number;
    retention_days: number;
    selfie_search_enabled: boolean;
    downloads_enabled: boolean;
  }
): Promise<EventSettingsData> {
  const res = await fetch(`${getApiBaseUrl()}/sharing/settings/${eventId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) {
    throw new Error("Failed to update event settings");
  }
  const data = await res.json();
  return data.settings;
}
