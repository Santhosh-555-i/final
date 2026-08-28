import ClientSharedGalleryPage from "./ClientSharedGalleryPage";

export function generateStaticParams() {
  return [{ token: "preview" }, { token: "demo" }];
}

export default function SharedGalleryPage() {
  return <ClientSharedGalleryPage />;
}
