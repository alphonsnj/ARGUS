import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "@argus/ui/styles.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "ARGUS",
  description: "Investigation intelligence platform",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${sans.variable} ${display.variable}`}>{children}</html>;
}
