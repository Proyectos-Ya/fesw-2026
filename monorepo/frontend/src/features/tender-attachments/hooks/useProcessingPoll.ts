import { useEffect, useRef } from "react";

export function useProcessingPoll(
  active: boolean,
  onTick: () => void,
  {
    intervalMs = 15_000,
    maxTicks = 40,
  }: { intervalMs?: number; maxTicks?: number } = {}
): void {
  const onTickRef = useRef(onTick);
  useEffect(() => {
    onTickRef.current = onTick;
  });

  useEffect(() => {
    if (!active) return;
    let ticks = 0;
    const id = setInterval(() => {
      ticks += 1;
      onTickRef.current();
      if (ticks >= maxTicks) clearInterval(id);
    }, intervalMs);
    return () => clearInterval(id);
  }, [active, intervalMs, maxTicks]);
}
