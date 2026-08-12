"""
Stage F — new problem statement: render Russian markdown reports to a PDF package.

Pipeline: Markdown -> self-built HTML (+CSS, figures as base64) -> PDF via headless
Edge/Chrome. Primary PDF path uses the DevTools protocol (CDP) Page.printToPDF with a
page-number footer; a CLI --print-to-pdf fallback is used if CDP is unavailable.

No MD/LAMMPS is launched. This script only formats existing reports.
Run: <venv>\\python.exe scripts\\stageF_render_new_statement_pdf.py
"""
import os, re, sys, json, time, base64, socket, struct, shutil, tempfile, mimetypes
import subprocess, http.client, urllib.parse

PROJ = r"C:\Users\dille\Documents\ilua-system\projects\physics_md_al_fe"
REPORTS = os.path.join(PROJ, "docs", "reports")
FIGDIR = os.path.join(REPORTS, "figures")
PDFDIR = os.path.join(REPORTS, "pdf")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# ---------------------------------------------------------------- markdown -> html

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def inline(text):
    codes = []
    def _c(m):
        codes.append(m.group(1))
        return "\x00C%d\x00" % (len(codes) - 1)
    text = re.sub(r"`([^`]+)`", _c, text)
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    for i, c in enumerate(codes):
        text = text.replace("\x00C%d\x00" % i, "<code>%s</code>" % esc(c))
    return text

def _split_row(s):
    s = s.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]

def _is_table_sep(s):
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", s))

def _aligns(sep):
    out = []
    for c in _split_row(sep):
        c = c.strip()
        l, r = c.startswith(":"), c.endswith(":")
        out.append("center" if (l and r) else "right" if r else "left")
    return out

def _table(header, aligns, rows):
    def al(i):
        return aligns[i] if i < len(aligns) else "left"
    h = "<thead><tr>" + "".join(
        "<th style='text-align:%s'>%s</th>" % (al(i), inline(c)) for i, c in enumerate(header)
    ) + "</tr></thead>"
    b = "<tbody>" + "".join(
        "<tr>" + "".join(
            "<td style='text-align:%s'>%s</td>" % (al(i), inline(c)) for i, c in enumerate(r)
        ) + "</tr>" for r in rows
    ) + "</tbody>"
    return "<table>%s%s</table>" % (h, b)

def _list(block):
    items = []
    for ln in block:
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln)
        if m:
            indent = len(m.group(1).expandtabs(4))
            typ = "ol" if re.match(r"^\d+\.$", m.group(2)) else "ul"
            items.append({"indent": indent, "type": typ, "content": inline(m.group(3).strip())})
        elif items:
            items[-1]["content"] += " " + inline(ln.strip())
    out, stack = [], []
    for it in items:
        ind = it["indent"]
        while stack and ind < stack[-1][0]:
            out.append("</li></%s>" % stack[-1][1]); stack.pop()
        if not stack or ind > stack[-1][0]:
            out.append("<%s>" % it["type"]); stack.append((ind, it["type"]))
        else:
            out.append("</li>")
        out.append("<li>%s" % it["content"])
    while stack:
        out.append("</li></%s>" % stack[-1][1]); stack.pop()
    return "".join(out)

