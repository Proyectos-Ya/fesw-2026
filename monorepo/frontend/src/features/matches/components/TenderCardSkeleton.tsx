export function TenderCardSkeleton() {
  return (
    <div className="flex gap-5 rounded-lg border border-border-subtle bg-surface-card p-5 shadow-xs animate-pulse">
      <div className="size-[92px] flex-none rounded-full bg-warm-100" />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex gap-2">
          <div className="h-5 w-24 rounded-full bg-warm-100" />
          <div className="h-5 w-28 rounded-full bg-warm-100" />
        </div>
        <div className="h-5 w-3/4 rounded bg-warm-100" />
        <div className="h-4 w-1/2 rounded bg-warm-100" />
        <div className="mt-2 flex items-center gap-4">
          <div className="h-8 w-32 rounded bg-warm-100" />
          <div className="flex-1" />
          <div className="h-9 w-32 rounded-md bg-warm-100" />
        </div>
      </div>
    </div>
  );
}
