# Demonstração com capturas de tela

As imagens de `docs/screenshots/` são geradas pelas páginas **reais** do app (`app/**`), lendo
dados **fictícios** de `demo/mock-api.ts` (veículos, cidades e políticos inventados; faixa de aviso em toda tela).
Não precisa de banco, API nem Ollama.

```bash
cd frontend && npm install          # React e dependências do app
npm install --no-save esbuild playwright && npx playwright install chromium
node demo/build.mjs && node demo/shots.mjs
```

Variáveis opcionais: `DEMO_CHROMIUM` (caminho de um Chromium já instalado), `DEMO_NODE_PATH`,
`DEMO_ESBUILD`, `DEMO_PLAYWRIGHT`. Quando uma página mudar, rode de novo para atualizar as imagens.
`demo/dist/` é gerado e fica fora do git.
