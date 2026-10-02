import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FEATURES } from "@/lib/features";

import { FeatureNotice, PhaseBadge } from "./feature-notice";

describe("FeatureNotice", () => {
  it("explains which phase delivers an unavailable feature", () => {
    render(<FeatureNotice featureKey="askSaige" />);
    const note = screen.getByRole("note");
    expect(note).toHaveTextContent(FEATURES.askSaige.label);
    expect(note).toHaveTextContent(`Phase ${FEATURES.askSaige.phase}`);
  });

  it("shows a compact phase badge", () => {
    render(<PhaseBadge featureKey="askSaige" />);
    expect(screen.getByText(`P${FEATURES.askSaige.phase}`)).toBeInTheDocument();
  });
});

describe("feature registry", () => {
  it("assigns every feature to a real roadmap phase", () => {
    for (const f of Object.values(FEATURES)) {
      expect(f.phase).toBeGreaterThanOrEqual(1);
      expect(f.phase).toBeLessThanOrEqual(16);
      expect(f.description.length).toBeGreaterThan(10);
    }
  });
});

describe("shipped features", () => {
  it("renders nothing once a feature is available", () => {
    const { container } = render(<FeatureNotice featureKey="upload" />);
    expect(container).toBeEmptyDOMElement();
  });
});
