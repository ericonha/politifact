import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolitiFact BR",
  description: "Cobertura de notícias e checagem de fatos",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="top">
          <Link href="/" className="brand">PolitiFact BR</Link>
          <nav>
            <Link href="/">Histórias</Link>
            <Link href="/cobertura">Cobertura</Link>
            <Link href="/noticias">Notícias</Link>
            <Link href="/revisao">Revisão</Link>
            <Link href="/coletas">Coletas</Link>
            <Link href="/veiculos">Veículos</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
