import { TenderDetailView } from "@/features/matches/components/TenderDetailView";
import { parseRankingContext } from "@/features/ranking-telemetry/utils/rankingLink";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function TenderDetailPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const query = await searchParams;
  // El ranking viaja en la URL desde las tarjetas del dashboard; desde búsqueda o
  // notificación no hay, y las interacciones se guardan sin atribuir.
  return <TenderDetailView tenderId={id} rankingContext={parseRankingContext(query.r, query.p)} />;
}
