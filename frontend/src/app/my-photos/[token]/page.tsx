"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { 
  Download, Sparkles, Image as ImageIcon, ShieldCheck, 
  Clock, Lock, CheckSquare, Check, ArrowLeft, RefreshCw,
  AlertCircle, Shield, Share2, ExternalLink
} from "lucide-react";
import { 
  getSharedGalleryPhotos, downloadPhotosZip, getFullImageUrl,
  SharedGalleryData, PhotoData, MatchResult 
} from "@/lib/api";
import { PhotoMasonry } from "@/components/PhotoMasonry";
import { LightboxModal } from "@/components/LightboxModal";
import confetti from "canvas-confetti";

export default function SharedGalleryPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;

  const [galleryData, setGalleryData] = useState<SharedGalleryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedPhoto, setSelectedPhoto] = useState<MatchResult | null>(null);
  const [isZipping, setIsZipping] = useState(false);

  // Multi-select state
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedPhotoUrls, setSelectedPhotoUrls] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function loadSharedPhotos() {
      try {
        const data = await getSharedGalleryPhotos(token);
        setGalleryData(data);
        if (data.photos && data.photos.length > 0) {
          confetti({
            particleCount: 60,
            spread: 60,
            origin: { y: 0.6 },
            colors: ["#c0c1ff", "#8083ff", "#7bd0ff"],
          });
        }
      } catch (err: any) {
        setError(err.message || "This sharing link is invalid or has expired.");
      } finally {
        setLoading(false);
      }
    }
    if (token) {
      loadSharedPhotos();
    }
  }, [token]);

  // Download All Shared Photos (.ZIP)
  const handleDownloadAllZip = async () => {
    if (!galleryData || galleryData.photos.length === 0) return;
    setIsZipping(true);
    try {
      const urls = galleryData.photos.map((p) => getFullImageUrl(p.image_url));
      await downloadPhotosZip(urls);
    } catch (err) {
      console.error("ZIP Download error:", err);
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
      console.error("Selected ZIP error:", err);
    } finally {
      setIsZipping(false);
    }
  };

  // Format expiration timestamp
  const formatExpiryTime = (isoString?: string) => {
    if (!isoString) return "";
    const expiry = new Date(isoString);
    const now = new Date();
    const diffHours = Math.round((expiry.getTime() - now.getTime()) / (1000 * 60 * 60));
    if (diffHours <= 0) return "Expiring soon";
    if (diffHours < 24) return `Expires in ${diffHours} hours`;
    const diffDays = Math.round(diffHours / 24);
    return `Expires in ${diffDays} days`;
  };

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center p-4">
        <RefreshCw className="w-10 h-10 text-[#8083ff] animate-spin mb-4" />
        <h3 className="text-lg font-bold text-white">Decrypting Secure Share Link...</h3>
        <p className="text-xs text-[#908fa0] mt-1">Verifying cryptographic authorization token</p>
      </div>
    );
  }

  if (error || !galleryData) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center p-4">
        <div className="glass-panel rounded-3xl p-8 max-w-md w-full border border-white/10 text-center shadow-2xl">
          <div className="w-16 h-16 rounded-2xl bg-[#93000a]/30 text-[#ffdad6] flex items-center justify-center mx-auto mb-4 border border-[#ffb4ab]/30">
            <Lock className="w-8 h-8 text-[#ffb4ab]" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Access Link Expired</h2>
          <p className="text-xs text-[#c7c4d7] mb-6">
            {error || "This temporary sharing link has expired or has been revoked by the event host."}
          </p>
          <button
            onClick={() => router.push("/")}
            className="w-full bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-bold text-sm py-3 rounded-xl hover:opacity-95 transition-all shadow-[0_0_20px_rgba(192,193,255,0.3)]"
          >
            Return to Home
          </button>
        </div>
      </div>
    );
  }

  // Convert photos to match result format
  const photosAsMatches: MatchResult[] = galleryData.photos.map((p) => ({
    photo_id: p.id,
    image_url: p.image_url,
    thumbnail_url: p.thumbnail_url,
    similarity: 1.0,
  }));

  return (
    <div className="min-h-[calc(100vh-4rem)] pb-16">
      {/* Sticky Header Banner */}
      <div className="sticky top-16 z-40 bg-[#0b1326]/90 backdrop-blur-xl border-b border-white/10 shadow-lg px-4 md:px-12 py-4">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center gap-1 bg-[#8083ff]/15 text-[#c0c1ff] border border-[#c0c1ff]/30 px-2.5 py-0.5 rounded-full text-[11px] font-bold">
                <ShieldCheck className="w-3 h-3 text-[#7bd0ff]" /> Private Shared Gallery
              </span>
              <span className="text-xs text-[#908fa0]">&bull;</span>
              <span className="text-xs text-[#7bd0ff] font-semibold">{galleryData.event_title}</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#c0c1ff]" />
              Your Private Memories ({galleryData.photos.length} {galleryData.photos.length === 1 ? "photo" : "photos"})
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
            {/* Expiry Badge */}
            <div className="flex items-center gap-1.5 bg-[#131b2e] px-3 py-2 rounded-xl border border-white/10 text-xs text-[#c7c4d7]">
              <Clock className="w-3.5 h-3.5 text-[#7bd0ff]" />
              <span>{formatExpiryTime(galleryData.expires_at)}</span>
            </div>

            {/* Multi-Select Toggle */}
            <button
              onClick={() => {
                setIsSelectMode(!isSelectMode);
                setSelectedPhotoUrls(new Set());
              }}
              className={`text-xs font-semibold px-3.5 py-2 rounded-xl border transition-colors flex items-center gap-1.5 ${
                isSelectMode
                  ? "bg-[#c0c1ff] text-[#1000a9] border-[#c0c1ff]"
                  : "bg-white/5 hover:bg-white/10 text-[#dae2fd] border-white/10"
              }`}
            >
              <CheckSquare className="w-4 h-4" />
              {isSelectMode ? "Cancel Select" : "Select Photos"}
            </button>

            {isSelectMode && selectedPhotoUrls.size > 0 && (
              <button
                onClick={handleDownloadSelectedZip}
                disabled={isZipping}
                className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] flex items-center gap-1.5"
              >
                <Download className="w-4 h-4" />
                Download ({selectedPhotoUrls.size}) Selected
              </button>
            )}

            {!isSelectMode && galleryData.photos.length > 0 && (
              <button
                onClick={handleDownloadAllZip}
                disabled={isZipping}
                className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs px-4 py-2 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 flex items-center gap-1.5"
              >
                <Download className="w-4 h-4" />
                {isZipping ? "Zipping..." : "Download All Photos (.zip)"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Photo Gallery */}
      <div className="max-w-7xl mx-auto px-4 md:px-12 pt-8">
        <PhotoMasonry
          matches={photosAsMatches}
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
        />
      </div>

      {/* Privacy Notice Footer */}
      <div className="max-w-7xl mx-auto px-4 md:px-12 mt-12 text-center text-xs text-[#908fa0] flex items-center justify-center gap-2">
        <ShieldCheck className="w-4 h-4 text-[#7bd0ff]" />
        <span>This private link is protected and expires automatically. Zero biometric vector data is exposed.</span>
      </div>

      {/* Lightbox Modal */}
      <LightboxModal photo={selectedPhoto} onClose={() => setSelectedPhoto(null)} />
    </div>
  );
}
