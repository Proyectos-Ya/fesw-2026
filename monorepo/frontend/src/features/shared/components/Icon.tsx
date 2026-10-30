import {
  ArrowLeft,
  ArrowRight,
  Bell,
  BookOpen,
  Bookmark,
  BookmarkCheck,
  Building2,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  Clock,
  Copy,
  Download,
  ExternalLink,
  FilePlus,
  FileSpreadsheet,
  FileText,
  Flag,
  Gauge,
  Info,
  Kanban,
  Lightbulb,
  Link,
  Link2Off,
  LoaderCircle,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Menu,
  MessageCircle,
  MessageSquare,
  OctagonAlert,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Search,
  Settings,
  Share2,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  SlidersVertical,
  Sparkles,
  Star,
  Target,
  Trash2,
  TrendingUp,
  TriangleAlert,
  UserMinus,
  UserPlus,
  Wallet,
  X,
  type LucideIcon,
  type LucideProps,
} from "lucide-react";

const iconRegistry: Record<string, LucideIcon> = {
  ArrowLeft,
  ArrowRight,
  Bell,
  BookOpen,
  Bookmark,
  BookmarkCheck,
  Building2,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarPlus,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  Clock,
  Copy,
  Download,
  ExternalLink,
  FilePlus,
  FileSpreadsheet,
  FileText,
  Flag,
  Gauge,
  Info,
  Kanban,
  Lightbulb,
  Link,
  Link2Off,
  LoaderCircle,
  Lock,
  LogOut,
  Mail,
  MapPin,
  Menu,
  MessageCircle,
  MessageSquare,
  OctagonAlert,
  Paperclip,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Search,
  Settings,
  Share2,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  SlidersVertical,
  Sparkles,
  Star,
  Target,
  Trash2,
  TrendingUp,
  TriangleAlert,
  UserMinus,
  UserPlus,
  Wallet,
  X,
};

const aliasMap: Record<string, keyof typeof iconRegistry> = {
  "alert-circle": "CircleAlert",
  "alert-triangle": "TriangleAlert",
  "arrow-left": "ArrowLeft",
  "arrow-right": "ArrowRight",
  "building-2": "Building2",
  "check-circle-2": "CircleCheck",
  "circle-check": "CircleCheck",
  "file-text": "FileText",
  "link-2-off": "Link2Off",
  "map-pin": "MapPin",
  "share-2": "Share2",
  "shield-check": "ShieldCheck",
  sliders: "SlidersVertical",
  "trash-2": "Trash2",
  "trending-up": "TrendingUp",
};

function toPascal(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function iconKey(name: string): string {
  return aliasMap[name] ?? toPascal(name);
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
  // Direct registry lookup: the React Compiler lint rejects a component returned by a
  // function call during render, even when it comes from a static map.
  const LucideComponent: LucideIcon | undefined = iconRegistry[iconKey(name)];
  if (!LucideComponent) {
    if (process.env.NODE_ENV !== "production") {
      console.warn(`[Icon] Unknown lucide name: "${name}"`);
    }
    return null;
  }
  return (
    <LucideComponent
      size={size}
      color={color}
      strokeWidth={strokeWidth}
      className={`flex-none ${className}`}
      {...rest}
    />
  );
}
