"use client";

import { Search } from "lucide-react";
import Link from "next/link";

import { LogoMark } from "@/components/common/logo";
import { Kbd } from "@/components/ui/kbd";
import { useUIStore } from "@/stores/ui-store";

import { AccountMenu } from "./account-menu";
import { ThemeToggle, useMounted } from "./theme-toggle";

export function TopBar() {
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const mounted = useMounted();
  const isMac = mounted && /Mac|iPhone|iPad/.test(navigator.userAgent);

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/90 px-3 backdrop-blur sm:px-4">
      <Link href="/" className="md:hidden" aria-label="Saige Vault home">
        <LogoMark />
      </Link>

      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-md border bg-surface px-3 text-sm text-muted-foreground shadow-xs transition-colors hover:bg-muted"
      >
        <Search className="size-4" aria-hidden="true" />
        <span className="flex-1 truncate text-left">Search or run a command…</span>
        <span className="hidden items-center gap-0.5 sm:flex" aria-hidden="true">
          <Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd>
          <Kbd>K</Kbd>
        </span>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        <AccountMenu />
      </div>
    </header>
  );
}