def md_to_html(md, drop_first_h1=True):
    lines = md.split("\n")
    out = []
    i, n = 0, len(lines)
    first_h1_dropped = False
    while i < n:
        line = lines[i]
        if line.strip() == "":
            i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            if lvl == 1 and drop_first_h1 and not first_h1_dropped:
                first_h1_dropped = True; i += 1; continue
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2).strip()), lvl)); i += 1; continue
        if re.match(r"^---+\s*$", line):
            out.append("<hr/>"); i += 1; continue
        if line.strip().startswith("```"):
            i += 1; buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre class='formula'>%s</pre>" % esc("\n".join(buf))); continue
        if "|" in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            header = _split_row(line); aligns = _aligns(lines[i + 1]); i += 2
            rows = []
            while i < n and "|" in lines[i] and lines[i].strip() != "":
                rows.append(_split_row(lines[i])); i += 1
            out.append(_table(header, aligns, rows)); continue
        if re.match(r"^(\s*)([-*]|\d+\.)\s+", line):
            block = []
            while i < n and (re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]) or
                             (lines[i].strip() != "" and lines[i].startswith("   "))):
                block.append(lines[i]); i += 1
            out.append(_list(block)); continue
        para = [line]; i += 1
        while i < n and lines[i].strip() != "" and \
                not re.match(r"^(#{1,6})\s", lines[i]) and \
                not lines[i].strip().startswith("```") and \
                not re.match(r"^---+\s*$", lines[i]) and \
                not re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]) and \
                not ("|" in lines[i] and i + 1 < n and _is_table_sep(lines[i + 1])):
            para.append(lines[i]); i += 1
        out.append("<p>" + "<br/>".join(inline(p.strip()) for p in para) + "</p>")
    return "\n".join(out)

# ---------------------------------------------------------------- assets / css

def data_uri(path):
    with open(path, "rb") as f:
        b = f.read()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return "data:%s;base64,%s" % (mime, base64.b64encode(b).decode())

CSS = """
@page { size: A4; margin: 20mm; }
html, body { font-family: Arial, "Segoe UI", "DejaVu Sans", sans-serif; font-size: 11pt;
  line-height: 1.45; color: #1a1a1a; margin: 0; }
h1 { font-size: 20pt; margin: 0.6em 0 0.3em; color: #0b3d5c; }
h2 { font-size: 15pt; margin: 1.05em 0 0.4em; color: #0b3d5c; border-bottom: 1px solid #cbd6df;
  padding-bottom: 2px; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin: 0.8em 0 0.3em; color: #134b6e; page-break-after: avoid; }
p { margin: 0.35em 0; text-align: justify; }
code { font-family: Consolas, "DejaVu Sans Mono", monospace; background: #f2f4f7; padding: 0 3px;
  border-radius: 3px; font-size: 9.5pt; }
pre.formula { font-family: Consolas, "DejaVu Sans Mono", monospace; background: #f5f7fa;
  border: 1px solid #d9e0e7; border-left: 3px solid #3a7ca5; padding: 8px 10px; font-size: 10pt;
  white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; margin: 0.5em 0; }
table { width: 100%; border-collapse: collapse; margin: 0.6em 0; font-size: 9.5pt;
  page-break-inside: avoid; }
th, td { border: 1px solid #b9c4cf; padding: 4px 7px; vertical-align: top; }
th { background: #e8eef3; }
tr:nth-child(even) td { background: #fafbfc; }
tr { page-break-inside: avoid; }
img { max-width: 100%; height: auto; display: block; margin: 6px auto; }
ul, ol { margin: 0.3em 0 0.3em 1.3em; padding-left: 0.6em; }
li { margin: 0.15em 0; }
hr { border: none; border-top: 1px solid #dfe5ea; margin: 0.8em 0; }
.title-page { text-align: center; padding-top: 55mm; page-break-after: always; }
.title-page h1 { font-size: 26pt; border: none; color: #0b3d5c; }
.subtitle { font-size: 14pt; color: #40566a; margin-top: 10px; }
.meta { margin-top: 16mm; font-size: 11pt; color: #333; }
.status { margin-top: 8mm; font-size: 10.5pt; color: #2a2a2a; font-style: italic; }
.pagebreak { page-break-before: always; }
.keybox { background: #eef4f8; border: 1px solid #cfe0ea; padding: 6px 10px; margin: 0.6em 0; }
.warn { background: #fff4e5; border: 1px solid #f0c98b; border-left: 4px solid #e08b00;
  padding: 8px 10px; margin: 0.8em 0; font-weight: bold; }
figure { margin: 8px 0 14px; page-break-inside: avoid; }
figcaption { font-size: 9pt; color: #444; margin-top: 4px; text-align: left; }
"""

