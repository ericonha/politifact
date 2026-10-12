import Link from "next/link";
import { WINDOWS, getOutlets, getStories, parseWindow } from "@/lib/api";

export default async function StoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ janela?: string }>;
}) {
  const { janela } = await searchParams;
  const win = parseWindow(janela);
  const [stories, outlets] = await Promise.all([getStories(win), getOutlets()]);

  return (
    <>
      <div className="toolbar">
        <h1>Histórias</h1>
        <div className="tabs">
          {WINDOWS.map((w) => (
            <Link
              key={w.value}
              href={`/?janela=${w.value}`}
              className={w.value === win ? "tab active" : "tab"}
            >
              {w.label}
            </Link>
          ))}
        </div>
      </div>

      <p className="note">
        Cobertura entre os {outlets.length} veículos monitorados, não cobertura total da mídia.
      </p>

      {stories.length === 0 ? (
        <div className="empty">
          Nenhuma história neste período ainda. As notícias são agrupadas logo depois de cada
          coleta; veja as <Link href="/noticias">notícias coletadas</Link> e a{" "}
          <Link href="/revisao">fila de revisão</Link>.
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>História</th>
              {outlets.map((o) => (
                <th key={o.id} className="num">{o.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stories.map((s) => {
              const byOutlet = new Map(s.coverage.map((c) => [c.outlet_id, c.article_count]));
              return (
                <tr key={s.id}>
                  <td>
                    <Link href={`/historias/${s.id}`} className="story-link">{s.title}</Link>
                    {s.summary && <div className="muted">{s.summary}</div>}
                  </td>
                  {outlets.map((o) => (
                    <td key={o.id} className="num">{byOutlet.get(o.id) ?? "—"}</td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
