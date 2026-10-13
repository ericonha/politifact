import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import Link from "next/link";
import { MainNav } from "@/components/MainNav";
import "./globals.css";

// Fonte das manchetes e do cabeçalho: grotesca firme, levemente estreita, de portal de notícias.
const display = Archivo({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PolitiFact BR",
  description: "Cobertura de notícias e checagem de fatos",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={display.variable}>
      <body>
        <header className="masthead">
          <div className="mast-inner">
            <Link href="/" className="brand" aria-label="PolitiFact BR, página inicial">
              <span className="brand-block" aria-hidden="true">PF</span>
              <span className="brand-name">PolitiFact BR</span>
            </Link>
            <MainNav />
          </div>
        </header>
        <main className="shell">{children}</main>
      </body>
    </html>
  );
}
