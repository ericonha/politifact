import Link from "next/link";
import type { ReactNode } from "react";
import { toggleFavorite } from "@/app/actions";
import {
  GROUPS,
  TOPIC_LABELS,
  WINDOWS,
  formatTime,
  timeAgo,
  type CollectionStatus,
  type Outlet,
  type Topic,
} from "@/lib/api";

type Params = Record<string, string | undefined>;

type Props = {
  title: string;
  intro?: ReactNode;
  /** Caminho da página, para montar os links de filtro mantendo os outros parâmetros. */
  basePath: string;
  params: Params;
  status: CollectionStatus | null;
  /** Períodos: "janela" (24h/3d/7d). */
  period?: boolean;
  /** Intervalo de datas (só no painel de cobertura). */
  customRange?: boolean;
  topics?: Topic[] | true;
  outlets?: Outlet[];
  group?: boolean;
};

function href(basePath: string, params: Params, change: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...params, ...change })) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `${basePath}?${s}` : basePath;
}

function Star({ outlet }: { outlet: Outlet }) {
  return (
    <form action={toggleFavorite} className="star-form">
      <input type="hidden" name="outlet_id" value={outlet.id} />
      <input type="hidden" name="favorite" value={outlet.favorite ? "false" : "true"} />
      <button
        type="submit"
        className={outlet.favorite ? "star on" : "star"}
        aria-pressed={outlet.favorite}
        aria-label={outlet.favorite ? `Tirar ${outlet.name} dos favoritos` : `Favoritar ${outlet.name}`}
        title={outlet.favorite ? "Tirar dos favoritos" : "Favoritar"}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3.5l2.6 5.3 5.9.9-4.25 4.1 1 5.85L12 16.9l-5.25 2.75 1-5.85L3.5 9.7l5.9-.9z" />
        </svg>
      </button>
    </form>
  );
}

function CollectionBox({ status }: { status: CollectionStatus | null }) {
  if (!status) return null;
  return (
    <div className="side-status" aria-live="polite">
      <div className="side-label">Última coleta</div>
      {status.last_success_at ? (
        <div>
          <strong>{formatTime(status.last_success_at)}</strong>{" "}
          <span className="muted">({timeAgo(status.last_success_at)})</span>
        </div>
      ) : (
        <div className="muted">Nenhuma coleta concluída ainda.</div>
      )}
      {status.running ? (
        <div className="side-running">Coletando agora…</div>
      ) : status.next_expected_at ? (
        <div className="muted">Próxima por volta de {formatTime(status.next_expected_at)}</div>
      ) : null}
      {status.failing_outlets.length > 0 && (
        <Link href="/coletas" className="side-warn">
          {status.failing_outlets.length === 1
            ? `${status.failing_outlets[0]} falhou na última coleta`
            : `${status.failing_outlets.length} veículos falharam na última coleta`}
        </Link>
      )}
    </div>
  );
}

