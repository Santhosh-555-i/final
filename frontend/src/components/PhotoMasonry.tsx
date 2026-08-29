"use client";

import React, { useState } from "react";
import { Download, Maximize2, Sparkles, Check, CheckSquare, Square } from "lucide-react";
import { MatchResult, getFullImageUrl } from "@/lib/api";

interface PhotoMasonryProps {
  matches: MatchResult[];
  onSelectPhoto: (photo: MatchResult) => void;
  isSelectMode?: boolean;
  selectedPhotoUrls?: Set<string>;
  onToggleSelect?: (url: string) => void;
  onSwitchToAllPhotos?: () => void;
  onRetakeSelfie?: () => void;
  totalGalleryCount?: number;
}

export const PhotoMasonry: React.FC<PhotoMasonryProps> = ({ 
  matches, 
  onSelectPhoto,
  isSelectMode = false,
  selectedPhotoUrls = new Set(),
  onToggleSelect,
  onSwitchToAllPhotos,
  onRetakeSelfie,
  totalGalleryCount = 0
}) => {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Strict Unique Deduplication: Guarantees every photo is displayed only once
  const uniqueMatches = React.useMemo(() => {
    const seen = new Set<string>();
    const unique: MatchResult[] = [];
    for (const item of matches) {
      const key = (item.image_url || item.photo_id || "").toLowerCase().trim();
      if (!key || !seen.has(key)) {
        if (key) seen.add(key);
        unique.push(item);
      }
    }
    return unique;
  }, [matches]);

  if (uniqueMatches.length === 0) {
    return (
      <div className="w-full py-16 text-center glass-panel rounded-3xl p-8 border border-white/10 max-w-2xl mx-auto shadow-2xl animate-in fade-in">
        <div className="w-16 h-16 rounded-full bg-[#131b2e] flex items-center justify-center mx-auto mb-4 text-[#908fa0] border border-white/10">
          <Sparkles className="w-8 h-8 text-[#c0c1ff]" />
        </div>
        <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">
          Your Face is Not Clear or Your Photos Are Not Available
        </h3>
        <p className="text-sm text-[#c7c4d7] max-w-md mx-auto mb-6">
          We couldn't detect matching photos in this event. Please ensure your face is clearly visible with good lighting and retry your selfie, or explore the complete gallery below!
        </p>

        <div className="flex flex-wrap justify-center gap-3">
          {onSwitchToAllPhotos && (
            <button
              onClick={onSwitchToAllPhotos}
              className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-extrabold text-xs sm:text-sm px-6 py-3 rounded-xl hover:opacity-95 transition-opacity shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-95 cursor-pointer flex items-center gap-2"
            >
              Browse All Event Photos ({totalGalleryCount})
            </button>
          )}

          {onRetakeSelfie && (
            <button
              onClick={onRetakeSelfie}
              className="bg-white/10 hover:bg-white/15 text-white font-bold text-xs sm:text-sm px-5 py-3 rounded-xl transition-colors border border-white/10 cursor-pointer"
            >
              Retake Selfie
            </button>
          )}
        </div>
      </div>
    );
  }

  const handleQuickDownload = async (e: React.MouseEvent, photo: MatchResult) => {
    e.stopPropagation();
    const url = getFullImageUrl(photo.image_url);
    setDownloadingId(photo.photo_id);
    try {
      const resp = await fetch(url);
      const blob = await resp.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `EventPhoto_${photo.photo_id.slice(0, 8)}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch {
      window.open(url, "_blank");
    } finally {
      setTimeout(() => setDownloadingId(null), 1000);
    }
  };

  return (
    <div className="masonry w-full">
      {uniqueMatches.map((photo) => {
        const thumbUrl = getFullImageUrl(photo.thumbnail_url || photo.image_url);
        const simPct = Math.round(photo.similarity * 100);
        const isSelected = selectedPhotoUrls.has(photo.image_url);
        const isFromSelfieMatch = photo.similarity < 0.999;

        return (
          <div
            key={photo.photo_id}
            onClick={() => {
              if (isSelectMode && onToggleSelect) {
                onToggleSelect(photo.image_url);
              } else {
                onSelectPhoto(photo);
              }
            }}
            className={`masonry-item glass-panel rounded-2xl overflow-hidden group cursor-pointer border transition-all duration-300 hover:-translate-y-1.5 shadow-lg relative ${
              isSelected
                ? "border-[#c0c1ff] ring-2 ring-[#8083ff] shadow-[0_0_25px_rgba(192,193,255,0.3)]"
                : "border-white/10 hover:border-[#c0c1ff]/50 hover:shadow-[0_10px_30px_rgba(192,193,255,0.15)]"
            }`}
          >
            {/* Image Container */}
            <div className="relative w-full overflow-hidden bg-[#060e20]">
              <img
                src={thumbUrl}
                alt="Event memory"
                className={`w-full h-auto object-cover transition-transform duration-500 ${
                  isSelected ? "scale-105" : "group-hover:scale-105"
                }`}
                loading="lazy"
                decoding="async"
                onError={(e) => {
                  console.warn("[EventLens Diagnostic] Image failed to load:", {
                    photo_id: photo.photo_id,
                    requested_src: thumbUrl,
                    raw_image_url: photo.image_url,
                    raw_thumb_url: photo.thumbnail_url
                  });
                }}
              />

              {/* Gradient Overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-[#0b1326] via-transparent to-black/30 opacity-60 group-hover:opacity-80 transition-opacity" />

              {/* Select Mode Checkbox Overlay */}
              {isSelectMode && (
                <div 
                  onClick={(e) => {
                    e.stopPropagation();
                    if (onToggleSelect) onToggleSelect(photo.image_url);
                  }}
                  className="absolute top-3 right-3 z-30"
                >
                  <div className={`w-7 h-7 rounded-xl flex items-center justify-center transition-all ${
                    isSelected 
                      ? "bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] shadow-[0_0_15px_rgba(192,193,255,0.4)]" 
                      : "bg-black/60 backdrop-blur-md border border-white/30 text-transparent hover:border-white"
                  }`}>
                    <Check className="w-4 h-4 font-bold" />
                  </div>
                </div>
              )}

              {/* Match Confidence Badge */}
              {isFromSelfieMatch && (
                <div className="absolute top-3 left-3 bg-[#131b2e]/80 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/10 flex items-center gap-1.5 shadow z-20">
                  <Sparkles className="w-3.5 h-3.5 text-[#7bd0ff]" />
                  <span className="text-xs font-bold text-[#c0c1ff]">{simPct}% Match</span>
                </div>
              )}

              {/* Action Buttons Overlay */}
              {!isSelectMode && (
                <div className="absolute bottom-3 right-3 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all transform translate-y-2 group-hover:translate-y-0 z-20">
                  <button
                    onClick={(e) => handleQuickDownload(e, photo)}
                    className="p-2.5 rounded-xl bg-[#8083ff] text-[#1000a9] hover:bg-[#c0c1ff] transition-colors shadow-lg flex items-center justify-center"
                    title="Download High-Res Photo"
                  >
                    <Download className="w-4 h-4 font-bold" />
                  </button>
                  <button
                    onClick={() => onSelectPhoto(photo)}
                    className="p-2.5 rounded-xl bg-white/20 text-white backdrop-blur-md hover:bg-white/30 transition-colors shadow-lg"
                    title="Expand Full View"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

