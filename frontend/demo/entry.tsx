import { createRoot } from "react-dom/client";
import Link from "next/link";
import { MainNav } from "@/components/MainNav";
import Home from "@/app/page";
import Story from "@/app/historias/[id]/page";
import Outlet from "@/app/veiculos/[id]/page";
import CheckList from "@/app/checagem/page";
import CheckDetail from "@/app/checagem/[id]/page";

const PAGES: Record<string, { path: string; render: () => Promise<any> }> = {
  historias: { path: "/", render: () => Home({ searchParams: Promise.resolve({}) }) },
  historia: { path: "/historias/1", render: () => Story({ params: Promise.resolve({ id: "1" }) }) },
  veiculo: { path: "/veiculos/3", render: () => Outlet({ params: Promise.resolve({ id: "3" }), searchParams: Promise.resolve({}) }) },
  checagens: { path: "/checagem", render: () => CheckList({ searchParams: Promise.resolve({}) }) },
  checagem: { path: "/checagem/12", render: () => CheckDetail({ params: Promise.resolve({ id: "12" }) }) },
};

(async () => {
  const page = PAGES[location.hash.slice(1)] ?? PAGES.historias;
  (globalThis as any).__PATH__ = page.path;
  const el = await page.render();
  createRoot(document.getElementById("root")!).render(<>
    <div className="demo-banner">DEMONSTRAÇÃO — todos os veículos, pessoas e números desta tela são fictícios</div>
    <header className="masthead"><div className="mast-inner">
      <Link href="/" className="brand"><span className="brand-block">PF</span><span className="brand-name">PolitiFact BR</span></Link>
      <MainNav /></div></header>
    <main className="shell">{el}</main></>);
  document.body.dataset.ready = "1";
})().catch((e) => { console.error("RENDER FAIL", e); document.body.dataset.ready = "error"; });
