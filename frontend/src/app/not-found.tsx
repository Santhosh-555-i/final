"use client";

import React, { useEffect } from "react";
import Link from "next/link";

export default function NotFound() {
  useEffect(() => {
    if (typeof window !== "undefined") {
      const path = window.location.pathname;
      if (path.includes("/admin") && !path.endsWith("/")) {
        window.location.replace(path + "/");
      }
    }
  }, []);

  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center px-4">
      <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-2xl mb-4 shadow-lg">
        🔍
      </div>
      <h1 className="text-3xl font-bold text-white mb-2">Page Navigation</h1>
      <p className="text-slate-400 mb-6 max-w-md text-sm">
        Please select where you would like to go:
      </p>
      <div className="flex flex-wrap justify-center gap-3">
        <Link 
          href="/" 
          className="px-5 py-2.5 bg-gradient-to-r from-[#8083ff] to-[#6063e6] text-white rounded-xl text-sm font-semibold hover:opacity-90 shadow-md transition-all"
        >
          Attendee Home
        </Link>
        <Link 
          href="/admin" 
          className="px-5 py-2.5 bg-white/10 border border-white/15 text-white rounded-xl text-sm font-semibold hover:bg-white/20 transition-all"
        >
          Admin Portal
        </Link>
      </div>
    </div>
  );
}
