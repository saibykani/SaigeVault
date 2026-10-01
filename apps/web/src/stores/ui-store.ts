import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type FileViewMode = "grid" | "list";

interface UIState {
  sidebarCollapsed: boolean;
  fileViewMode: FileViewMode;
  commandPaletteOpen: boolean;
  toggleSidebar: () => void;
  setFileViewMode: (mode: FileViewMode) => void;
  setCommandPaletteOpen: (open: boolean) => void;
}

/**
 * Client-only UI preferences. Persisted to localStorage — this store must
 * never hold document data, tokens or anything sensitive.
 */
export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      fileViewMode: "list",
      commandPaletteOpen: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setFileViewMode: (fileViewMode) => set({ fileViewMode }),
      setCommandPaletteOpen: (commandPaletteOpen) => set({ commandPaletteOpen }),
    }),
    {
      name: "saige-ui",
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ sidebarCollapsed: s.sidebarCollapsed, fileViewMode: s.fileViewMode }),
    },
  ),
);
