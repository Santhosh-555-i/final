"use client";

import React, { useState } from "react";
import { X, Download, ExternalLink, Sparkles, CheckCircle2 } from "lucide-react";
import { MatchResult, getFullImageUrl } from "@/lib/api";

interface LightboxModalProps {
  photo: MatchResult | null;
  onClose: () => void;
}

export const LightboxModal: React.FC<LightboxModalProps> = ({ photo, onClose }) => {
  const [showHighlight, setShowHighlight] = useState(true);
  if (!photo) return null;

  const fullUrl = getFullImageUrl(photo.image_url);
  const similarityPct = Math.round(photo.similarity * 100);

  const handleDownload = async () => {
    try {
      const resp = await fetch(fullUrl);
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `EventLens_Photo_${photo.photo_id.slice(0, 8)}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      window.open(fullUrl, "_blank");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-2xl transition-opacity animate-in fade-in">
      <div className="relative w-full max-w-5xl max-h-[92vh] flex flex-col glass-modal rounded-3xl overflow-hidden border border-white/10 shadow-[0_0_80px_rgba(0,0,0,0.8)]">
        {/* Header Bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#0b1326]/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 bg-[#8083ff]/20 text-[#c0c1ff] border border-[#c0c1ff]/30 px-3 py-1 rounded-full text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-[#7bd0ff]" />
              <span>{similarityPct}% Face Match</span>
            </div>
            <span className="text-xs text-[#908fa0] hidden sm:inline">
              Photo ID: {photo.photo_id.slice(0, 8)}...
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-bold text-xs px-4 py-2 rounded-xl hover:opacity-90 transition-opacity shadow-[0_0_15px_rgba(192,193,255,0.3)] active:scale-95"
            >
              <Download className="w-4 h-4" /> Download Photo
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-[#c7c4d7] hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Full Image Container */}
        <div className="relative flex-1 bg-[#060e20] flex items-center justify-center p-4 min-h-[400px] overflow-hidden">
          <div className="relative inline-block max-h-[75vh] max-w-full">
            <img
              src={fullUrl}
              alt="Matched event photo"
              className="max-h-[75vh] max-w-full object-contain rounded-xl shadow-2xl block"
            />

            {/* Bounding box highlight if present */}
            {showHighlight && photo.bounding_box && (
              <div
                className="absolute border-2 border-[#7bd0ff] rounded-lg shadow-[0_0_25px_rgba(123,208,255,0.8)] pointer-events-none transition-all animate-in fade-in"
                style={{
                  left: `${photo.bounding_box.x * 100}%`,
                  top: `${photo.bounding_box.y * 100}%`,
                  width: `${photo.bounding_box.width * 100}%`,
                  height: `${photo.bounding_box.height * 100}%`,
                }}
              >
                <div className="absolute -top-7 left-0 bg-gradient-to-r from-[#8083ff] to-[#7bd0ff] text-[#1000a9] text-[11px] font-extrabold px-2 py-0.5 rounded shadow-lg flex items-center gap-1 whitespace-nowrap">
                  <Sparkles className="w-3 h-3" />
                  <span>You ({similarityPct}%)</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer info */}
        <div className="px-6 py-3 bg-[#0b1326]/80 border-t border-white/10 flex items-center justify-between text-xs text-[#908fa0]">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-[#7bd0ff]">
              <CheckCircle2 className="w-4 h-4" /> High Resolution JPEG Original
            </div>
            {photo.bounding_box && (
              <button
                onClick={() => setShowHighlight(!showHighlight)}
                className={`text-xs px-2.5 py-1 rounded-lg border transition-all flex items-center gap-1 ${
                  showHighlight
                    ? "bg-[#8083ff]/20 text-[#c0c1ff] border-[#c0c1ff]/40"
                    : "bg-white/5 text-[#908fa0] border-white/10 hover:text-white"
                }`}
              >
                <Sparkles className="w-3 h-3" />
                {showHighlight ? "Highlight Active (In Group)" : "Show Face Highlight"}
              </button>
            )}
          </div>
          <button
            onClick={() => window.open(fullUrl, "_blank")}
            className="hover:text-white flex items-center gap-1 transition-colors"
          >
            Open Original <ExternalLink className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
};
