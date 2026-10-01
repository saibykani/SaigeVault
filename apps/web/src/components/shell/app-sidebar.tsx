"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { PhaseBadge } from "@/components/common/feature-notice";
import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { type NavItem, PRIMARY_NAV, SECONDARY_NAV, isActive } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

function NavLink({
  item,
  collapsed,
  active,
}: {
  item: NavItem;
  collapsed: boolean;
  active: boolean;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[13px] font-medium text-sidebar-foreground/85 transition-colors hover:bg-sidebar-active/60 hover:text-foreground",
        active && "bg-sidebar-active text-foreground",
        collapsed && "justify-center px-0",
      )}
    >
      <Icon className={cn("size-4 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
      {collapsed ? (
        <span className="sr-only">{item.label}</span>
      ) : (
        <span className="truncate">{item.label}</span>
      )}
      {!collapsed && item.feature ? (
        <PhaseBadge featureKey={item.feature} className="ml-auto" />
      ) : null}
    </Link>
  );
  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  return (
    <aside
      aria-label="Main navigation"
      className={cn(
        "hidden h-dvh shrink-0 flex-col border-r bg-sidebar transition-[width] duration-200 md:flex",
        collapsed ? "w-14" : "w-60",
      )}
    >
      <div
        className={cn("flex h-14 items-center border-b px-3", collapsed && "justify-center px-0")}
      >
        <Link href="/" aria-label="Saige Vault home" className="rounded-md">
          <Logo collapsed={collapsed} />
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {PRIMARY_NAV.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            collapsed={collapsed}
            active={isActive(pathname, item.href)}
          />
        ))}
      </nav>
      <div className="flex flex-col gap-0.5 border-t p-2">
        {SECONDARY_NAV.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            collapsed={collapsed}
            active={isActive(pathname, item.href)}
          />
        ))}
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSidebar}
          className={cn(
            "mt-1 justify-start gap-2.5 px-2.5 text-muted-foreground",
            collapsed && "justify-center px-0",
          )}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
          {collapsed ? null : <span className="text-[13px]">Collapse</span>}
        </Button>
      </div>
    </aside>
  );
}

/** Bottom tab bar for small screens. */
export function MobileNav() {
  const pathname = usePathname();
  const items = [...PRIMARY_NAV.slice(0, 4), SECONDARY_NAV[1]!];
  return (
    <nav
      aria-label="Main navigation"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      {items.map((item) => {
        const Icon = item.icon;
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex flex-col items-center gap-1 py-2 text-[11px] font-medium text-muted-foreground",
              active && "text-primary",
            )}
          >
            <Icon className="size-5" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