export function Sidebar({ title, intro, basePath, params, status, period, customRange, topics, outlets, group }: Props) {
  const custom = !!(params.de && params.ate);
  const win = params.janela ?? "24h";
  const topicCounts = Array.isArray(topics) ? new Map(topics.map((t) => [t.key, t.article_count])) : null;
  const selectedOutlet = params.veiculo ? Number(params.veiculo) : undefined;
  const favs = (outlets ?? []).filter((o) => o.favorite);
  const others = (outlets ?? []).filter((o) => !o.favorite && o.active);
  const clearOutlet = { veiculo: undefined, favoritos: undefined };

  return (
    <aside className="sidebar" aria-label="Filtros">
      <h1 className="page-title">{title}</h1>
      {intro && <div className="side-intro">{intro}</div>}
      <CollectionBox status={status} />

      {period && (
        <section className="side-block">
          <div className="side-label">Período</div>
          <div className="seg">
            {WINDOWS.map((w) => (
              <Link
                key={w.value}
                href={href(basePath, params, { janela: w.value, de: undefined, ate: undefined })}
                className={!custom && w.value === win ? "seg-item active" : "seg-item"}
                aria-current={!custom && w.value === win ? "true" : undefined}
              >
                {w.label}
              </Link>
            ))}
          </div>
          {customRange && (
            <details className="side-dates" open={custom}>
              <summary>Escolher datas</summary>
              <form action={basePath} method="get">
                {Object.entries(params)
                  .filter(([k, v]) => v && !["janela", "de", "ate"].includes(k))
                  .map(([k, v]) => <input key={k} type="hidden" name={k} value={v} />)}
                <label>De <input type="date" name="de" defaultValue={params.de ?? ""} required /></label>
                <label>Até <input type="date" name="ate" defaultValue={params.ate ?? ""} required /></label>
                <button type="submit" className="button small">Aplicar datas</button>
              </form>
            </details>
          )}
        </section>
      )}

      {topics && (
        <section className="side-block">
          <div className="side-label">Seções</div>
          <nav className="side-topics" aria-label="Seções">
            <Link href={href(basePath, params, { secao: undefined })} className={!params.secao ? "topic active" : "topic"}>
              Todas
            </Link>
            {Object.entries(TOPIC_LABELS).map(([key, label]) => {
              const n = topicCounts?.get(key);
              return (
                <Link
                  key={key}
                  href={href(basePath, params, { secao: key })}
                  className={`topic${params.secao === key ? " active" : ""}${topicCounts && !n && params.secao !== key ? " empty" : ""}`}
                  aria-current={params.secao === key ? "page" : undefined}
                >
                  <span>{label}</span>
                  {n ? <span className="count">{n}</span> : null}
                </Link>
              );
            })}
          </nav>
        </section>
      )}

      {group && (
        <section className="side-block">
          <div className="side-label">Grupo</div>
          <div className="seg">
            {GROUPS.map((g) => (
              <Link
                key={g.label}
                href={href(basePath, params, { grupo: g.value })}
                className={g.value === params.grupo ? "seg-item active" : "seg-item"}
              >
                {g.label}
              </Link>
            ))}
          </div>
        </section>
      )}

      {outlets && (
        <section className="side-block">
          <div className="side-label">Veículos</div>
          <ul className="side-outlets">
            <li>
              <Link href={href(basePath, params, clearOutlet)} className={!selectedOutlet && params.favoritos !== "1" ? "outlet-link active" : "outlet-link"}>
                Todos
              </Link>
            </li>
            <li>
              <Link
                href={href(basePath, params, { veiculo: undefined, favoritos: "1" })}
                className={params.favoritos === "1" && !selectedOutlet ? "outlet-link active" : "outlet-link"}
              >
                Só favoritos{favs.length ? ` (${favs.length})` : ""}
              </Link>
            </li>
          </ul>
          {favs.length === 0 && <p className="side-hint">Toque na estrela de um veículo para favoritá-lo.</p>}
          {favs.length > 0 && (
            <ul className="side-outlets">
              {favs.map((o) => (
                <li key={o.id}>
                  <Link href={href(basePath, params, { veiculo: String(o.id), favoritos: undefined })}
                        className={selectedOutlet === o.id ? "outlet-link active" : "outlet-link"}>
                    {o.name}
                  </Link>
                  <Star outlet={o} />
                </li>
              ))}
            </ul>
          )}
          <details className="side-more" open={!!selectedOutlet && others.some((o) => o.id === selectedOutlet)}>
            <summary>{favs.length ? "Outros veículos" : "Todos os veículos"} ({others.length})</summary>
            <ul className="side-outlets">
              {others.map((o) => (
                <li key={o.id}>
                  <Link href={href(basePath, params, { veiculo: String(o.id), favoritos: undefined })}
                        className={selectedOutlet === o.id ? "outlet-link active" : "outlet-link"}>
                    {o.name}
                  </Link>
                  <Star outlet={o} />
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}

    </aside>
  );
}

/** Página com barra lateral à esquerda e conteúdo à direita. */
export function PageLayout({ sidebar, children }: { sidebar: ReactNode; children: ReactNode }) {
  return (
    <div className="page">
      {sidebar}
      <div className="page-main">{children}</div>
    </div>
  );
}
