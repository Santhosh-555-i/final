import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";

export const metadata: Metadata = {
  title: "EventLens - AI Photo Retrieval & Matching",
  description: "Find your high-res event photos instantly using privacy-first AI face recognition.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body 
        className="antialiased bg-[#0b1326] text-[#dae2fd] min-h-screen flex flex-col selection:bg-[#8083ff] selection:text-white"
        suppressHydrationWarning
      >
        <Navbar />
        <main className="flex-1 pt-16" suppressHydrationWarning>{children}</main>
        <footer className="py-6 border-t border-white/10 text-center text-xs text-[#908fa0] bg-[#060e20]" suppressHydrationWarning>
          EventLens AI &copy; 2026 &bull; Privacy-Preserving Facial Embedding Search
        </footer>
      </body>
    </html>
  );
}
