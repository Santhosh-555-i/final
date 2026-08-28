"use client";

import React, { useEffect, useState } from "react";
import { Cpu, Sparkles, ShieldCheck } from "lucide-react";

interface AiScanningOverlayProps {
  isScanning: boolean;
  selfiePreviewUrl?: string | null;
}

const SCAN_STEPS = [
  "Normalizing selfie illumination & contrast (CLAHE + Adaptive Gamma)...",
  "Deep neural facial landmark detection (YuNet Engine)...",
  "Extracting 512-d VGGFace2 deep vector embedding...",
  "Executing vectorized sub-millisecond search across event & group photos...",
  "Isolating attendee matches in portraits and crowd shots...",
  "Loading your personalized high-resolution gallery..."
];

export const AiScanningOverlay: React.FC<AiScanningOverlayProps> = ({
  isScanning,
  selfiePreviewUrl,
}) => {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  useEffect(() => {
    if (!isScanning) {
      setCurrentStepIndex(0);
      return;
    }

    const interval = setInterval(() => {
      setCurrentStepIndex((prev) => (prev + 1) % SCAN_STEPS.length);
    }, 450);

    return () => clearInterval(interval);
  }, [isScanning]);

  if (!isScanning) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#060e20]/90 backdrop-blur-xl transition-all" suppressHydrationWarning>
      <div className="relative w-full max-w-lg glass-modal rounded-3xl p-8 border border-[#c0c1ff]/30 text-center shadow-[0_0_80px_rgba(192,193,255,0.25)] flex flex-col items-center" suppressHydrationWarning>
        {/* Animated Header Badge */}
        <div className="inline-flex items-center gap-2 bg-[#8083ff]/20 text-[#c0c1ff] border border-[#c0c1ff]/40 px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider mb-6 animate-pulse" suppressHydrationWarning>
          <Sparkles className="w-4 h-4 text-[#7bd0ff]" />
          <span>AI Vector Matching Active</span>
        </div>

        {/* Central Scan Frame */}
        <div className="relative w-56 h-56 rounded-full overflow-hidden border-2 border-[#c0c1ff] shadow-[0_0_50px_rgba(192,193,255,0.3)] mb-6 bg-[#131b2e]">
          {selfiePreviewUrl ? (
            <img
              src={selfiePreviewUrl}
              alt="Selfie scan target"
              className="w-full h-full object-cover filter brightness-90 contrast-105"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[#908fa0]">
              <Cpu className="w-16 h-16 animate-spin" />
            </div>
          )}

          {/* Mesh Grid Overlay */}
          <div className="absolute inset-0 mesh-grid opacity-60 pointer-events-none" />

          {/* Laser Scanning Line */}
          <div className="scan-line" />

          {/* Target Reticle / Pulse Ring */}
          <div className="absolute inset-4 rounded-full border border-dashed border-[#7bd0ff]/60 pulse-ring pointer-events-none" />
        </div>

        {/* Dynamic Status Text */}
        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-[#7bd0ff] animate-pulse" />
          <span>Analyzing Selfie</span>
        </h3>

        <p className="text-sm font-medium text-[#c0c1ff] h-8 transition-all duration-300 flex items-center justify-center">
          {SCAN_STEPS[currentStepIndex]}
        </p>

        {/* Progress Bar Beam */}
        <div className="w-full bg-[#131b2e] h-2 rounded-full overflow-hidden mt-4 border border-white/10 relative">
          <div className="h-full bg-gradient-to-r from-[#8083ff] via-[#7bd0ff] to-[#c0c1ff] rounded-full animate-pulse transition-all duration-300 w-full" />
        </div>

        <div className="mt-6 flex items-center gap-2 text-xs text-[#7bd0ff] opacity-80">
          <ShieldCheck className="w-4 h-4" />
          <span>Zero-Storage Guarantee: Selfie is processed strictly in-memory and discarded.</span>
        </div>
      </div>
    </div>
  );
};
