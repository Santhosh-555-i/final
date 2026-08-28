"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  Key, QrCode, ArrowRight, Lock, Unlock, Calendar, 
  MapPin, Sparkles, Image as ImageIcon, ShieldCheck, 
  Camera, Eye, Search, AlertCircle, RefreshCw, Layers
} from "lucide-react";
import { QrScannerModal } from "@/components/QrScannerModal";
import { listEvents, getEventByCode, verifyEventPassword, EventData, getFullImageUrl } from "@/lib/api";

export default function LandingPage() {
  const router = useRouter();
  
  // Mounted State to guarantee 100% hydration match with browser extensions
  const [mounted, setMounted] = useState(false);
  
  // Event Name / Code & Password Inputs
  const [eventNameOrCodeInput, setEventNameOrCodeInput] = useState("");
  const [eventPasswordInput, setEventPasswordInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  
  // QR Modal
  const [isQrModalOpen, setIsQrModalOpen] = useState(false);
  
  // Events Data from Backend
  const [events, setEvents] = useState<EventData[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [searchFilter, setSearchFilter] = useState("");
  const [fetchError, setFetchError] = useState("");

  const loadAllEvents = async () => {
    setLoadingEvents(true);
    setFetchError("");
    try {
      const data = await listEvents();
      setEvents(data && data.length > 0 ? data : []);
    } catch (err: any) {
      console.warn("Could not fetch events list:", err);
      setEvents([]);
    } finally {
      setLoadingEvents(false);
    }
  };

  useEffect(() => {
    setMounted(true);
    loadAllEvents();
  }, []);

  // Handle Direct Event Entry by Name or Code + Optional Password
  const handleEnterEvent = async (targetIdentifier?: string, targetDestination: "selfie" | "gallery" = "selfie") => {
    const rawIdentifier = (targetIdentifier || eventNameOrCodeInput).trim();
    if (!rawIdentifier) {
      setErrorMsg("Please enter an Event Name or Event Code");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg("");

    try {
      // 1. Resolve event by Name, Code, or ID
      const resolvedEvent = await getEventByCode(rawIdentifier);
      const actualCode = resolvedEvent.event_code || resolvedEvent.id;

      // 2. If event is protected and user entered a password
      if (resolvedEvent.is_protected) {
        if (eventPasswordInput.trim()) {
          try {
            await verifyEventPassword(actualCode, eventPasswordInput.trim());
            sessionStorage.setItem(`eventlens_unlocked_${actualCode}`, "true");
            sessionStorage.setItem(`eventlens_unlocked_${resolvedEvent.id}`, "true");
            sessionStorage.setItem(`eventlens_unlocked_${encodeURIComponent(actualCode)}`, "true");
          } catch (passErr: any) {
            setErrorMsg(passErr.message || "Incorrect event passcode. Please try again.");
            setIsSubmitting(false);
            return;
          }
        }
      }

      // 3. Navigate to target destination
      if (targetDestination === "gallery") {
        router.push(`/event/${encodeURIComponent(actualCode)}/gallery`);
      } else {
        router.push(`/event/${encodeURIComponent(actualCode)}`);
      }
    } catch (err: any) {
      setErrorMsg(`Event "${rawIdentifier}" not found. Please check the name or code.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Filtered Events List
  const filteredEvents = events.filter((ev) => {
    const q = searchFilter.toLowerCase().trim();
    if (!q) return true;
    return (
      ev.title.toLowerCase().includes(q) ||
      ev.event_code.toLowerCase().includes(q)
    );
  });

  if (!mounted) {
    return null;
  }

  return (
    <div className="relative min-h-[calc(100vh-4rem)] flex flex-col justify-between overflow-x-hidden" suppressHydrationWarning>
      {/* Background Ambient Glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden flex items-center justify-center -z-10" suppressHydrationWarning>
        <div className="w-[500px] h-[500px] bg-[#8083ff]/20 rounded-full blur-[140px] opacity-60 transform -translate-y-1/3" />
        <div className="w-[400px] h-[400px] bg-[#7bd0ff]/15 rounded-full blur-[120px] opacity-40 transform translate-x-1/3 translate-y-1/4" />
      </div>

      <div className="max-w-7xl mx-auto px-4 md:px-12 py-12 md:py-20 w-full" suppressHydrationWarning>
        {/* Hero Section */}
        <section className="flex flex-col items-center justify-center text-center max-w-4xl mx-auto mb-16" suppressHydrationWarning>
          <div className="inline-flex items-center gap-2 bg-[#8083ff]/15 text-[#c0c1ff] border border-[#c0c1ff]/30 px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider mb-8 shadow-[0_0_20px_rgba(192,193,255,0.2)]">
            <Sparkles className="w-4 h-4 text-[#7bd0ff]" />
            <span>AI-Powered Event Photo Search & Facial Recognition</span>
          </div>

          <h1 className="font-extrabold text-4xl sm:text-6xl md:text-7xl text-white tracking-tight mb-6 leading-tight text-glow">
            Find Your Event Memories <br className="hidden sm:inline" />
            <span className="gradient-text">in Seconds</span>
          </h1>

          <p className="text-lg md:text-xl text-[#c7c4d7] max-w-2xl mb-10 leading-relaxed font-normal">
            Type your event name or passcode to instantly see your photos, or take a quick selfie to discover all pictures featuring you.
          </p>

          {/* Unified Access Card */}
          <div className="w-full max-w-xl glass-panel p-6 sm:p-8 rounded-3xl border border-white/10 shadow-[0_0_50px_rgba(0,0,0,0.5)] flex flex-col gap-4" suppressHydrationWarning>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleEnterEvent(undefined, "selfie");
              }}
              className="flex flex-col gap-3"
              suppressHydrationWarning
            >
              {/* Event Name or Code Input */}
              <div className="relative flex items-center">
                <Layers className="absolute left-4 w-5 h-5 text-[#908fa0] transition-colors" />
                <input
                  type="text"
                  value={eventNameOrCodeInput}
                  onChange={(e) => setEventNameOrCodeInput(e.target.value)}
                  placeholder="Enter Event Name or Code (e.g. Wedding, Demo, SA)"
                  className="w-full bg-[#131b2e]/90 border border-white/15 rounded-2xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-[#c0c1ff] focus:ring-2 focus:ring-[#8083ff]/40 font-medium placeholder:text-[#908fa0]/70 transition-all text-sm sm:text-base tracking-wide"
                />
              </div>

              {/* Password Input (Optional / If protected) */}
              <div className="relative flex items-center">
                <Lock className="absolute left-4 w-5 h-5 text-[#908fa0] transition-colors" />
                <input
                  type="password"
                  value={eventPasswordInput}
                  onChange={(e) => setEventPasswordInput(e.target.value)}
                  placeholder="Event Password (Leave blank if public)"
                  className="w-full bg-[#131b2e]/90 border border-white/15 rounded-2xl py-3.5 pl-12 pr-4 text-white focus:outline-none focus:border-[#c0c1ff] focus:ring-2 focus:ring-[#8083ff]/40 font-medium placeholder:text-[#908fa0]/70 transition-all text-sm sm:text-base"
                />
              </div>

              {/* Action Buttons: Selfie AI vs Full Gallery */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] hover:opacity-95 font-bold py-3 px-4 rounded-xl text-xs sm:text-sm transition-all shadow-[0_0_20px_rgba(192,193,255,0.3)] active:scale-98 flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Camera className="w-4 h-4" />
                  {isSubmitting ? "Finding Event..." : "Selfie Face Match"}
                </button>

                <button
                  type="button"
                  onClick={() => handleEnterEvent(undefined, "gallery")}
                  disabled={isSubmitting}
                  className="w-full bg-white/10 hover:bg-white/15 text-white font-bold py-3 px-4 rounded-xl text-xs sm:text-sm transition-all border border-white/15 active:scale-98 flex items-center justify-center gap-2 cursor-pointer"
                >
                  <Eye className="w-4 h-4 text-[#7bd0ff]" />
                  View All Photos
                </button>
              </div>
            </form>

            {errorMsg && (
              <div className="p-3 rounded-xl bg-[#93000a]/20 border border-[#ffb4ab]/30 text-[#ffdad6] text-xs font-semibold flex items-center gap-2 text-left">
                <AlertCircle className="w-4 h-4 text-[#ffb4ab] shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="flex items-center gap-3 my-1">
              <div className="flex-grow h-px bg-white/10" />
              <span className="text-xs font-semibold text-[#908fa0] uppercase tracking-wider">OR</span>
              <div className="flex-grow h-px bg-white/10" />
            </div>

            <button
              onClick={() => setIsQrModalOpen(true)}
              className="w-full bg-[#171f33] hover:bg-[#222a3d] text-white py-3.5 rounded-2xl font-bold text-sm flex items-center justify-center gap-3 border border-white/15 hover:border-[#c0c1ff]/40 transition-all shadow-lg active:scale-98 cursor-pointer"
            >
              <QrCode className="w-5 h-5 text-[#7bd0ff]" />
              Scan Event QR Code
            </button>
          </div>
        </section>

        {/* Live Available Galleries Section */}
        <section className="mt-8">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold text-white mb-1 flex items-center gap-2">
                <ImageIcon className="w-6 h-6 text-[#7bd0ff]" /> Available Event Galleries ({events.length})
              </h2>
              <p className="text-xs sm:text-sm text-[#c7c4d7]">
                Real-time synchronized galleries across all your phones, laptops, and devices.
              </p>
            </div>

            {/* Live Filter Input */}
            {events.length > 0 && (
              <div className="relative w-full sm:w-72">
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#908fa0]" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filter events by name or code..."
                  className="w-full bg-[#131b2e] border border-white/15 rounded-xl py-2 pl-9 pr-3 text-xs text-white placeholder:text-[#908fa0] focus:outline-none focus:border-[#c0c1ff]"
                />
              </div>
            )}
          </div>

          {fetchError && (
            <div className="mb-6 p-4 rounded-2xl bg-[#93000a]/20 border border-[#ffb4ab]/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs text-[#ffdad6]">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[#ffb4ab]" />
                <span>{fetchError}</span>
              </div>
              <button
                onClick={loadAllEvents}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white font-bold transition-colors"
              >
                Retry Connection
              </button>
            </div>
          )}

          {loadingEvents ? (
            <div className="py-20 text-center text-[#c7c4d7]">
              <RefreshCw className="w-8 h-8 text-[#8083ff] animate-spin mx-auto mb-3" />
              <p className="text-sm font-semibold">Loading live event galleries...</p>
            </div>
          ) : filteredEvents.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredEvents.map((ev) => (
                <div
                  key={ev.id}
                  className="glass-panel rounded-2xl overflow-hidden group border border-white/10 hover:border-[#c0c1ff]/50 transition-all duration-300 hover:-translate-y-1.5 shadow-xl flex flex-col justify-between"
                >
                  <div 
                    onClick={() => handleEnterEvent(ev.event_code, "selfie")}
                    className="h-44 bg-[#131b2e] relative overflow-hidden flex items-center justify-center cursor-pointer"
                  >
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0b1326] via-transparent to-transparent z-10 opacity-90" />
                    <ImageIcon className="w-12 h-12 text-[#8083ff]/40 group-hover:scale-110 transition-transform duration-500" />
                    
                    <div className="absolute top-3 right-3 z-20 bg-[#131b2e]/90 backdrop-blur-md px-3 py-1 rounded-full border border-white/10 text-xs font-semibold flex items-center gap-1.5 shadow">
                      {ev.is_protected ? (
                        <>
                          <Lock className="w-3 h-3 text-[#ffb4ab]" />
                          <span className="text-[#ffdad6] font-mono">{ev.event_code}</span>
                        </>
                      ) : (
                        <>
                          <Unlock className="w-3 h-3 text-[#7bd0ff]" />
                          <span className="text-[#7bd0ff] font-mono">{ev.event_code}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="p-6 relative z-20 flex-1 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <h3 
                          onClick={() => handleEnterEvent(ev.event_code, "selfie")}
                          className="text-lg sm:text-xl font-bold text-white group-hover:text-[#c0c1ff] transition-colors truncate cursor-pointer"
                        >
                          {ev.title}
                        </h3>
                        {ev.is_protected && (
                          <span className="text-[10px] uppercase font-bold bg-[#ffb4ab]/15 text-[#ffb4ab] px-2 py-0.5 rounded shrink-0 border border-[#ffb4ab]/20">
                            Protected
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-4 text-xs text-[#c7c4d7] mb-5">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-[#7bd0ff]" /> {ev.created_at ? ev.created_at.slice(0, 10) : "2026"}
                        </span>
                        <span className="flex items-center gap-1 text-[#c0c1ff] font-semibold">
                          <ImageIcon className="w-3.5 h-3.5" /> {ev.photo_count || 0} Photos
                        </span>
                      </div>
                    </div>

                    {/* Dual Action Options per Event Card */}
                    <div className="grid grid-cols-2 gap-2 pt-3 border-t border-white/10">
                      <button
                        onClick={() => handleEnterEvent(ev.event_code, "selfie")}
                        className="bg-[#8083ff]/20 hover:bg-[#8083ff]/30 text-[#c0c1ff] font-bold text-xs py-2 px-3 rounded-xl border border-[#c0c1ff]/30 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Camera className="w-3.5 h-3.5" /> Selfie Match
                      </button>

                      <button
                        onClick={() => handleEnterEvent(ev.event_code, "gallery")}
                        className="bg-white/5 hover:bg-white/10 text-white font-bold text-xs py-2 px-3 rounded-xl border border-white/10 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5 text-[#7bd0ff]" /> Gallery
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-16 px-6 rounded-3xl bg-[#131b2e]/60 border border-white/10 text-center flex flex-col items-center max-w-lg mx-auto">
              <div className="w-14 h-14 rounded-2xl bg-[#8083ff]/15 text-[#c0c1ff] flex items-center justify-center mb-3">
                <ImageIcon className="w-7 h-7 text-[#7bd0ff]" />
              </div>
              <h4 className="text-base font-bold text-white mb-1">
                {searchFilter ? `No events matching "${searchFilter}"` : "No Events Created Yet"}
              </h4>
              <p className="text-xs text-[#908fa0] mb-4">
                {searchFilter
                  ? "Try searching for a different event name or clear the filter."
                  : "Create an event and upload photos in the Admin Dashboard to see them live here."}
              </p>
              {!searchFilter && (
                <a
                  href="/admin"
                  className="bg-gradient-to-r from-[#8083ff] to-[#c0c1ff] text-[#1000a9] font-bold text-xs px-4 py-2.5 rounded-xl hover:opacity-95 transition-opacity"
                >
                  Go to Admin Dashboard
                </a>
              )}
            </div>
          )}
        </section>
      </div>

      {/* QR Code Scanner Modal */}
      <QrScannerModal
        isOpen={isQrModalOpen}
        onClose={() => setIsQrModalOpen(false)}
        onScanSuccess={(code) => {
          setIsQrModalOpen(false);
          handleEnterEvent(code, "selfie");
        }}
      />
    </div>
  );
}
