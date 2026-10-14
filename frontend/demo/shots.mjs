// Tira as capturas de tela de demo/dist/index.html em docs/screenshots/.
// Uso: node demo/shots.mjs   (precisa de playwright e de um Chromium; veja demo/README.md)
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, "../../docs/screenshots");
const { chromium } = await import(process.env.DEMO_PLAYWRIGHT ?? "playwright");
mkdirSync(out, { recursive: true });

const SHOTS = [
  ["historias", 1280, "light", "01-historias"], ["historia", 1600, "light", "02-historia-enquadramento"],
  ["veiculo", 1280, "light", "03-veiculo-vies"], ["checagem", 1280, "light", "04-checagem-detalhe"],
  ["checagens", 1280, "light", "05-checagens-lista"], ["checagem", 390, "light", "06-checagem-celular"],
  ["veiculo", 1280, "dark", "07-veiculo-escuro"],
];
const browser = await chromium.launch(process.env.DEMO_CHROMIUM ? { executablePath: process.env.DEMO_CHROMIUM } : {});
let failed = 0;
for (const [page, width, scheme, file] of SHOTS) {
  const p = await browser.newPage({ viewport: { width, height: 900 }, colorScheme: scheme, deviceScaleFactor: 1 });
  const errors = [];
  p.on("pageerror", (e) => errors.push(String(e)));
  p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await p.goto("file://" + resolve(here, "dist/index.html") + "#" + page);
  await p.waitForSelector("body[data-ready]", { timeout: 15000 });
  const state = await p.evaluate(() => document.body.dataset.ready);
  if (state !== "1" || errors.length) { failed++; console.error("FALHA", file, state, errors); }
  await p.screenshot({ path: resolve(out, file + ".png"), fullPage: true });
  console.log("ok", file);
  await p.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
