import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { AppProviders } from "@/components/providers";
import { cn } from "@/lib/utils";

const bodyFont = Manrope({ subsets: ["latin"], variable: "--font-body" });
const headingFont = Space_Grotesk({ subsets: ["latin"], variable: "--font-heading" });

export const metadata: Metadata = {
  title: "Dymo SaaS Core",
  description: "Frontend de pilotage du core Dymo SaaS."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fr">
      <body className={cn(bodyFont.variable, headingFont.variable, "min-h-screen bg-slate-50 font-sans")}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
