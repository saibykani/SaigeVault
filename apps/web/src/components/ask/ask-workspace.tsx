"use client";

import { ConversationScope } from "@saige/types";
import {
  ArrowUp,
  BookOpenCheck,
  CircleHelp,
  Lightbulb,
  MessagesSquare,
  ShieldAlert,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { FeatureNotice } from "@/components/common/feature-notice";
import { LogoMark } from "@/components/common/logo";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSystemInfo } from "@/lib/api";
import { feature } from "@/lib/features";

const SCOPES: { value: ConversationScope; label: string }[] = [
  { value: ConversationScope.VAULT, label: "Entire vault" },
  { value: ConversationScope.COLLECTION, label: "A collection" },
  { value: ConversationScope.FOLDER, label: "A folder" },
  { value: ConversationScope.FILES, label: "Selected files" },
];

const SUGGESTIONS = [
  "What certificates do I have?",
  "When did I join my current company?",
  "What was my net salary in August?",
  "Which documents mention JMeter?",
  "Compare my resume with this job description",
  "Find documents expiring soon",
];

/** The trust model every answer follows. */
const ANSWER_KINDS = [
  {
    icon: BookOpenCheck,
    label: "Source-backed fact",
    detail: "Quoted from a document, with a page citation.",
  },
  { icon: Lightbulb, label: "AI inference", detail: "Reasoned from sources and labelled as such." },
  {
    icon: CircleHelp,
    label: "Unknown",
    detail: "Not in your documents — Saige says so instead of guessing.",
  },
];

export function AskWorkspace() {
  const [scope, setScope] = useState<ConversationScope>(ConversationScope.VAULT);
  const [draft, setDraft] = useState("");
  const { data: info } = useSystemInfo();
  const aiDisabled = info?.ai_processing_policy === "disabled";

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const f = feature("askSaige");
    toast.info(`${f.label} arrives in Phase ${f.phase}`, {
      description: "Your question was not sent anywhere.",
    });
  }

  return (
    <div className="grid h-[calc(100dvh-3.5rem)] min-h-0 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside aria-label="Conversations" className="hidden flex-col border-r lg:flex">
        <div className="flex h-12 items-center justify-between border-b px-4">
          <h2 className="text-sm font-semibold">Conversations</h2>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <MessagesSquare className="size-5 text-muted-foreground" aria-hidden="true" />
          <p className="text-[13px] text-muted-foreground">
            Your conversation history will appear here.
          </p>
        </div>
      </aside>

      <section className="flex min-h-0 flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-2xl flex-col items-center px-6 pt-12 pb-6 text-center">
            <LogoMark className="size-10" />
            <h1 className="mt-4 text-xl font-semibold tracking-tight">Ask Saige</h1>
            <p className="mt-1.5 max-w-md text-sm text-muted-foreground">
              Ask about one document, a collection, or your entire vault. Every answer cites its
              sources.
            </p>

            {aiDisabled ? (
              <div
                role="note"
                className="mt-6 flex w-full items-start gap-3 rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-left text-sm"
              >
                <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden="true" />
                <p className="text-muted-foreground">
                  <span className="font-medium text-foreground">
                    AI processing is disabled on this server.
                  </span>{" "}
                  No document content is sent to any model. An administrator can change{" "}
                  <code className="font-mono text-xs">AI_PROCESSING_POLICY</code> to{" "}
                  <code className="font-mono text-xs">local_only</code> or{" "}
                  <code className="font-mono text-xs">third_party_allowed</code>.
                </p>
              </div>
            ) : null}

            <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setDraft(s)}
                  className="rounded-lg border bg-surface px-3 py-2.5 text-left text-[13px] transition-colors hover:bg-muted"
                >
                  {s}
                </button>
              ))}
            </div>

            <ul className="mt-8 grid w-full gap-3 text-left sm:grid-cols-3">
              {ANSWER_KINDS.map(({ icon: Icon, label, detail }) => (
                <li key={label} className="rounded-lg border p-3">
                  <Icon className="size-4 text-primary" aria-hidden="true" />
                  <p className="mt-2 text-[13px] font-medium">{label}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
                </li>
              ))}
            </ul>
            <FeatureNotice featureKey="askSaige" className="mt-6 w-full text-left" />
          </div>
        </div>

        <form onSubmit={onSubmit} className="border-t bg-background px-4 py-3">
          <div className="mx-auto flex max-w-2xl flex-col gap-2 rounded-xl border bg-surface p-2 shadow-xs focus-within:border-ring">
            <label htmlFor="ask-input" className="sr-only">
              Ask a question about your documents
            </label>
            <textarea
              id="ask-input"
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Ask anything about your documents…"
              className="resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
            />
            <div className="flex items-center justify-between">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button type="button" variant="ghost" size="sm" className="text-muted-foreground">
                    Scope: {SCOPES.find((s) => s.value === scope)?.label}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  <DropdownMenuLabel>Answer from</DropdownMenuLabel>
                  <DropdownMenuRadioGroup
                    value={scope}
                    onValueChange={(v) => setScope(v as ConversationScope)}
                  >
                    {SCOPES.map((s) => (
                      <DropdownMenuRadioItem key={s.value} value={s.value}>
                        {s.label}
                      </DropdownMenuRadioItem>
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                type="submit"
                size="icon-sm"
                disabled={!draft.trim()}
                aria-label="Send question"
              >
                <ArrowUp />
              </Button>
            </div>
          </div>
        </form>
      </section>
    </div>
  );
}