FIGURES = [
    ("stageF_cpu_results_delta_sigma_vm_last20.png",
     "Профиль Δσ_vm(r) = eps00194 − eps0000, окно last20. Пик +578.422 MPa у границы (r≈1 Å) с быстрым спадом к шумовому уровню 133.527 MPa. Поддерживает вывод о сильной локализации передачи напряжения."),
    ("stageF_cpu_results_sigma_zz_last20.png",
     "Профиль σzz(r) для eps0000 и eps00194. Иллюстрирует нормальную компоненту; Δσzz на 50 Å = −69.071 MPa. Поддерживает вывод, что σzz не доминирует в пике von Mises."),
    ("stageF_cpu_results_sigma_vm_last20.png",
     "Полный σ_vm(r) для обоих случаев. Показывает интерфейсный фон и общий уровень напряжений; абсолютные значения — local virial stress proxy, не калиброванный continuum stress."),
    ("stageF_cpu_results_sigma_vm_p95_last20.png",
     "p95 σ_vm(r) — верхний перцентиль на атом. Демонстрирует шумность atom-level proxy: использовать только для формы профиля, не для абсолютных MPa."),
    ("stageF_cpu_results_delta_defect_nonfcc_final.png",
     "Профиль Δ доли non-FCC (final кадр). Максимум |Δ| = 0.035964 у r≈3 Å — слабый локальный интерфейсный structural-отклик, не доказательство пластичности."),
    ("stageF_cpu_results_defect_other_final.png",
     "Доля OTHER (final) по r. У границы велика в обоих случаях (структура самой границы/свободной поверхности); DXA line length = 0 Å."),
]

FIVE_NUMBERS = [
    ("Peak Δσ_vm mean", "+578.422 MPa", "максимум добавочного von Mises proxy у interface"),
    ("r пика Δσ_vm", "1 Å (bin 0–2 Å)", "положение пика — первый слой у границы"),
    ("Meaningful Δσ_vm above noise", "4 Å", "добавочный сигнал выше шума только в первых ~4 Å"),
    ("Δσ_vm на 50 / 100 Å", "−20.441 / +30.160 MPa", "на 50–100 Å эффект мал относительно пика"),
    ("DXA final line length", "0 Å; residual not_confirmed", "развитые дислокации не обнаружены; остаточная пластичность не подтверждена"),
]

FORMULAS = [
    "1)  σ_m = λ_m · B",
    "2)  ε ≈ σ / E",
    "3)  ΔQ(r) = Q_eps00194(r) − Q_eps0000(r)",
    "4)  r = z − z_interface",
    "5)  σ_vm = sqrt(0.5·[(σxx−σyy)² + (σyy−σzz)² + (σzz−σxx)² + 6(σxy² + σyz² + σxz²)])",
    "6)  f_yield(r) = N(σ_vm > 120 MPa) / N_total",
    "7)  f_HCP(r) = N_HCP(r) / N_Al(r)",
    "8)  Δf_OTHER(r) = f_OTHER,eps00194(r) − f_OTHER,eps0000(r)",
]

def section_nav(md):
    secs = re.findall(r"^##\s+(.*)$", md, re.M)
    lis = "".join("<li>%s</li>" % inline(s.strip()) for s in secs)
    return "<ul style='list-style:none;margin-left:0.4em;padding-left:0'>%s</ul>" % lis

def five_numbers_table():
    rows = "".join(
        "<tr><td>%s</td><td style='text-align:right'><strong>%s</strong></td><td>%s</td></tr>"
        % (esc(a), esc(b), esc(c)) for a, b, c in FIVE_NUMBERS)
    return ("<table><thead><tr><th>Показатель</th><th style='text-align:right'>Значение</th>"
            "<th>Интерпретация</th></tr></thead><tbody>%s</tbody></table>" % rows)

def formulas_block():
    return "<pre class='formula'>%s</pre>" % esc("\n".join(FORMULAS))

