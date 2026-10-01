import {
  Activity,
  CalendarClock,
  FolderClosed,
  LayoutDashboard,
  Library,
  type LucideIcon,
  Search,
  Settings,
  Sparkles,
} from "lucide-react";

import type { FeatureKey } from "@/lib/features";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  feature?: FeatureKey;
  /** Keyboard sequence shown in the command palette, e.g. ["G", "F"]. */
  shortcut?: string[];
}

export const PRIMARY_NAV: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, shortcut: ["G", "D"] },
  { href: "/files", label: "Files", icon: FolderClosed, feature: "files", shortcut: ["G", "F"] },
  { href: "/search", label: "Search", icon: Search, feature: "search", shortcut: ["/"] },
  {
    href: "/collections",
    label: "Collections",
    icon: Library,
    feature: "collections",
    shortcut: ["G", "C"],
  },
  { href: "/ask", label: "Ask Saige", icon: Sparkles, feature: "askSaige", shortcut: ["G", "A"] },
  { href: "/timeline", label: "Timeline", icon: CalendarClock, feature: "timeline" },
];

export const SECONDARY_NAV: NavItem[] = [
  { href: "/system", label: "System status", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings, shortcut: ["G", "S"] },
];

export function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}
