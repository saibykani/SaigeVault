import type { MetadataRoute } from "next";

/** Makes the web app installable ("Add to Home Screen") on iPhone and Android. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Saige Vault",
    short_name: "Saige Vault",
    description: "Your private, AI-powered personal document vault.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#fbfcfa",
    theme_color: "#3d7a63",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
