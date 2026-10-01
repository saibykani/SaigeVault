import "./globals.css";

import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Saige Vault", template: "%s · Saige Vault" },
  description: "Your private, AI-powered personal document vault.",
  applicationName: "Saige Vault",
  // Private application: never index.
  robots: { index: false, follow: false },
  // Home-screen install on iPhone: full screen, no Safari toolbars.
  appleWebApp: { capable: true, title: "Saige Vault", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfcfa" },
    { media: "(prefers-color-scheme: dark)", color: "#111614" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