def figures_html(embed=True):
    out = ["<div class='pagebreak'></div>", "<h2>Приложение. Иллюстрации</h2>"]
    for name, cap in FIGURES:
        path = os.path.join(FIGDIR, name)
        if not os.path.exists(path):
            out.append("<p><em>[figure отсутствует: %s]</em></p>" % esc(name)); continue
        src = data_uri(path) if embed else ("figures/" + name)
        out.append("<figure><img src='%s' alt='%s'/><figcaption>%s</figcaption></figure>"
                   % (src, esc(name), inline(cap)))
    return "\n".join(out)

def wrap_html(title, body):
    return ("<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
            "<title>%s</title><style>%s</style></head><body>%s</body></html>"
            % (esc(title), CSS, body))

# ---------------------------------------------------------------- build docs

def build_full_html():
    md = open(os.path.join(REPORTS, "stageF_new_problem_statement_report_ru.md"), encoding="utf-8").read()
    title = "Отчёт по новой постановке расчёта Fe₄Al₁₃/Al"
    front = (
        "<div class='title-page'>"
        "<h1>%s</h1>"
        "<div class='subtitle'>Локальная модель границы, напряжённый слой и структурные индикаторы</div>"
        "<div class='meta'>Дата генерации: 2026-07-06</div>"
        "<div class='status'>CPU production pair completed clean; GPU production не используется в физическом выводе.</div>"
        "</div>"
    ) % title
    front += "<h2>Краткое содержание</h2>" + section_nav(md)
    front += "<h2>Пять главных чисел</h2>" + five_numbers_table()
    front += "<h2>Ключевые формулы</h2>" + formulas_block()
    front += ("<div class='warn'>Высокий σ_vm сам по себе не является доказательством "
              "пластической деформации.</div>")
    front += ("<p><strong>Итог:</strong> передача напряжения подтверждена; "
              "пластическая деформация не подтверждена; развитые дислокационные линии "
              "не обнаружены (DXA line length = 0 Å).</p>")
    front += "<div class='pagebreak'></div>"
    body = md_to_html(md, drop_first_h1=True)
    body += figures_html(embed=True)
    return wrap_html(title, front + body)

def build_short_html():
    md = open(os.path.join(REPORTS, "stageF_new_problem_statement_short_ru.md"), encoding="utf-8").read()
    title = "Fe₄Al₁₃/Al — новая постановка: короткая версия"
    head = ("<h1>%s</h1>"
            "<div class='status'>CPU production pair completed clean; GPU не используется в физическом выводе. "
            "Дата: 2026-07-06.</div>") % title
    body = md_to_html(md, drop_first_h1=True)
    return wrap_html(title, head + body)

def build_figures_appendix_html():
    title = "Fe₄Al₁₃/Al — приложение иллюстраций"
    head = ("<h1>%s</h1><p>Иллюстрации к отчёту по новой постановке. Подписи не содержат "
            "утверждений о доказанной пластичности.</p>") % title
    figs = []
    for name, cap in FIGURES:
        path = os.path.join(FIGDIR, name)
        if not os.path.exists(path):
            figs.append("<p><em>[figure отсутствует: %s]</em></p>" % esc(name)); continue
        figs.append("<figure><img src='%s' alt='%s'/><figcaption>%s</figcaption></figure>"
                    % (data_uri(path), esc(name), inline(cap)))
    return wrap_html(title, head + "\n".join(figs))

# ---------------------------------------------------------------- CDP websocket

