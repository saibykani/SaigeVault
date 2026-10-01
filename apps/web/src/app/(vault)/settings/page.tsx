import type { Metadata } from "next";

import { PageHeader } from "@/components/common/page-header";
import { SettingsView } from "@/components/settings/settings-view";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Appearance, privacy, storage and security." />
      <SettingsView />
    </>
  );
}
