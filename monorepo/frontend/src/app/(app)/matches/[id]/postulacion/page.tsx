import { ProposalView } from "@/features/proposals/components/ProposalView";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ProposalPage({ params }: PageProps) {
  const { id } = await params;
  return <ProposalView tenderId={id} />;
}
