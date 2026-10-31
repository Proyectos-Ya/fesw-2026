export function TenderCardSkeleton() {
  return (
    <div className="flex flex-col sm:flex-row gap-4 sm:gap-5 rounded-lg border border-border-subtle bg-surface-card p-4 sm:p-5 shadow-xs animate-pulse">
      <div className="size-[92px] flex-none rounded-full bg-surface-inset" />
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex gap-2">
          <div className="h-5 w-24 rounded-full bg-surface-inset" />
          <div className="h-5 w-28 rounded-full bg-surface-inset" />
        </div>
        <div className="h-5 w-3/4 rounded bg-surface-inset" />
        <div className="h-4 w-1/2 rounded bg-surface-inset" />
        <div className="mt-2 flex items-center gap-4">
          <div className="h-8 w-32 rounded bg-surface-inset" />
          <div className="flex-1" />
          <div className="h-9 w-32 rounded-md bg-surface-inset" />
        </div>
      </div>
    </div>
  );
}
