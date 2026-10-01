import type { DocumentType, ProcessingStatus } from "./enums.gen";

/** Human-readable labels. Typed as Record<Enum, string> so a new backend
 * enum value fails type-checking until a label is added. */
export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  identity: "Identity",
  education: "Education",
  employment: "Employment",
  salary: "Salary",
  banking: "Banking",
  tax: "Tax",
  insurance: "Insurance",
  finance: "Finance",
  medical: "Medical",
  legal: "Legal",
  travel: "Travel",
  certificate: "Certificates",
  resume: "Resume",
  job_description: "Job Description",
  personal: "Personal",
  work: "Work",
  project: "Projects",
  image: "Images",
  other: "Other",
  unclassified: "Unclassified",
};

export const PROCESSING_STATUS_LABELS: Record<ProcessingStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  unsupported: "Unsupported",
};
