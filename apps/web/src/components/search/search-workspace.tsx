"use client";

import { SearchMode } from "@saige/types";
import { Search as SearchIcon, SlidersHorizontal } from "lucide-react";
import { type FormEvent, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { FeatureNotice } from "@/components/common/feature-notice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";

const MODES: { value: SearchMode; label: string }[] = [
  { value: SearchMode.HYBRID, label: "Hybrid" },
  { value: SearchMode.FULL_TEXT, label: "Full text" },
  { value: SearchMode.SEMANTIC, label: "Semantic" },
  { value: SearchMode.EXACT, label: "Exact" },
];

const FILTERS = ["File type", "Document type", "Date", "Folder", "Collection", "Tags", "Favorites"];

const EXAMPLES = [
  "Find all payslips from 2026",
  "JMeter performance notes",
  "Certificates issued by my university",
  "Documents expiring this year",
];

export function SearchWorkspace() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>(SearchMode.HYBRID);
  const [submitted, setSubmitted] = useState<string | null>(null);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (query.trim()) setSubmitted(query.trim());
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 p-6">
      <form role="search" onSubmit={onSubmit} className="flex flex-col gap-3">
        <div className="relative">
          <SearchIcon
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search filenames, document text, or ask in natural language…"
            aria-label="Search your vault"
            className="h-11 pl-9 text-[15px]"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl
            ariaLabel="Search mode"
            value={mode}
            onValueChange={setMode}
            options={MODES}
          />
          <div className="mx-1 hidden h-5 w-px bg-border sm:block" aria-hidden="true" />
          <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
          {FILTERS.map((f) => (
            <Badge key={f} variant="outline" className="h-7 px-2.5 text-xs">
              {f}
            </Badge>
          ))}
        </div>
      </form>

      {submitted ? (
        <div className="rounded-xl border">
          <EmptyState
            icon={SearchIcon}
            title="Search isn't connected yet"
            description={
              <>
                Your query <span className="font-medium text-foreground">“{submitted}”</span> was
                not sent anywhere. Results will appear here once the search service is available.
              </>
            }
          />
        </div>
      ) : (
        <div className="rounded-xl border p-5">
          <p className="text-sm font-medium">Try searching for</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((example) => (
              <Button
                key={example}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setQuery(example)}
              >
                {example}
              </Button>
            ))}
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            Natural-language queries are translated into structured filters — e.g. “payslips from
            2026” becomes <em>Document type: Salary · Year: 2026</em>.
          </p>
        </div>
      )}

      <FeatureNotice featureKey="search" />
      <FeatureNotice featureKey="semanticSearch" />
    </div>
  );
}
