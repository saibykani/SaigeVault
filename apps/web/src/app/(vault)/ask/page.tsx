import type { Metadata } from "next";

import { AskWorkspace } from "@/components/ask/ask-workspace";

export const metadata: Metadata = { title: "Ask Saige" };

export default function AskPage() {
  return <AskWorkspace />;
}
