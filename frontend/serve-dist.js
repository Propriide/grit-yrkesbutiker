// Minimal static server for the Expo web export (frontend/dist) – used to test the production PWA build.
// SPA: unknown paths -> index.html. /api/* is proxied to the FastAPI backend (same origin, like production).
// Usage: PORT=3001 API_TARGET=http://localhost:8001 node serve-dist.js
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "dist");
const PORT = Number(process.env.PORT || 3001);
const API = new URL(process.env.API_TARGET || "http://localhost:8001");
const TYPES = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".json": "application/json",
  ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon",
  ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2", ".map": "application/json",
};

function send(res, file) {
  const ext = path.extname(file);
  const base = path.basename(file);
  const headers = { "Content-Type": TYPES[ext] || "application/octet-stream" };
  if (base === "manifest.json") headers["Content-Type"] = "application/manifest+json";
  if (base === "sw.js" || base === "index.html" || base === "manifest.json") headers["Cache-Control"] = "no-cache";
  else if (file.includes(`${path.sep}_expo${path.sep}`)) headers["Cache-Control"] = "public, max-age=31536000, immutable";
  if (base === "sw.js") headers["Service-Worker-Allowed"] = "/";
  res.writeHead(200, headers);
  fs.createReadStream(file).pipe(res);
}

http
  .createServer((req, res) => {
    if (req.url.startsWith("/api")) {
      const p = http.request(
        { host: API.hostname, port: API.port, path: req.url, method: req.method, headers: { ...req.headers, host: req.headers.host } },
        (r) => { res.writeHead(r.statusCode, r.headers); r.pipe(res); },
      );
      p.on("error", () => { res.writeHead(502); res.end("backend unavailable"); });
      req.pipe(p);
      return;
    }
    const clean = decodeURIComponent(req.url.split("?")[0]);
    const file = path.normalize(path.join(ROOT, clean));
    if (file.startsWith(ROOT) && fs.existsSync(file) && fs.statSync(file).isFile()) return send(res, file);
    send(res, path.join(ROOT, "index.html"));
  })
  .listen(PORT, "0.0.0.0", () => console.log(`GRIT dist on :${PORT} -> api ${API.href}`));
