"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { 
  Download, RefreshCw, ArrowLeft, Sparkles, Image as ImageIcon, 
  ShieldCheck, CheckCircle2, Lock, CheckSquare, Square, 
  Check, Eye, Layers, Share2, Copy, ExternalLink, X, Clock,
  Users, User, Search
} from "lucide-react";
import { PhotoMasonry } from "@/components/PhotoMasonry";
import { LightboxModal } from "@/components/LightboxModal";
import { 
  MatchResult, MatchResponseData, downloadPhotosZip, 
  getFullImageUrl, getEventByCode, getEventPhotos, 
  createTemporaryShareLink, getEventClusters,
  PhotoData, EventData, PersonCluster 
} from "@/lib/api";
import confetti from "canvas-confetti";

export default function GalleryPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawParam = (params.code as string) || "";
  const eventCode = decodeURIComponent(rawParam).trim().toUpperCase();
  const initialTab = searchParams.get("tab") === "all" ? "all" : searchParams.get("tab") === "people" ? "people" : "selfie";

  const [activeTab, setActiveTab] = useState<"selfie" | "all" | "people">(initialTab);
  const [eventData, setEventData] = useState<EventData | null>(null);
  const [mounted, setMounted] = useState(false);
  const [matches, setMatches] = useState<MatchResult[]>([]);
  const [allPhotos, setAllPhotos] = useState<PhotoData[]>([]);
  const [clusters, setClusters] = useState<PersonCluster[]>([]);
  const [selectedCluster, setSelectedCluster] = useState<PersonCluster | null>(null);
  const [clusterSearchQuery, setClusterSearchQuery] = useState("");
  const [selectedPhoto, setSelectedPhoto] = useState<MatchResult | null>(null);
  const [isZipping, setIsZipping] = useState(false);
  const [loading, setLoading] = useState(true);

  // Temporary Share Link Modal State
  const [shareModalOpen, setShareModalOpen] = useState(false);
  const [generatedShareUrl, setGeneratedShareUrl] = useState("");
  const [creatingShareLink, setCreatingShareLink] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);
  const [expiryHours, setExpiryHours] = useState(48);

  // Multi-select state
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedPhotoUrls, setSelectedPhotoUrls] = useState<Set<string>>(new Set());

  useEffect(() => {
    setMounted(true);
    async function initGallery() {
      try {
        const targetLookup = eventCode || rawParam;
        const ev = await getEventByCode(targetLookup);
        setEventData(ev);

        // Verify password protection
        if (ev.is_protected) {
          const isUnlocked = 
            sessionStorage.getItem(`eventlens_unlocked_${eventCode}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${rawParam}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${ev.id}`) === "true" ||
            sessionStorage.getItem(`eventlens_unlocked_${ev.event_code}`) === "true";
          if (!isUnlocked) {
            router.push(`/event/${encodeURIComponent(ev.event_code || eventCode)}`);
            return;
          }
        }

        // 1. Load Match Results from session
        const stored = 
          sessionStorage.getItem(`eventlens_matches_${eventCode}`) ||
          sessionStorage.getItem(`eventlens_matches_${rawParam}`) ||
          sessionStorage.getItem(`eventlens_matches_${encodeURIComponent(eventCode)}`);
          
        if (stored) {
          try {
            const data: MatchResponseData = JSON.parse(stored);
            setMatches(data.matches || []);
            if (data.matches && data.matches.length > 0 && initialTab === "selfie") {
              confetti({
                particleCount: 80,
                spread: 70,
                origin: { y: 0.6 },
                colors: ["#c0c1ff", "#8083ff", "#7bd0ff"],
              });
            }
          } catch (err) {
            console.error("Error parsing stored matches:", err);
          }
        }

        // 2. Fetch all event photos
        try {
          const photos = await getEventPhotos(ev.id || eventCode);
          setAllPhotos(photos);
        } catch (err) {
          console.warn("Could not load full event photos:", err);
        }

        // 3. Fetch Google Photos style Person Clusters
        try {
          const c = await getEventClusters(ev.id || eventCode);
          setClusters(c);
        } catch (err) {
          console.warn("Could not load person clusters:", err);
        }

      } catch (err) {
        console.warn("Gallery init error:", err);
      } finally {
        setLoading(false);
      }
    }

    initGallery();
  }, [eventCode, rawParam, initialTab, router]);

  // Download All Matched Photos (.ZIP)
  const handleDownloadAllMatchedZip = async () => {
    if (matches.length === 0) return;
    setIsZipping(true);
    try {
      const urls = matches.map((m) => getFullImageUrl(m.image_url));
      await downloadPhotosZip(urls);
    } catch (err) {
      console.error("ZIP Download failed:", err);
      matches.forEach((m) => {
        const a = document.createElement("a");
        a.href = getFullImageUrl(m.image_url);
        a.target = "_blank";
        a.download = `Photo_${m.photo_id.slice(0, 6)}.jpg`;
        a.click();
      });
    } finally {
      setIsZipping(false);
    }
  };

  // Download All Event Photos (.ZIP)
  const handleDownloadAllEventPhotosZip = async () => {
    if (allPhotos.length === 0) return;
    setIsZipping(true);
    try {
      const urls = allPhotos.map((p) => getFullImageUrl(p.image_url));
      await downloadPhotosZip(urls);
    } catch (err) {
      console.error("ZIP Download failed:", err);
      allPhotos.forEach((p) => {
        const a = document.createElement("a");
        a.href = getFullImageUrl(p.image_url);
        a.target = "_blank";
        a.download = `EventPhoto_${p.id.slice(0, 6)}.jpg`;
        a.click();
      });
    } finally {
      setIsZipping(false);
    }
  };

  // Download Selected Person Cluster Photos (.ZIP)
  const handleDownloadClusterZip = async () => {
    if (!selectedCluster || selectedCluster.photos.length === 0) return;
    setIsZipping(true);
    try {
      const urls = selectedCluster.photos.map((p) => getFullImageUrl(p.image_url));
      await downloadPhotosZip(urls);
    } catch (err) {
      console.error("Cluster ZIP download failed:", err);
    } finally {
      setIsZipping(false);
    }
  };

  // Toggle Single Selection
  const togglePhotoSelection = (url: string) => {
    setSelectedPhotoUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else {
        next.add(url);
      }
      return next;
    });
  };

  // Download Selected Photos (.ZIP)
  const handleDownloadSelectedZip = async () => {
    if (selectedPhotoUrls.size === 0) return;
    setIsZipping(true);
    try {
      const urls = Array.from(selectedPhotoUrls).map((u) => getFullImageUrl(u));
      await downloadPhotosZip(urls);
      setIsSelectMode(false);
      setSelectedPhotoUrls(new Set());
    } catch (err) {
      console.error("Selected photos ZIP download failed:", err);
    } finally {
      setIsZipping(false);
    }
  };

  // Select / Deselect All
  const toggleSelectAll = () => {
    if (activeTab === "selfie") {
      if (selectedPhotoUrls.size === matches.length) {
        setSelectedPhotoUrls(new Set());
      } else {
        setSelectedPhotoUrls(new Set(matches.map((m) => m.image_url)));
      }
    } else if (activeTab === "people" && selectedCluster) {
      if (selectedPhotoUrls.size === selectedCluster.photos.length) {
        setSelectedPhotoUrls(new Set());
      } else {
        setSelectedPhotoUrls(new Set(selectedCluster.photos.map((p) => p.image_url)));
      }
    } else {
      if (selectedPhotoUrls.size === allPhotos.length) {
        setSelectedPhotoUrls(new Set());
      } else {
        setSelectedPhotoUrls(new Set(allPhotos.map((p) => p.image_url)));
      }
    }
  };

  // Generate Temporary Private Share Link
  const handleGenerateShareLink = async () => {
    if (!eventData) return;
    const pIds = activeTab === "selfie" 
      ? matches.map((m) => m.photo_id) 
      : selectedCluster 
      ? selectedCluster.photos.map((p) => p.photo_id)
      : [];
    if (pIds.length === 0) return;

    setCreatingShareLink(true);
    try {
      const res = await createTemporaryShareLink(eventData.id, pIds, expiryHours);
      const fullUrl = `${window.location.origin}${res.share_url}`;
      setGeneratedShareUrl(fullUrl);
      setShareModalOpen(true);
    } catch (err: any) {
      alert("Failed to generate sharing link: " + err.message);
    } finally {
      setCreatingShareLink(false);
    }
  };

  const copyShareLink = () => {
    navigator.clipboard.writeText(generatedShareUrl);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2000);
  };

  // Convert allPhotos & cluster photos to MatchResult format for unified rendering
  const allPhotosAsMatches: MatchResult[] = allPhotos.map((p) => ({
    photo_id: p.id,
    image_url: p.image_url,
    thumbnail_url: p.thumbnail_url,
    similarity: 1.0,
  }));

  const clusterPhotosAsMatches: MatchResult[] = selectedCluster
    ? selectedCluster.photos.map((p) => ({
        photo_id: p.photo_id,
        image_url: p.image_url,
        thumbnail_url: p.thumbnail_url,
        similarity: 1.0,
        bounding_box: p.bounding_box,
      }))
    : [];

  const rawDisplayList = 
    activeTab === "selfie" 
      ? matches 
      : activeTab === "people" && selectedCluster 
      ? clusterPhotosAsMatches 
      : allPhotosAsMatches;

  // Strict Deduplication: Guarantees no photo ever appears twice
  const currentDisplayList = React.useMemo(() => {
    const seen = new Set<string>();
    const unique: MatchResult[] = [];
    for (const item of rawDisplayList) {
      const key = (item.image_url || item.photo_id || "").toLowerCase().trim();
      if (!key || !seen.has(key)) {
        if (key) seen.add(key);
        unique.push(item);
      }
    }
    return unique;
  }, [rawDisplayList]);

  const filteredClusters = clusters.filter((c) =>
    c.name.toLowerCase().includes(clusterSearchQuery.toLowerCase())
  );

  if (!mounted) {
    return null;
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] pb-16" suppressHydrationWarning>
      {/* Sticky Header Banner */}
      <div className="sticky top-16 z-40 bg-[#0b1326]/90 backdrop-blur-xl border-b border-white/10 shadow-lg px-4 md:px-12 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <button
                onClick={() => router.push(`/event/${encodeURIComponent(eventCode)}`)}
                className="text-xs font-medium text-[#c0c1ff] hover:underline flex items-center gap-1"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Back to Scanner
              </button>
              <span className="text-xs text-[#908fa0]">&bull;</span>
              <span className="text-xs text-[#7bd0ff] font-semibold">Event: {eventCode}</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2">
              {activeTab === "selfie" ? (
                matches.length > 0 ? (
                  <>
                    <Sparkles className="w-5 h-5 text-[#8083ff]" />
                    Found {matches.length} {matches.length === 1 ? "photo" : "photos"} of you
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5 text-[#c0c1ff]" />
                    Photos Not Available / Face Not Clear
                  </>
                )
              ) : activeTab === "people" ? (
                selectedCluster ? (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedCluster(null)}
                      className="text-sm font-semibold text-[#c0c1ff] hover:underline flex items-center gap-1 mr-2"
                    >
                      <ArrowLeft className="w-4 h-4" /> All People
                    </button>
                    <span>{selectedCluster.name} ({selectedCluster.photo_count} photos)</span>
                  </div>
                ) : (
                  <>
                    <Users className="w-5 h-5 text-[#8083ff]" />
                    People & Faces ({clusters.length} discovered)
                  </>
                )
              ) : (
                <>
                  <ImageIcon className="w-5 h-5 text-[#7bd0ff]" />
                  Full Event Gallery ({allPhotos.length} {allPhotos.length === 1 ? "photo" : "photos"})
                </>
              )}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
            {/* Multi-Select Toggle */}
            <button
              onClick={() => {
                setIsSelectMode(!isSelectMode);
                setSelectedPhotoUrls(new Set());
              }}
              className={`text-xs font-semibold px-3.5 py-2.5 rounded-xl border transition-colors flex items-center gap-1.5 ${
                isSelectMode
                  ? "bg-[#c0c1ff] text-[#1000a9] border-[#c0c1ff]"
                  : "bg-white/5 hover:bg-white/10 text-[#dae2fd] border-white/10"
              }`}
            >
              <CheckSquare className="w-4 h-4" />
              {isSelectMode ? "Cancel Select" : "Select Photos"}
            </button>

            {isSelectMode && (
              <>
                <button
                  onClick={toggleSelectAll}
                  className="bg-white/5 hover:bg-white/10 text-white font-medium text-xs px-3.5 py-2.5 rounded-xl border border-white/10 transition-colors"
                >
                  Select All
                </button>

                {selectedPhotoUrls.size > 0 && (
                  <button
                    onClick={handleDownloadSelectedZip}
                    disabled={isZipping}
                    className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2.5 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] flex items-center gap-1.5"
                  >
                    <Download className="w-4 h-4" />
                    Download ({selectedPhotoUrls.size}) Selected
                  </button>
                )}
              </>
            )}

            {!isSelectMode && (
              <>
                <button
                  onClick={() => router.push(`/event/${encodeURIComponent(eventCode)}`)}
                  className="bg-white/5 hover:bg-white/10 text-white font-medium text-xs px-3.5 py-2.5 rounded-xl border border-white/10 transition-colors flex items-center gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-[#7bd0ff]" /> Retake Selfie
                </button>

                {activeTab === "selfie" && matches.length > 0 && (
                  <>
                    <button
                      onClick={handleGenerateShareLink}
                      disabled={creatingShareLink}
                      className="bg-white/10 hover:bg-white/20 text-[#dae2fd] font-bold text-xs px-3.5 py-2.5 rounded-xl border border-white/15 transition-all flex items-center gap-1.5 cursor-pointer"
                      title="Create Temporary Private Link"
                    >
                      <Share2 className="w-4 h-4 text-[#7bd0ff]" />
                      {creatingShareLink ? "Generating..." : "Share My Photos"}
                    </button>

                    <button
                      onClick={handleDownloadAllMatchedZip}
                      disabled={isZipping}
                      className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2.5 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 flex items-center gap-1.5"
                    >
                      <Download className="w-4 h-4" />
                      {isZipping ? "Zipping..." : "Download All My Photos (.zip)"}
                    </button>
                  </>
                )}

                {activeTab === "people" && selectedCluster && selectedCluster.photos.length > 0 && (
                  <>
                    <button
                      onClick={handleGenerateShareLink}
                      disabled={creatingShareLink}
                      className="bg-white/10 hover:bg-white/20 text-[#dae2fd] font-bold text-xs px-3.5 py-2.5 rounded-xl border border-white/15 transition-all flex items-center gap-1.5 cursor-pointer"
                    >
                      <Share2 className="w-4 h-4 text-[#7bd0ff]" /> Share {selectedCluster.name}
                    </button>

                    <button
                      onClick={handleDownloadClusterZip}
                      disabled={isZipping}
                      className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2.5 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 flex items-center gap-1.5"
                    >
                      <Download className="w-4 h-4" />
                      {isZipping ? "Zipping..." : `Download ${selectedCluster.name}'s Photos (.zip)`}
                    </button>
                  </>
                )}

                {activeTab === "all" && allPhotos.length > 0 && (
                  <button
                    onClick={handleDownloadAllEventPhotosZip}
                    disabled={isZipping}
                    className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2.5 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 flex items-center gap-1.5"
                  >
                    <Download className="w-4 h-4" />
                    {isZipping ? "Zipping..." : "Download Entire Gallery (.zip)"}
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="max-w-7xl mx-auto flex gap-6 mt-4 border-t border-white/10 pt-3 overflow-x-auto">
          <button
            onClick={() => {
              setActiveTab("selfie");
              setSelectedCluster(null);
            }}
            className={`text-xs font-bold pb-1 flex items-center gap-1.5 border-b-2 transition-all whitespace-nowrap ${
              activeTab === "selfie"
                ? "border-[#c0c1ff] text-[#c0c1ff]"
                : "border-transparent text-[#908fa0] hover:text-white"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-[#7bd0ff]" /> My Matched Photos ({matches.length})
          </button>

          <button
            onClick={() => {
              setActiveTab("people");
              setSelectedCluster(null);
            }}
            className={`text-xs font-bold pb-1 flex items-center gap-1.5 border-b-2 transition-all whitespace-nowrap ${
              activeTab === "people"
                ? "border-[#c0c1ff] text-[#c0c1ff]"
                : "border-transparent text-[#908fa0] hover:text-white"
            }`}
          >
            <Users className="w-3.5 h-3.5 text-[#8083ff]" /> People & Faces ({clusters.length})
          </button>

          <button
            onClick={() => {
              setActiveTab("all");
              setSelectedCluster(null);
            }}
            className={`text-xs font-bold pb-1 flex items-center gap-1.5 border-b-2 transition-all whitespace-nowrap ${
              activeTab === "all"
                ? "border-[#c0c1ff] text-[#c0c1ff]"
                : "border-transparent text-[#908fa0] hover:text-white"
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-[#dae2fd]" /> All Event Photos ({allPhotos.length})
          </button>
        </div>
      </div>

      {/* Main Gallery Container */}
      <div className="max-w-7xl mx-auto px-4 md:px-12 pt-8">
        {loading ? (
          <div className="py-20 text-center text-[#c7c4d7]">
            <Sparkles className="w-8 h-8 text-[#8083ff] animate-spin mx-auto mb-3" />
            <p>Loading gallery memories & people...</p>
          </div>
        ) : activeTab === "people" && !selectedCluster ? (
          /* --- GOOGLE PHOTOS STYLE PEOPLE & FACES GRID --- */
          <div className="flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[#131b2e]/60 p-4 rounded-2xl border border-white/10">
              <div>
                <h2 className="text-lg font-extrabold text-white flex items-center gap-2">
                  <Users className="w-5 h-5 text-[#8083ff]" /> Discovered People ({clusters.length})
                </h2>
                <p className="text-xs text-[#908fa0]">
                  AI automatically clusters and separates every attendee across group and individual photos.
                </p>
              </div>

              <div className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#908fa0]" />
                <input
                  type="text"
                  value={clusterSearchQuery}
                  onChange={(e) => setClusterSearchQuery(e.target.value)}
                  placeholder="Search person name..."
                  className="w-full bg-[#0b1326] border border-white/15 rounded-xl pl-9 pr-3 py-2 text-xs text-white focus:outline-none focus:border-[#c0c1ff] transition-colors"
                />
              </div>
            </div>

            {filteredClusters.length === 0 ? (
              <div className="py-16 text-center glass-panel rounded-3xl p-8 border border-white/10 max-w-md mx-auto">
                <Users className="w-12 h-12 text-[#908fa0] mx-auto mb-3" />
                <h3 className="text-base font-bold text-white mb-1">No People Clusters Found</h3>
                <p className="text-xs text-[#c7c4d7] mb-4">
                  {clusterSearchQuery ? "No discovered person matches your search." : "No facial clusters have been indexed yet for this event."}
                </p>
                <button
                  onClick={() => setActiveTab("all")}
                  className="bg-white/10 hover:bg-white/15 text-white font-bold text-xs px-4 py-2.5 rounded-xl transition-colors border border-white/10"
                >
                  Browse Full Event Gallery
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                {filteredClusters.map((cluster) => {
                  const thumb = getFullImageUrl(cluster.thumbnail_url || (cluster.photos[0]?.image_url ?? ""));
                  return (
                    <div
                      key={cluster.cluster_id}
                      onClick={() => setSelectedCluster(cluster)}
                      className="glass-panel p-4 rounded-3xl border border-white/10 hover:border-[#c0c1ff]/60 hover:shadow-[0_0_30px_rgba(192,193,255,0.2)] transition-all duration-300 flex flex-col items-center text-center cursor-pointer group hover:-translate-y-1"
                    >
                      {/* Avatar Bubble */}
                      <div className="relative w-24 h-24 sm:w-28 sm:h-28 rounded-full overflow-hidden mb-3 border-2 border-[#c0c1ff]/40 group-hover:border-[#c0c1ff] group-hover:scale-105 transition-all shadow-lg bg-[#131b2e]">
                        {thumb ? (
                          <img
                            src={thumb}
                            alt={cluster.name}
                            className="w-full h-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-[#908fa0]">
                            <User className="w-10 h-10" />
                          </div>
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>

                      {/* Name & Photo Count */}
                      <h4 className="text-sm font-bold text-white group-hover:text-[#c0c1ff] transition-colors truncate max-w-full">
                        {cluster.name}
                      </h4>
                      <span className="text-[11px] font-semibold text-[#7bd0ff] bg-[#8083ff]/15 px-2.5 py-0.5 rounded-full mt-1 border border-[#c0c1ff]/20">
                        {cluster.photo_count} {cluster.photo_count === 1 ? "photo" : "photos"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : activeTab === "selfie" && matches.length === 0 ? (
          <div className="py-20 text-center glass-panel rounded-3xl p-8 border border-white/10 max-w-md mx-auto">
            <Search className="w-16 h-16 text-[#ffb4ab] mx-auto mb-4 opacity-80" />
            <h3 className="text-xl font-bold text-white mb-2">Face or Image Not Found</h3>
            <p className="text-sm text-[#c7c4d7] mb-6">
              We couldn't find a matching face in this event. Please ensure your selfie is well-lit and try again.
            </p>
            <button
              onClick={() => router.push(`/event/${encodeURIComponent(eventCode)}`)}
              className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-sm px-6 py-3 rounded-xl shadow-[0_0_20px_rgba(192,193,255,0.3)] hover:opacity-95 transition-all"
            >
              Take New Selfie
            </button>
          </div>
        ) : (
          <PhotoMasonry
            matches={currentDisplayList}
            onSelectPhoto={(photo) => {
              if (isSelectMode) {
                togglePhotoSelection(photo.image_url);
              } else {
                setSelectedPhoto(photo);
              }
            }}
            isSelectMode={isSelectMode}
            selectedPhotoUrls={selectedPhotoUrls}
            onToggleSelect={(url) => togglePhotoSelection(url)}
            onSwitchToAllPhotos={() => setActiveTab("all")}
            onRetakeSelfie={() => router.push(`/event/${encodeURIComponent(eventCode)}`)}
            totalGalleryCount={allPhotos.length}
          />
        )}
      </div>

      {/* Share Link Modal */}
      {shareModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
          <div className="glass-panel rounded-3xl p-6 sm:p-8 max-w-md w-full border border-white/15 shadow-2xl relative flex flex-col gap-4">
            <div className="flex justify-between items-center pb-3 border-b border-white/10">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-[#8083ff]/20 text-[#c0c1ff] flex items-center justify-center">
                  <Share2 className="w-4 h-4 text-[#7bd0ff]" />
                </div>
                <h3 className="text-base font-bold text-white">Private Share Link</h3>
              </div>
              <button
                onClick={() => setShareModalOpen(false)}
                className="p-1.5 text-[#908fa0] hover:text-white rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs text-[#c7c4d7]">
              Share this secure temporary link with friends or family. It gives direct access to these {matches.length} photos without requiring login or exposing biometric vector data.
            </p>

            <div>
              <label className="text-[11px] font-semibold text-[#908fa0] mb-1 block">Expiration Window</label>
              <div className="flex gap-2">
                {[24, 48, 168].map((h) => (
                  <button
                    key={h}
                    onClick={() => setExpiryHours(h)}
                    className={`flex-1 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                      expiryHours === h
                        ? "bg-[#c0c1ff] text-[#1000a9] border-[#c0c1ff]"
                        : "bg-[#131b2e] text-[#dae2fd] border-white/10 hover:border-white/20"
                    }`}
                  >
                    {h === 24 ? "24 Hours" : h === 48 ? "48 Hours" : "7 Days"}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 bg-[#131b2e] p-2.5 rounded-xl border border-white/15">
              <input
                type="text"
                readOnly
                value={generatedShareUrl}
                className="bg-transparent text-xs text-white flex-1 outline-none truncate font-mono"
              />
              <button
                onClick={copyShareLink}
                className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] text-xs font-bold px-3 py-1.5 rounded-lg flex items-center gap-1 shrink-0 hover:opacity-90"
              >
                {shareCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {shareCopied ? "Copied" : "Copy"}
              </button>
            </div>

            <a
              href={generatedShareUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[#7bd0ff] hover:underline flex items-center justify-center gap-1 pt-1"
            >
              Open Link in New Tab <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      )}

      {/* Lightbox Modal */}
      <LightboxModal photo={selectedPhoto} onClose={() => setSelectedPhoto(null)} />
    </div>
  );
}


