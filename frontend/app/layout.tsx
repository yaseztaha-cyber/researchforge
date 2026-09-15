import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "ResearchForge — Research with evidence, not guesses",
  description: "Source-grounded AI research agent with evidence tracking and citation verification."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">Skip to content</a>
        <header className="topbar">
          <div className="topbar-inner">
            <a className="brand" href="/">ResearchForge<small>Research with evidence, not guesses.</small></a>
            <nav className="nav" aria-label="Primary">
              <a href="/">New research</a>
              <a href="/history">History</a>
              <a href="/evaluation">Evaluation</a>
            </nav>
          </div>
        </header>
        <main id="main" className="container">{children}</main>
        <footer className="container footer">
          ResearchForge · source-grounded research · every claim traces to evidence.
        </footer>
      </body>
    </html>
  );
}
