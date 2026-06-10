import { icons, type LucideProps } from "lucide-react";

type LucideName = keyof typeof icons;

const aliasMap: Record<string, LucideName> = {
  "building-2": "Building2",
  "check-circle-2": "CircleCheck",
  "circle-check": "CircleCheck",
  "map-pin": "MapPin",
  "file-text": "FileText",
  "shield-check": "ShieldCheck",
  "trending-up": "TrendingUp",
  "arrow-right": "ArrowRight",
  "arrow-left": "ArrowLeft",
};

function toPascal(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function resolveLucideName(name: string): LucideName | null {
  if (name in aliasMap) return aliasMap[name];
  const pascal = toPascal(name) as LucideName;
  return pascal in icons ? pascal : null;
}

interface IconProps extends Omit<LucideProps, "ref" | "name"> {
  name: string;
  size?: number;
}

export function Icon({
  name,
  size = 20,
  color = "currentColor",
  strokeWidth = 2,
  className = "",
  ...rest
}: IconProps) {
  const key = resolveLucideName(name);
  if (!key) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[Icon] Unknown lucide name: "${name}"`);
    }
    return null;
  }
  const LucideIcon = icons[key];
  return (
    <LucideIcon
      size={size}
      color={color}
      strokeWidth={strokeWidth}
      className={`flex-none ${className}`}
      {...rest}
    />
  );
}
