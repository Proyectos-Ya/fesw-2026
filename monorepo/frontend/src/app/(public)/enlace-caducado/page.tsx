import type { Metadata } from "next";

import { ExpiredLinkNotice } from "@/features/tender-sharing/components/ExpiredLinkNotice";
import type { ExpiredReason } from "@/features/tender-sharing/types";

export const metadata: Metadata = {
  title: "Chiripa - Enlace caducado",
  robots: { index: false, follow: false },
};

interface PageProps {
  searchParams: Promise<{ motivo?: string }>;
}

export default async function ExpiredLinkPage({ searchParams }: PageProps) {
  const { motivo } = await searchParams;
  const reason: ExpiredReason | null =
    motivo === "caducado" || motivo === "revocado" ? motivo : null;
  return <ExpiredLinkNotice reason={reason} />;
}
