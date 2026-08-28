"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Camera, Lock, Scan, ShieldCheck, UserCircle, LayoutDashboard, Shield } from "lucide-react";

export const Navbar: React.FC = () => {
  const [adminEmail, setAdminEmail] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const email = sessionStorage.getItem("eventlens_admin_email");
    if (email) {
      setAdminEmail(email);
    }
  }, []);

  return (
    <header className="fixed top-0 w-full z-50 flex justify-between items-center px-4 md:px-12 h-16 bg-[#0b1326]/80 backdrop-blur-xl border-b border-white/10 shadow-sm" suppressHydrationWarning>
      <Link href="/" className="flex items-center gap-2.5 group" suppressHydrationWarning>
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#8083ff] to-[#c0c1ff] flex items-center justify-center shadow-[0_0_15px_rgba(192,193,255,0.4)] group-hover:scale-105 transition-transform" suppressHydrationWarning>
          <Camera className="w-5 h-5 text-[#1000a9]" />
        </div>
        <span className="font-bold text-xl md:text-2xl text-[#c0c1ff] tracking-tight group-hover:text-white transition-colors">
          EventLens
        </span>
      </Link>

      <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-[#c7c4d7]" suppressHydrationWarning>
        <Link href="/" className="hover:text-[#c0c1ff] transition-colors flex items-center gap-2">
          <Scan className="w-4 h-4 text-[#7bd0ff]" /> Event Access
        </Link>
        <Link href="/admin" className="hover:text-[#c0c1ff] transition-colors flex items-center gap-2">
          <LayoutDashboard className="w-4 h-4 text-[#c0c1ff]" /> Admin Portal
        </Link>
        <span className="hover:text-[#c0c1ff] cursor-pointer transition-colors flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#ffafd3]" /> Zero-Storage Privacy
        </span>
      </nav>

      <div className="flex items-center gap-3" suppressHydrationWarning>
        <div className="flex items-center gap-1.5 bg-[#131b2e] px-3 py-1.5 rounded-full border border-white/10 text-xs font-semibold text-[#7bd0ff]" suppressHydrationWarning>
          <Lock className="w-3.5 h-3.5" />
          <span>Encrypted</span>
        </div>
        {mounted && (
          <Link
            href="/admin"
            className={`text-xs font-medium px-3.5 py-1.5 rounded-lg border transition-colors hidden sm:flex items-center gap-1.5 ${
              adminEmail 
                ? "bg-[#8083ff]/15 text-[#c0c1ff] border-[#c0c1ff]/30 hover:bg-[#8083ff]/25" 
                : "bg-white/5 hover:bg-white/10 text-[#dae2fd] border-white/10"
            }`}
            suppressHydrationWarning
          >
            {adminEmail ? (
              <>
                <Shield className="w-3.5 h-3.5 text-[#7bd0ff]" />
                <span className="max-w-[150px] truncate">{adminEmail}</span>
              </>
            ) : (
              <>
                <UserCircle className="w-4 h-4 text-[#c0c1ff]" /> Admin
              </>
            )}
          </Link>
        )}
      </div>
    </header>
  );
};
