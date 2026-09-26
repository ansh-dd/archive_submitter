import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Website Archive Submitter",
  description: "Domain discovery, archival submission and backup repository",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="brand">
            <span className="brandMark">WA</span>
            <div><strong>Website Archive Submitter</strong><small>Automated Backup Repository</small></div>
          </div>
          <nav>
            <Link href="/">Dashboard</Link>
            <Link href="/queue">Queue</Link>
            <Link href="/repository">Repository</Link>
          </nav>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
