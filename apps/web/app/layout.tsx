import type { Metadata } from "next";
import "./globals.css";
import "./auth.css";

export const metadata: Metadata = {
  title: "ADDA AI - Agent workspace",
  description: "A multi-agent workspace that shows the route, the evidence, and the result.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
