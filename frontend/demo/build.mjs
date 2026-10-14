// Gera demo/dist/<página>.html a partir das páginas REAIS do app (app/**) lendo dados fictícios (mock-api.ts).
// Uso: node demo/build.mjs   (precisa de esbuild; veja demo/README.md)
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const front = resolve(here, "..");
const nodePaths = (process.env.DEMO_NODE_PATH ?? "").split(":").filter(Boolean);
const { build } = await import(process.env.DEMO_ESBUILD ?? "esbuild");

mkdirSync(resolve(here, "dist"), { recursive: true });
await build({
  entryPoints: [resolve(here, "entry.tsx")], bundle: true, outfile: resolve(here, "dist/out.js"), jsx: "automatic",
  nodePaths: [resolve(front, "node_modules"), ...nodePaths], logLevel: "warning",
  define: { "process.env.NODE_ENV": '"production"', "process.env.API_URL": "undefined" },
  plugins: [{ name: "shims", setup(b) {
    b.onResolve({ filter: /^@\/lib\/api$/ }, () => ({ path: resolve(here, "mock-api.ts") }));
    b.onResolve({ filter: /^next\/link$/ }, () => ({ path: resolve(here, "shims/link.tsx") }));
    b.onResolve({ filter: /^next\/navigation$/ }, () => ({ path: resolve(here, "shims/nav.ts") }));
    b.onResolve({ filter: /^next\/cache$/ }, () => ({ path: resolve(here, "shims/cache.ts") }));
    b.onResolve({ filter: /^@\// }, (a) => b.resolve("./" + a.path.slice(2), { resolveDir: front, kind: a.kind }));
  } }],
});

const css = readFileSync(resolve(front, "app/globals.css"), "utf8");
const banner = `.demo-banner{background:#7c2d12;color:#fff;text-align:center;font:600 12px/1 system-ui,sans-serif;padding:8px 12px;letter-spacing:.02em}`;
writeFileSync(resolve(here, "dist/index.html"),
  `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
  `<title>PolitiFact BR (demonstração)</title><style>${css}\n${banner}</style></head><body><div id="root"></div><script src="out.js"></script></body></html>`);
console.log("ok: demo/dist/index.html");
