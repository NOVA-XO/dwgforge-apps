r"""Локал вэб GUI — эд ангийн хэмжээсийг браузераас оруулж DWG үүсгэнэ.

Гуравдагч этгээдийн багц ХЭРЭГГҮЙ: Python-ы стандарт `http.server` ашиглана.

Яагаад сервер хэрэгтэй вэ: браузер нь аюулгүй байдлын үүднээс локал програм
(AutoCAD) дуудаж чаддаггүй. Тиймээс HTML нь форм үзүүлж, энэ сервер нь
accoreconsole-ыг дуудна.

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe parts3d\\gui.py

Дараа нь браузер дээр:  http://localhost:8765
"""

from __future__ import annotations

import dataclasses
import json
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from parts import CheckValve, Elbow, Flange, Pipe, Reducer, Tee, emit, run  # noqa: E402
from partsan import load_table  # noqa: E402
from zurag import VIEWS, render  # noqa: E402

PORT = 8765
OUTDIR = HERE / "parts"
PREVIEW = OUTDIR / ".preview"

# Формд гарах эд ангиуд. Шинэ эд анги нэмэхэд энд нэг мөр л нэмнэ —
# талбаруудыг нь dataclass-аас автоматаар уншина.
PART_TYPES: dict[str, Any] = {
    "Pipe": Pipe,
    "Elbow": Elbow,
    "Tee": Tee,
    "Reducer": Reducer,
    "Flange": Flange,
    "CheckValve": CheckValve,
}

LABELS = {
    "Pipe": "Хоолой",
    "Elbow": "Тохой",
    "Tee": "Тройник",
    "Reducer": "Шилжилт",
    "Flange": "Фланец",
    "CheckValve": "Буцах хавхлага",
}

FIELD_LABELS = {
    "dn": "DN",
    "dn_small": "Жижиг DN",
    "branch_dn": "Салааны DN",
    "length": "Урт",
    "angle": "Өнцөг",
    "bend_radius": "Гулзайлтын радиус",
    "od": "Гадна диаметр",
    "wall": "Ханын зузаан",
    "run_length": "Гол шугамын урт",
    "branch_length": "Салааны урт",
    "hub_length": "Хүзүүний урт",
    "outer": "Фланецын гадна D",
    "thickness": "Зузаан",
    "bolt_circle": "Болтын тойрог",
    "bolt_hole": "Болтын нүх",
    "bolt_count": "Болтын тоо",
    "face_to_face": "Бие даасан урт (A)",
    "body_od": "Их биеийн гадна D (B)",
    "bore": "Урсгалын нүх",
    "eye": "Өргөх цагираг (1/0)",
    "open_angle": "Нээлтийн өнцөг (0 = хаалттай)",
    "detail": "Гадна нарийн ширийн (1/0)",
}

# Нэг зэрэг зөвхөн нэг AutoCAD ажиллуулна — accoreconsole хүнд бөгөөд
# зэрэг ажиллуулбал лицензийн болон түр файлын мөргөлдөөн үүсгэж болзошгүй.
BUILD_LOCK = threading.Lock()


def part_schema() -> list[dict[str, Any]]:
    """Эд анги бүрийн талбарыг dataclass-аас уншиж, формын тодорхойлолт болгоно."""
    out: list[dict[str, Any]] = []
    for key, cls in PART_TYPES.items():
        fields = []
        for f in dataclasses.fields(cls):
            default = f.default if f.default is not dataclasses.MISSING else None
            # "int | None" гэх мэт заавал биш талбарууд хоосон үлдэж болно —
            # тэр үед хүснэгтээс (hemjees.json) утгыг нь авна.
            optional = default is None
            out_type = "int" if "int" in str(f.type) else "float"
            fields.append(
                {
                    "name": f.name,
                    "label": FIELD_LABELS.get(f.name, f.name),
                    "type": out_type,
                    "default": default,
                    "optional": optional,
                }
            )
        out.append({"key": key, "label": LABELS.get(key, key), "fields": fields})
    return out


