import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Auto-YouTube Dashboard",
  description: "Manage your AI-powered video generation pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
