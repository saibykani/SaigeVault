"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useUIStore } from "@/stores/ui-store";

const SEQUENCE_TIMEOUT_MS = 900;

/** "G then X" navigation targets. */
export const GO_TO_SHORTCUTS: Record<string, string> = {
  d: "/",
  f: "/files",
  c: "/collections",
  a: "/ask",
  s: "/settings",
};

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable === true
  );
}

/**
 * Global shortcuts:
 *   Ctrl/Cmd+K  command palette
 *   /           search
 *   G then D/F/C/A/S  navigate
 */
export function useKeyboardShortcuts(): void {
  const router = useRouter();
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);

  useEffect(() => {
    let pendingG = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(!useUIStore.getState().commandPaletteOpen);
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey || isTypingTarget(event.target)) return;
      if (useUIStore.getState().commandPaletteOpen) return;

      const key = event.key.toLowerCase();
      if (pendingG) {
        pendingG = false;
        clearTimeout(timer);
        const href = GO_TO_SHORTCUTS[key];
        if (href) {
          event.preventDefault();
          router.push(href);
        }
        return;
      }
      if (key === "/") {
        event.preventDefault();
        router.push("/search");
      } else if (key === "g") {
        pendingG = true;
        timer = setTimeout(() => {
          pendingG = false;
        }, SEQUENCE_TIMEOUT_MS);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      clearTimeout(timer);
    };
  }, [router, setOpen]);
}
