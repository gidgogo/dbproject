// Mermaid(.mmd) → SVG/PNG 렌더러 (인터넷 없이 로컬 npm 패키지 + Playwright Chromium)
//
// 준비(한 번): npm i mermaid@11 @mermaid-js/layout-elk@0.2 playwright
// 사용:       node tools/render_mermaid.js erd/erd_conceptual.mmd erd/img/erd_conceptual [elk|dagre]
//             → erd/img/erd_conceptual.svg, .png
// 환경변수 NODE_MODULES 로 node_modules 폴더 위치를 직접 줄 수 있다.
// ESM 모듈은 file:// 에서 못 읽으므로 작은 로컬 HTTP 서버로 node_modules 를 띄워서 불러온다.
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const MODULES = process.env.NODE_MODULES || path.dirname(path.dirname(require.resolve('mermaid/package.json')));
const TYPES = { '.mjs': 'text/javascript', '.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json' };

function serve() {
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    if (url === '/index.html') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end('<!doctype html><html><head><meta charset="utf-8"><style>body{margin:0;background:#fff}</style>'
        + '</head><body><div id="out"></div></body></html>');
    }
    const file = path.join(MODULES, url);
    if (!file.startsWith(MODULES) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

async function main() {
  const [src, outBase, layout = 'elk'] = process.argv.slice(2);
  if (!src || !outBase) {
    console.error('사용: node tools/render_mermaid.js <입력.mmd> <출력경로(확장자 없이)> [elk|dagre]');
    process.exit(2);
  }
  const code = fs.readFileSync(src, 'utf8');
  const server = await serve();
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  const scale = Number(process.env.SCALE || 2);  // 큰 ERD는 SCALE=1 로
  const page = await browser.newPage({ deviceScaleFactor: scale, viewport: { width: 1800, height: 1200 } });
  await page.goto(`${base}/index.html`);
  const svg = await page.evaluate(async ({ c, layout, base }) => {
    const mermaid = (await import(`${base}/mermaid/dist/mermaid.esm.min.mjs`)).default;
    if (layout === 'elk') {
      const elk = (await import(`${base}/@mermaid-js/layout-elk/dist/mermaid-layout-elk.esm.min.mjs`)).default;
      mermaid.registerLayoutLoaders(elk);
    }
    mermaid.initialize({ startOnLoad: false, theme: 'neutral', layout, er: { useMaxWidth: false },
                         fontFamily: "'Noto Sans CJK KR','Apple SD Gothic Neo','Malgun Gothic',sans-serif" });
    const { svg } = await mermaid.render('erd', c);
    document.getElementById('out').innerHTML = svg;
    return svg;
  }, { c: code, layout, base });
  fs.mkdirSync(path.dirname(outBase), { recursive: true });
  fs.writeFileSync(outBase + '.svg', svg);
  await (await page.$('#out svg')).screenshot({ path: outBase + '.png' });
  await browser.close();
  server.close();
  console.log('저장:', outBase + '.svg', outBase + '.png');
}
main().catch((e) => { console.error(e); process.exit(1); });
