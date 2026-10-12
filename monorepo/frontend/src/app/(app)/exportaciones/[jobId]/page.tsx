import { ExportDownloadView } from "@/features/tender-export/components/ExportDownloadView";

interface PageProps {
  params: Promise<{ jobId: string }>;
}

export default async function ExportDownloadPage({ params }: PageProps) {
  const { jobId } = await params;
  return <ExportDownloadView jobId={jobId} />;
}
