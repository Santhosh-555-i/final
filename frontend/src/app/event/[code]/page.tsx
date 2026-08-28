import ClientEventSelfiePage from "./ClientEventSelfiePage";

export function generateStaticParams() {
  return [
    { code: "TECH-CONF-2026" },
    { code: "DEMO" },
    { code: "EVENT" },
  ];
}

export default function EventSelfiePage() {
  return <ClientEventSelfiePage />;
}
