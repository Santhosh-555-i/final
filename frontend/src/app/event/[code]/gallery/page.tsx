import { Suspense } from "react";
import ClientEventGalleryPage from "./ClientEventGalleryPage";

export default function GalleryPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center text-white">Loading Gallery...</div>}>
      <ClientEventGalleryPage />
    </Suspense>
  );
}
