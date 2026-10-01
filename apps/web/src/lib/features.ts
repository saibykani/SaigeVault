/**
 * Feature availability registry.
 *
 * The UI never pretends a capability exists. Every surface that depends on
 * an unbuilt backend capability reads its status from here and shows an
 * honest notice. As each phase ships, flip `available` to true.
 */
export type FeatureKey =
  | "auth"
  | "googleDrive"
  | "files"
  | "upload"
  | "collections"
  | "tags"
  | "processing"
  | "search"
  | "semanticSearch"
  | "askSaige"
  | "agent"
  | "timeline"
  | "sync"
  | "export";

export interface Feature {
  label: string;
  phase: number;
  available: boolean;
  description: string;
}

export const FEATURES: Record<FeatureKey, Feature> = {
  auth: {
    label: "Secure sign-in",
    phase: 3,
    available: true,
    description: "Google sign-in with server-side sessions and token rotation.",
  },
  googleDrive: {
    label: "Google Drive connection",
    phase: 4,
    available: true,
    description:
      "Connect your Drive. Files stay in your Drive; tokens stay encrypted on the server.",
  },
  files: {
    label: "File management",
    phase: 5,
    available: false,
    description: "Browse, rename, move, favourite, delete and restore your files.",
  },
  upload: {
    label: "Uploads",
    phase: 5,
    available: false,
    description: "Upload files with server-side type validation and integrity checks.",
  },
  collections: {
    label: "Collections",
    phase: 5,
    available: false,
    description: "Group files virtually — one file can live in many collections without copies.",
  },
  tags: {
    label: "Tags",
    phase: 5,
    available: false,
    description: "Manual tags plus AI-suggested tags that you confirm.",
  },
  processing: {
    label: "Document processing",
    phase: 7,
    available: false,
    description: "Text extraction, OCR, classification and structured data extraction.",
  },
  search: {
    label: "Search",
    phase: 8,
    available: false,
    description: "Filename, full-text and filtered search across your vault.",
  },
  semanticSearch: {
    label: "Semantic & hybrid search",
    phase: 9,
    available: false,
    description: "Meaning-based retrieval powered by vector embeddings.",
  },
  askSaige: {
    label: "Ask Saige",
    phase: 11,
    available: false,
    description: "Ask questions about your documents and get cited, source-backed answers.",
  },
  agent: {
    label: "Saige agent",
    phase: 12,
    available: false,
    description: "Multi-step tasks over your documents, with confirmation for any change.",
  },
  timeline: {
    label: "Timeline",
    phase: 10,
    available: false,
    description: "Your documents in time, built only from extracted or confirmed dates.",
  },
  sync: {
    label: "Drive sync",
    phase: 13,
    available: false,
    description: "Detect changes made directly in Google Drive and keep the vault in sync.",
  },
  export: {
    label: "Data export",
    phase: 14,
    available: false,
    description: "Export metadata, collections, tags, summaries and chat history.",
  },
};

export function feature(key: FeatureKey): Feature {
  return FEATURES[key];
}
