import { TenderAnalysisView } from "@/features/matches/components/TenderAnalysisView";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function TenderAnalysisPage({ params }: PageProps) {
  const { id } = await params;
  return <TenderAnalysisView tenderId={id} />;
}
