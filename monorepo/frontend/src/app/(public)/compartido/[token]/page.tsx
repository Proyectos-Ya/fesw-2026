import type { Metadata } from "next";

import { SharedTenderView } from "@/features/tender-sharing/components/SharedTenderView";

export const metadata: Metadata = {
  title: "Chiripa - Licitación compartida",
  // La URL es la única llave: que no la indexen ni la filtre el Referer.
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

interface PageProps {
  params: Promise<{ token: string }>;
}

export default async function SharedTenderPage({ params }: PageProps) {
  const { token } = await params;
  return <SharedTenderView token={token} />;
}
