import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Control Fabric - Admin Console",
  description: "Manage prompts, domain packs, model runs, and evaluations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-neutral-50 text-neutral-900`}>
        <Sidebar />
        <main className="ml-60 min-h-screen">
          <div className="mx-auto max-w-7xl px-6 py-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
