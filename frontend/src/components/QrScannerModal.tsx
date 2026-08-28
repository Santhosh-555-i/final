"use client";

import React, { useEffect, useRef, useState } from "react";
import { X, QrCode, Camera } from "lucide-react";

interface QrScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onScanSuccess: (code: string) => void;
}

export const QrScannerModal: React.FC<QrScannerModalProps> = ({
  isOpen,
  onClose,
  onScanSuccess,
}) => {
  const [scannerActive, setScannerActive] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const scannerRef = useRef<any>(null);

  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    let html5QrcodeScanner: any = null;

    const startScanner = async () => {
      try {
        const { Html5QrcodeScanner } = await import("html5-qrcode");
        if (!isMounted) return;

        html5QrcodeScanner = new Html5QrcodeScanner(
          "qr-reader-element",
          { fps: 10, qrbox: { width: 220, height: 220 } },
          /* verbose= */ false
        );

        html5QrcodeScanner.render(
          (decodedText: string) => {
            if (decodedText) {
              // Extract code if text is a URL or raw code
              let code = decodedText.trim();
              if (code.includes("/event/")) {
                const parts = code.split("/event/");
                code = parts[parts.length - 1].split("/")[0];
              }
              onScanSuccess(code);
              if (html5QrcodeScanner) {
                html5QrcodeScanner.clear().catch(console.error);
              }
            }
          },
          (error: any) => {
            // Ignore scan errors while actively searching
          }
        );

        scannerRef.current = html5QrcodeScanner;
        setScannerActive(true);
      } catch (err: any) {
        console.error("QR Scanner Init Error:", err);
        setErrorMessage("Camera access restricted. Enter event code manually.");
      }
    };

    startScanner();

    return () => {
      isMounted = false;
      if (scannerRef.current) {
        scannerRef.current.clear().catch(console.error);
      }
    };
  }, [isOpen, onScanSuccess]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-md glass-modal rounded-2xl p-6 border border-[#c0c1ff]/30 shadow-[0_0_50px_rgba(192,193,255,0.2)]">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#c7c4d7] hover:text-white p-2 rounded-full bg-white/5 hover:bg-white/10 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center mb-5">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-[#c0c1ff]/10 text-[#c0c1ff] mb-3 border border-[#c0c1ff]/20">
            <QrCode className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white">Scan Event QR Code</h3>
          <p className="text-sm text-[#c7c4d7] mt-1">
            Point your camera at the event flyer or screen QR code
          </p>
        </div>

        <div className="relative overflow-hidden rounded-xl bg-[#060e20] border border-white/10 min-h-[260px] flex flex-col items-center justify-center">
          <div id="qr-reader-element" className="w-full text-white"></div>
          {errorMessage && (
            <div className="p-4 text-center text-xs text-[#ffb4ab]">
              {errorMessage}
            </div>
          )}
        </div>

        {/* Quick Demo Code selection buttons for instant trial */}
        <div className="mt-4 pt-3 border-t border-white/10 text-center">
          <p className="text-xs text-[#908fa0] mb-2">Quick Test Preset Codes:</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {["WEDDING2026", "TECHSUMMIT2026", "GALA2026"].map((preset) => (
              <button
                key={preset}
                onClick={() => onScanSuccess(preset)}
                className="text-xs bg-[#131b2e] hover:bg-[#8083ff]/30 text-[#c0c1ff] border border-[#c0c1ff]/30 px-3 py-1.5 rounded-lg transition-colors"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
