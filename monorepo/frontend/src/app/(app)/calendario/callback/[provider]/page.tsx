import { notFound } from "next/navigation";

import { CalendarOAuthCallback } from "@/features/tender-milestones/components/CalendarOAuthCallback";
import { CALENDAR_PROVIDERS, type CalendarProvider } from "@/features/tender-milestones/types";

interface PageProps {
  params: Promise<{ provider: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function single(value: string | string[] | undefined): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function isProvider(value: string): value is CalendarProvider {
  return (CALENDAR_PROVIDERS as readonly string[]).includes(value);
}

export default async function CalendarCallbackPage({ params, searchParams }: PageProps) {
  const { provider } = await params;
  if (!isProvider(provider)) notFound();
  const query = await searchParams;
  return (
    <CalendarOAuthCallback
      provider={provider}
      code={single(query.code)}
      state={single(query.state)}
      error={single(query.error)}
    />
  );
}
