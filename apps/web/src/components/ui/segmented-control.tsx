"use client";

import type * as React from "react";

import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  /** When true the label is only exposed to assistive tech. */
  iconOnly?: boolean;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  onValueChange: (value: T) => void;
  options: SegmentedOption<T>[];
  ariaLabel: string;
  className?: string;
}

/** Accessible single-select toggle group (radiogroup semantics, arrow-key navigation). */
export function SegmentedControl<T extends string>({
  value,
  onValueChange,
  options,
  ariaLabel,
  className,
}: SegmentedControlProps<T>) {
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const index = options.findIndex((o) => o.value === value);
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = options[(index + delta + options.length) % options.length];
    if (next) {
      onValueChange(next.value);
      const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=radio]");
      buttons[(index + delta + options.length) % options.length]?.focus();
    }
  }

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      onKeyDown={onKeyDown}
      className={cn("inline-flex h-8 items-center rounded-md border bg-muted p-0.5", className)}
    >
      {options.map((option) => {
        const selected = option.value === value;
        const Icon = option.icon;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            title={option.iconOnly ? option.label : undefined}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "inline-flex h-full items-center gap-1.5 rounded-[5px] px-2.5 text-[13px] font-medium text-muted-foreground transition-colors",
              selected && "bg-surface text-foreground shadow-xs",
            )}
          >
            {Icon ? <Icon className="size-3.5" /> : null}
            <span className={option.iconOnly ? "sr-only" : undefined}>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
