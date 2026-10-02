"use client";

import { Command } from "cmdk";
import { FolderPlus, type LucideIcon, Moon, Search, Sparkles, Sun, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";

import { PhaseBadge } from "@/components/common/feature-notice";
import { openFilePicker } from "@/components/files/upload-manager";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import type { FeatureKey } from "@/lib/features";
import { PRIMARY_NAV, SECONDARY_NAV } from "@/lib/navigation";
import { useUIStore } from "@/stores/ui-store";

interface PaletteAction {
  id: string;
  label: string;
  icon: LucideIcon;
  keywords?: string[];
  feature?: FeatureKey;
  run: () => void;
}

const itemClass =
  "flex h-9 cursor-default items-center gap-2.5 rounded-md px-2.5 text-sm outline-none select-none data-[selected=true]:bg-muted data-[disabled=true]:opacity-50 [&_svg]:size-4 [&_svg]:text-muted-foreground";

const groupClass =
  "px-1.5 py-1 [&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground";

export function CommandPalette() {
  const open = useUIStore((s) => s.commandPaletteOpen);
  const setOpen = useUIStore((s) => s.setCommandPaletteOpen);
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  function close() {
    setOpen(false);
  }

  const actions: PaletteAction[] = [
    {
      id: "upload",
      label: "Upload files",
      icon: Upload,
      keywords: ["add", "import"],
      run: () => openFilePicker(),
    },
    {
      id: "new-folder",
      label: "Go to files to create a folder",
      icon: FolderPlus,
      keywords: ["new folder"],
      run: () => router.push("/files"),
    },
    {
      id: "search-files",
      label: "Search files",
      icon: Search,
      keywords: ["find"],
      run: () => router.push("/search"),
    },
    {
      id: "ask",
      label: "Ask Saige",
      icon: Sparkles,
      keywords: ["ai", "chat", "question"],
      run: () => router.push("/ask"),
    },
    {
      id: "theme",
      label: resolvedTheme === "dark" ? "Switch to light theme" : "Switch to dark theme",
      icon: resolvedTheme === "dark" ? Sun : Moon,
      keywords: ["appearance", "dark mode", "light mode"],
      run: () => setTheme(resolvedTheme === "dark" ? "light" : "dark"),
    },
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-xl overflow-hidden" showClose={false}>
        <DialogTitle className="sr-only">Command palette</DialogTitle>
        <DialogDescription className="sr-only">
          Search for pages and actions. Use arrow keys to navigate and Enter to select.
        </DialogDescription>
        <Command label="Command palette" loop className="flex flex-col">
          <div className="flex items-center gap-2 border-b px-3">
            <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <Command.Input
              autoFocus
              placeholder="Type a command or search…"
              className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <Kbd>Esc</Kbd>
          </div>
          <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto py-1">
            <Command.Empty className="py-8 text-center text-sm text-muted-foreground">
              No matching commands.
            </Command.Empty>
            <Command.Group heading="Actions" className={groupClass}>
              {actions.map((action) => {
                const Icon = action.icon;
                return (
                  <Command.Item
                    key={action.id}
                    value={action.label}
                    keywords={action.keywords}
                    onSelect={() => {
                      close();
                      action.run();
                    }}
                    className={itemClass}
                  >
                    <Icon />
                    <span>{action.label}</span>
                    {action.feature ? (
                      <PhaseBadge featureKey={action.feature} className="ml-auto" />
                    ) : null}
                  </Command.Item>
                );
              })}
            </Command.Group>
            <Command.Group heading="Go to" className={groupClass}>
              {[...PRIMARY_NAV, ...SECONDARY_NAV].map((item) => {
                const Icon = item.icon;
                return (
                  <Command.Item
                    key={item.href}
                    value={`Go to ${item.label}`}
                    onSelect={() => {
                      close();
                      router.push(item.href);
                    }}
                    className={itemClass}
                  >
                    <Icon />
                    <span>{item.label}</span>
                    {item.shortcut ? (
                      <span className="ml-auto flex gap-1">
                        {item.shortcut.map((k) => (
                          <Kbd key={k}>{k}</Kbd>
                        ))}
                      </span>
                    ) : null}
                  </Command.Item>
                );
              })}
            </Command.Group>
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}
