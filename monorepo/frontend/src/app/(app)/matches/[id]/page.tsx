import { TenderDetailView } from "@/features/matches/components/TenderDetailView";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function TenderDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <TenderDetailView tenderId={id} />;
}
