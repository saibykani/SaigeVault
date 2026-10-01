import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useUIStore } from "@/stores/ui-store";

import { CommandPalette } from "./command-palette";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next-themes", () => ({ useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }) }));
vi.mock("sonner", () => ({ toast: { info: vi.fn() } }));

describe("CommandPalette", () => {
  beforeEach(() => {
    push.mockReset();
    useUIStore.setState({ commandPaletteOpen: true });
  });

  it("lists navigation targets and actions", () => {
    render(<CommandPalette />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Upload files")).toBeInTheDocument();
    expect(screen.getByText("Collections")).toBeInTheDocument();
  });

  it("filters by query and navigates on select", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);
    await user.type(screen.getByPlaceholderText(/type a command/i), "settings");
    expect(screen.queryByText("Upload files")).not.toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/settings");
    expect(useUIStore.getState().commandPaletteOpen).toBe(false);
  });

  it("does not render when closed", () => {
    useUIStore.setState({ commandPaletteOpen: false });
    render(<CommandPalette />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