def build_part(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """Нэг эд анги үүсгэж, үр дүнг буцаана."""
    cls = PART_TYPES.get(kind)
    if cls is None:
        return {"ok": False, "error": f"үл мэдэгдэх эд анги: {kind}"}

    # Хоосон талбарыг огт дамжуулахгүй — dataclass-ийн өгөгдмөл (None) хэвээр
    # үлдэж, хүснэгтээс утгаа авна.
    clean: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        raw = params.get(f.name)
        if raw is None or raw == "":
            continue
        try:
            clean[f.name] = int(raw) if "int" in str(f.type) else float(raw)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"{FIELD_LABELS.get(f.name, f.name)}: '{raw}' тоо биш"}

    try:
        part = cls(**clean)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}

    table = load_table()
    out = OUTDIR / f"{part.name()}.dwg"
    started = time.monotonic()
    with BUILD_LOCK:
        try:
            ok = run(emit([part], table), out)
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    secs = time.monotonic() - started

    # Дахин барихад хуучин зураг хуучирсан тул устгана.
    for stale in PREVIEW.glob(f"{part.name()}-*.png"):
        stale.unlink(missing_ok=True)

    if not ok or not out.is_file():
        return {"ok": False, "error": "AutoCAD үүсгэж чадсангүй — консолын гаралтыг харна уу"}
    return {
        "ok": True,
        "name": part.name(),
        "path": str(out),
        "size": out.stat().st_size,
        "seconds": round(secs, 1),
    }


def list_parts() -> list[dict[str, Any]]:
    """Үүсгэсэн DWG файлуудыг шинэ нь эхэнд байхаар жагсаана."""
    if not OUTDIR.is_dir():
        return []
    files = sorted(OUTDIR.glob("*.dwg"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.stem, "size": f.stat().st_size, "path": str(f)} for f in files[:40]]


class Handler(BaseHTTPRequestHandler):
    """Маш жижиг API: HTML + 3 эндпойнт."""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Хүсэлт бүрийг лог руу цутгахгүй — консолыг цэвэр байлгана."""

    # -- туслах --------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(
            code,
            json.dumps(obj, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    # -- маршрутууд ----------------------------------------------------
    def do_GET(self) -> None:
        """GET: HTML, тохиргоо, эсвэл үүсгэсэн файлуудын жагсаалт."""
        if self.path in ("/", "/index.html"):
            html = (HERE / "gui.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        elif self.path == "/api/schema":
            table = load_table()
            self._json(
                {
                    "parts": part_schema(),
                    "dn": sorted((int(k) for k in table.dn), key=int),
                    "outdir": str(OUTDIR),
                }
            )
        elif self.path == "/api/parts":
            self._json({"parts": list_parts()})
        elif self.path.startswith("/api/preview"):
            self._preview()
        elif self.path == "/api/views":
            self._json({"views": list(VIEWS)})
        else:
            self._json({"error": "not found"}, 404)

    def _preview(self) -> None:
        """PNG урьдчилсан харагдац. Байхгүй бол AutoCAD-аар нэг удаа гаргана."""
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = (q.get("name") or [""])[0]
        view = (q.get("view") or ["swiso"])[0]
        # Нэрийг цэвэрлэнэ: замын тэмдэгт орвол хавтаснаас гарах эрсдэлтэй.
        bad = not name or "/" in name or chr(92) in name or ".." in name
        if bad or view not in VIEWS:
            self._json({"error": "bad request"}, 400)
            return
        dwg = OUTDIR / f"{name}.dwg"
        if not dwg.is_file():
            self._json({"error": "no such part"}, 404)
            return
        png = PREVIEW / f"{name}-{view}.png"
        if not png.is_file():
            # AutoCAD хүнд тул нэг зэрэг нэг л ажиллуулна.
            with BUILD_LOCK:
                if not png.is_file() and render(dwg, png, view=view) is None:
                    self._json({"error": "render failed"}, 500)
                    return
        self._send(200, png.read_bytes(), "image/png")

    def do_POST(self) -> None:
        """POST /api/build: эд анги үүсгэнэ."""
        if self.path != "/api/build":
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._json({"ok": False, "error": f"буруу JSON: {exc}"}, 400)
            return
        kind = str(payload.get("type", ""))
        params = payload.get("params") or {}
        self._json(build_part(kind, params))


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"dwgforge GUI  ->  {url}")
    print(f"Гаралтын хавтас: {OUTDIR}")
    print("Зогсоох: Ctrl+C\n")
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nзогслоо")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
