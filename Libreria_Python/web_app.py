import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from Load import load_dataframe_from_path
from Smart_Assistant import OpenAssistantEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "Datos"
SUPPORTED_EXTS = {".csv", ".otus", ".txt", ".meta", ".taxonomy"}
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


APP_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Microbiota Workbench Web</title>
  <style>
    :root {
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #5d6673;
      --line: #d8dee8;
      --accent: #245d8f;
      --accent-soft: #e7f0f8;
      --warn: #fff2b8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    header {
      padding: 18px 24px 10px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    .subtitle { color: var(--muted); font-size: 14px; }
    main {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      gap: 16px;
      padding: 16px 24px 24px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    h2 { margin: 0 0 12px; font-size: 16px; }
    label { display: block; margin: 10px 0 5px; font-weight: 600; font-size: 13px; }
    select, textarea, input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 130px; resize: vertical; }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid #bed4e6;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 10px;
    }
    .dataset {
      border-bottom: 1px solid var(--line);
      padding: 8px 0;
      font-size: 13px;
    }
    .dataset:last-child { border-bottom: 0; }
    .muted { color: var(--muted); }
    .answer {
      white-space: pre-wrap;
      line-height: 1.45;
      min-height: 240px;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      max-height: 320px;
      overflow: auto;
    }
    .hint {
      background: var(--warn);
      border: 1px solid #e2c96d;
      border-radius: 6px;
      padding: 8px;
      color: #5a4200;
      font-size: 13px;
      margin-bottom: 10px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Microbiota Workbench Web</h1>
    <div class="subtitle">Prototipo paralelo para probar una interfaz mas amable con asistente estadistico.</div>
  </header>
  <main>
    <section>
      <h2>Datasets</h2>
      <div class="hint">Esta version carga archivos desde la carpeta Datos del proyecto. La app Tkinter sigue intacta.</div>
      <button class="secondary" onclick="loadDatasets()">Actualizar datasets</button>
      <div id="datasets" style="margin-top: 10px;"></div>
    </section>
    <section>
      <h2>Asistente</h2>
      <label for="dataset">Dataset</label>
      <select id="dataset"></select>
      <label for="question">Pregunta</label>
      <textarea id="question">Quiero comparar glucosa entre grupos de sexo. Que prueba y parametros uso?</textarea>
      <label for="model">Modelo Ollama local opcional</label>
      <input id="model" value="qwen2.5:3b" />
      <label><input id="useOllama" type="checkbox" style="width:auto;" /> Usar Ollama local</label>
      <div class="actions">
        <button onclick="askAssistant()">Preguntar</button>
        <button class="secondary" onclick="analyzeDatasets()">Analizar datasets</button>
      </div>
      <h2 style="margin-top: 18px;">Respuesta</h2>
      <div id="answer" class="answer muted">Carga datasets o haz una pregunta.</div>
      <h2 style="margin-top: 18px;">Parametros sugeridos</h2>
      <pre id="suggestions">{}</pre>
    </section>
  </main>
  <script>
    async function loadDatasets() {
      const res = await fetch('/api/datasets');
      const data = await res.json();
      const box = document.getElementById('datasets');
      const select = document.getElementById('dataset');
      box.innerHTML = '';
      select.innerHTML = '';
      for (const item of data.datasets) {
        const div = document.createElement('div');
        div.className = 'dataset';
        div.innerHTML = `<strong>${item.dataset}</strong><br><span class="muted">${item.rows} filas x ${item.columns} columnas &middot; ${item.numeric} numericas &middot; ${item.categorical} categoricas</span>`;
        box.appendChild(div);
        const opt = document.createElement('option');
        opt.value = item.dataset;
        opt.textContent = item.dataset;
        select.appendChild(opt);
      }
    }
    async function askAssistant() {
      document.getElementById('answer').textContent = 'Pensando...';
      const payload = {
        question: document.getElementById('question').value,
        dataset: document.getElementById('dataset').value,
        use_ollama: document.getElementById('useOllama').checked,
        model: document.getElementById('model').value
      };
      const res = await fetch('/api/ask', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      const data = await res.json();
      document.getElementById('answer').textContent = data.text || data.error || '';
      document.getElementById('suggestions').textContent = JSON.stringify(data.suggestions || {}, null, 2);
    }
    async function analyzeDatasets() {
      document.getElementById('answer').textContent = 'Revisando datasets...';
      const res = await fetch('/api/analyze', {method: 'POST'});
      const data = await res.json();
      document.getElementById('answer').textContent = data.text || data.error || '';
      document.getElementById('suggestions').textContent = JSON.stringify(data.suggestions || {}, null, 2);
    }
    loadDatasets();
  </script>
</body>
</html>"""


class WebState:
    def __init__(self):
        self.dfs = {}
        self.engine = OpenAssistantEngine(self.dfs)

    def load_default_datasets(self):
        if self.dfs:
            return
        if not DATA_DIR.exists():
            return
        for path in sorted(DATA_DIR.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
                continue
            try:
                self.dfs[path.stem] = load_dataframe_from_path(path)
            except Exception:
                continue
        self.engine.update_dfs(self.dfs)

    def dataset_summary(self):
        self.load_default_datasets()
        if not self.dfs:
            return []
        return self.engine.inspector.summarize_all().to_dict("records")


STATE = WebState()


class AppHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_html(APP_HTML)
        if parsed.path == "/api/datasets":
            return self._send_json({"datasets": STATE.dataset_summary()})
        return self._send_json({"error": "Ruta no encontrada"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_json()
        STATE.load_default_datasets()

        if parsed.path == "/api/ask":
            try:
                response = STATE.engine.answer(
                    payload.get("question", ""),
                    selected_dataset=payload.get("dataset") or None,
                    use_ollama=bool(payload.get("use_ollama")),
                    model=payload.get("model") or "qwen2.5:3b",
                )
                return self._send_response_object(response)
            except Exception as exc:
                return self._send_json({"error": str(exc)}, status=500)

        if parsed.path == "/api/analyze":
            try:
                response = STATE.engine.analyze_datasets()
                return self._send_response_object(response)
            except Exception as exc:
                return self._send_json({"error": str(exc)}, status=500)

        return self._send_json({"error": "Ruta no encontrada"}, status=404)

    def log_message(self, _format, *_args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _send_response_object(self, response):
        return self._send_json({
            "text": response.text,
            "target_analysis": response.target_analysis,
            "suggestions": response.suggestions,
            "warnings": response.warnings,
            "context": response.context,
        })

    def _send_html(self, html, status=200):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(host=DEFAULT_HOST, port=DEFAULT_PORT):
    server = ThreadingHTTPServer((host, int(port)), AppHandler)
    print(f"Microbiota Workbench Web: http://{host}:{port}")
    print("Presiona Ctrl+C para detener.")
    server.serve_forever()


if __name__ == "__main__":
    run()
