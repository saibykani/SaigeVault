import {
  File,
  FileArchive,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder,
  Presentation,
} from "lucide-react";

import { cn } from "@/lib/utils";

const KIND: Record<string, { icon: typeof File; className: string }> = {
  pdf: { icon: FileText, className: "text-red-600 dark:text-red-400" },
  doc: { icon: FileText, className: "text-blue-600 dark:text-blue-400" },
  docx: { icon: FileText, className: "text-blue-600 dark:text-blue-400" },
  xls: { icon: FileSpreadsheet, className: "text-emerald-600 dark:text-emerald-400" },
  xlsx: { icon: FileSpreadsheet, className: "text-emerald-600 dark:text-emerald-400" },
  csv: { icon: FileSpreadsheet, className: "text-emerald-600 dark:text-emerald-400" },
  ppt: { icon: Presentation, className: "text-orange-600 dark:text-orange-400" },
  pptx: { icon: Presentation, className: "text-orange-600 dark:text-orange-400" },
  png: { icon: FileImage, className: "text-violet-600 dark:text-violet-400" },
  jpg: { icon: FileImage, className: "text-violet-600 dark:text-violet-400" },
  jpeg: { icon: FileImage, className: "text-violet-600 dark:text-violet-400" },
  webp: { icon: FileImage, className: "text-violet-600 dark:text-violet-400" },
  gif: { icon: FileImage, className: "text-violet-600 dark:text-violet-400" },
  json: { icon: FileCode2, className: "text-amber-600 dark:text-amber-400" },
  xml: { icon: FileCode2, className: "text-amber-600 dark:text-amber-400" },
  zip: { icon: FileArchive, className: "text-stone-600 dark:text-stone-400" },
};

export function FileIcon({
  extension,
  folder = false,
  className,
}: {
  extension?: string | null;
  folder?: boolean;
  className?: string;
}) {
  if (folder) {
    return (
      <Folder
        className={cn("size-4 shrink-0 fill-primary/15 text-primary", className)}
        aria-hidden="true"
      />
    );
  }
  const kind = KIND[extension ?? ""] ?? { icon: File, className: "text-muted-foreground" };
  const Icon = kind.icon;
  return <Icon className={cn("size-4 shrink-0", kind.className, className)} aria-hidden="true" />;
}

export const PREVIEWABLE = new Set([
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "webp",
  "gif",
  "txt",
  "md",
  "csv",
  "json",
  "xml",
]);