class WS:
    def __init__(self, url):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET %s HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nOrigin: http://127.0.0.1\r\n\r\n"
               % (u.path, u.hostname, u.port, key))
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("ws handshake closed")
            buf += chunk
        if b" 101 " not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("ws handshake failed: " + buf[:120].decode("latin1"))
        self._rest = buf.split(b"\r\n\r\n", 1)[1]

    def _recv_exact(self, n):
        data = self._rest[:n]; self._rest = self._rest[n:]
        while len(data) < n:
            chunk = self.sock.recv(min(65536, n - len(data)))
            if not chunk:
                raise RuntimeError("socket closed")
            data += chunk
        return data

    def _send(self, opcode, payload):
        header = bytearray([0x80 | opcode])
        ln = len(payload); mask = os.urandom(4)
        if ln < 126:
            header.append(0x80 | ln)
        elif ln < 65536:
            header.append(0x80 | 126); header += struct.pack(">H", ln)
        else:
            header.append(0x80 | 127); header += struct.pack(">Q", ln)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def _frame(self):
        b0 = self._recv_exact(1)[0]; b1 = self._recv_exact(1)[0]
        fin = b0 & 0x80; opcode = b0 & 0x0f; masked = b1 & 0x80; ln = b1 & 0x7f
        if ln == 126:
            ln = struct.unpack(">H", self._recv_exact(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", self._recv_exact(8))[0]
        mk = self._recv_exact(4) if masked else None
        payload = self._recv_exact(ln)
        if mk:
            payload = bytes(b ^ mk[i % 4] for i, b in enumerate(payload))
        return fin, opcode, payload

    def _message(self):
        data = b""
        while True:
            fin, opcode, payload = self._frame()
            if opcode == 0x8:
                raise RuntimeError("ws closed by server")
            if opcode == 0x9:
                self._send(0xA, payload); continue
            if opcode == 0xA:
                continue
            data += payload
            if fin:
                break
        return data.decode("utf-8", errors="replace")

    def call(self, mid, method, params=None):
        self._send(0x1, json.dumps({"id": mid, "method": method, "params": params or {}}).encode())
        deadline = time.time() + 120
        while time.time() < deadline:
            msg = json.loads(self._message())
            if msg.get("id") == mid:
                return msg
        raise RuntimeError("CDP timeout for %s" % method)

def _http_json(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request("GET", path)
    return json.loads(conn.getresponse().read())

PDF_PARAMS = {
    "landscape": False, "displayHeaderFooter": True, "printBackground": True,
    "paperWidth": 8.27, "paperHeight": 11.69,
    "marginTop": 0.79, "marginBottom": 0.79, "marginLeft": 0.79, "marginRight": 0.79,
    "headerTemplate": "<span></span>",
    "footerTemplate": ("<div style='width:100%;font-size:9px;color:#666;text-align:center;"
                       "padding:0 10mm;'>Стр. <span class='pageNumber'></span> / "
                       "<span class='totalPages'></span></div>"),
    "preferCSSPageSize": False,
}

def cdp_print(ws_url, out_pdf):
    """Connect to an already-launched browser page target and print it to PDF."""
    ws = WS(ws_url)
    ws.call(1, "Page.enable")
    time.sleep(1.2)  # settle fonts/images (page already loaded on launch)
    res = ws.call(2, "Page.printToPDF", PDF_PARAMS)
    if "result" not in res or "data" not in res["result"]:
        raise RuntimeError("printToPDF error: " + json.dumps(res)[:200])
    with open(out_pdf, "wb") as f:
        f.write(base64.b64decode(res["result"]["data"]))
    return os.path.getsize(out_pdf)

# ---------------------------------------------------------------- main

DOCS = [
    ("stageF_new_problem_statement_report_ru.html",
     "stageF_new_problem_statement_report_ru.pdf", build_full_html),
    ("stageF_new_problem_statement_short_ru.html",
     "stageF_new_problem_statement_short_ru.pdf", build_short_html),
    ("stageF_new_problem_statement_figures_appendix_ru.html",
     "stageF_new_problem_statement_figures_appendix_ru.pdf", build_figures_appendix_html),
]

def build_only():
    os.makedirs(PDFDIR, exist_ok=True)
    out = []
    for html_name, pdf_name, builder in DOCS:
        html_path = os.path.join(PDFDIR, html_name)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(builder())
        out.append({"html": html_name, "pdf": pdf_name,
                    "html_path": html_path,
                    "html_bytes": os.path.getsize(html_path)})
    print(json.dumps({"outputs": out}, ensure_ascii=False, indent=2))

def main():
    args = sys.argv[1:]
    if args and args[0] == "printpdf":
        size = cdp_print(args[1], args[2])
        print(json.dumps({"pdf": args[2], "pdf_bytes": size}, ensure_ascii=False))
        return
    build_only()

if __name__ == "__main__":
    main()
