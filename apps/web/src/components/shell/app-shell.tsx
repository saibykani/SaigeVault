"use client";

import type * as React from "react";

import { UploadManager } from "@/components/files/upload-manager";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";

import { AppSidebar, MobileNav } from "./app-sidebar";
import { CommandPalette } from "./command-palette";
import { TopBar } from "./top-bar";

export function AppShell({ children }: { children: React.ReactNode }) {
  useKeyboardShortcuts();
  return (
    <div className="flex h-dvh overflow-hidden">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <AppSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main id="main" tabIndex={-1} className="flex-1 overflow-y-auto pb-20 outline-none md:pb-0">
          {children}
        </main>
      </div>
      <MobileNav />
      <CommandPalette />
      <UploadManager />
    </div>
  );
}
