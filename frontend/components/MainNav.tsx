"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Histórias" },
  { href: "/resumo", label: "Resumo" },
  { href: "/checagem", label: "Checagem" },
  { href: "/cobertura", label: "Cobertura" },
  { href: "/noticias", label: "Notícias" },
  { href: "/revisao", label: "Revisão" },
  { href: "/coletas", label: "Coletas" },
  { href: "/veiculos", label: "Veículos" },
];

export function MainNav() {
  const path = usePathname() ?? "/";
  const isActive = (href: string) =>
    href === "/" ? path === "/" || path.startsWith("/historias") || path.startsWith("/comparar") : path.startsWith(href);
  return (
    <nav className="mast-nav" aria-label="Principal">
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className={isActive(l.href) ? "active" : undefined}
              aria-current={isActive(l.href) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
