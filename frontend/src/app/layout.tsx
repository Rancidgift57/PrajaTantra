import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import ClientOnly from "@/components/ClientOnly";

export const metadata: Metadata = {
  title: "PrajaTantra – Loktantra Simulation",
  description: "भारतीय राजनीतिक-आर्थिक शासन सिमुलेशन | Indian political-economic governance simulation",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="hi" suppressHydrationWarning>
      <body suppressHydrationWarning>
        {/*
          ClientOnly ensures the entire dashboard renders ONLY on the client,
          sending an empty shell from the server. This completely eliminates
          the React 19 "removeChild" hydration crash caused by browser
          extensions (Google Translate, Grammarly, etc.) injecting DOM nodes
          before React can hydrate — there is no SSR output to mismatch against.
        */}
        <ClientOnly>{children}</ClientOnly>
      </body>
    </html>
  );
}