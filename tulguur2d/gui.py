r"""Локал вэб GUI — ЭСП каталогийн тулгуурыг сонгож 2D DWG үүсгэнэ.

Гуравдагч этгээдийн багц ХЭРЭГГҮЙ: Python-ы стандарт `http.server` ашиглана.
Сервер зөвхөн 127.0.0.1 дээр сонсох тул AutoCAD дуудах эрх нь локал машинд
үлдэнэ, браузер нь зөвхөн JSON хүсэлт явуулна.

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe tulguur2d\\gui.py

Дараа нь браузер дээр:  http://localhost:8767
"""

from __future__ import annotations

import hashlib
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

from dwgforge import DwgForgeError, render_png  # noqa: E402
from husnegt import neg_huudas  # noqa: E402
from tulguurdata import katalog  # noqa: E402
from tulguursan import ANKER, GAN, JB, SHILJILT, TOGSGOL, ZAVSAR, Tulguur  # noqa: E402
from zurag import bicheh, toim  # noqa: E402

PORT = 8767
OUTDIR = HERE / "zurag"
PREVIEW = OUTDIR / ".preview"

# Нэг зэрэг зөвхөн нэг AutoCAD ажиллуулна. Нэг файл бичих, PNG гаргах, тойм
# хуудас хийх аль аль нь accoreconsole дууддаг тул ижил түгжээгээр хамгаална.
BUILD_LOCK = threading.Lock()

# Багц/тойм ажиллагаа HTTP thread-ийг барихгүй. Харин явцыг энд хадгалж,
# браузер секунд тутам уншина.
YAVTS_LOCK = threading.Lock()
STOP_EVENT = threading.Event()
WORKER: threading.Thread | None = None


def _empty_yavts() -> dict[str, Any]:
    return {
        "running": False,
        "kind": "",
        "done": 0,
        "total": 0,
        "last": "",
        "errors": [],
        "stopped": False,
        "ok": None,
        "message": "",
        "out": "",
        "seconds": 0.0,
        "updated": time.time(),
    }


YAVTS: dict[str, Any] = _empty_yavts()

FIELD_LABELS = {
    "shifr": "Шифр",
    "ner": "Файлын нэр",
    "hutsel": "Хүчдэл",
    "tsep": "Цеп",
    "angilal": "Ангилал",
    "material": "Материал",
    "hev": "Силуэт",
    "undur": "Нийт өндөр",
    "dood": "Доод траверсын өндөр",
    "suuri": "Суурийн өргөн",
    "orgil": "Оройн өргөн",
    "urgun": "Зургийн нийт өргөн",
    "tor": "Траверс",
    "uzuur": "Тросостойк",
    "tatlaga": "Оттяжкийн анкерын зай",
    "hol": "Порталын хөл хоорондын зай",
    "jin": "Масс, цинкгүй",
    "jin_ts": "Масс, цинктэй",
    "shem": "Монтажийн схем",
    "huudas": "Каталогийн лист",
    "utas": "Провод",
    "tros": "Трос",
    "mus": "Гололёдын район",
    "temdeglel": "Тайлбар",
    "batalgaa": "Хэмжээс баталгаатай",
}

ANGILAL_EHLEH = (ZAVSAR, ANKER, TOGSGOL, SHILJILT)
MATERIAL_EHLEH = (GAN, JB)
SOURCE_NAMES = ("tulguursan.py", "tulguurdata.py", "tulguuruud.json", "zurag.py", "tulguur.py")


def _now() -> float:
    """Тест, явцын тооцоонд нэг эх үүсвэртэй цаг ашиглана."""
    return time.time()


def _source_mtime() -> float:
    """Каталог эсвэл зурагч өөрчлөгдвөл хуучин DWG кэш гэж тооцохгүй."""
    stamps = []
    for name in SOURCE_NAMES:
        path = HERE / name
        if path.is_file():
            stamps.append(path.stat().st_mtime)
    return max(stamps, default=0.0)


def _fresh(path: Path, stamp: float) -> bool:
    """`path` байгаа бөгөөд `stamp`-аас шинэ бол кэш хүчинтэй."""
    return path.is_file() and path.stat().st_mtime >= stamp


def _dwg_path(t: Tulguur, *, a3: bool = False) -> Path:
    """Нэг тулгуурын DWG гаралтын зам.

    АЗ хуудас нь ӨӨР файл: хоёулаа нэг нэр рүү бичвэл кэш хоорондоо
    холилдож, хэрэглэгч аль хувилбар нь байгааг мэдэхээ болино.
    """
    return OUTDIR / (f"{t.ner}-A3.dwg" if a3 else f"{t.ner}.dwg")


def _png_path(t: Tulguur, *, a3: bool = False) -> Path:
    """Нэг тулгуурын PNG урьдчилсан зургийн зам."""
    return PREVIEW / (f"{t.ner}-A3.png" if a3 else f"{t.ner}.png")


def _safe_name(raw: str) -> str | None:
    """Query string-ээс ирсэн файлын нэр хавтаснаас гарахгүй эсэхийг шалгана."""
    if not raw or "/" in raw or chr(92) in raw or ".." in raw:
        return None
    return raw


def _unique(vals: list[str], preferred: tuple[str, ...] = ()) -> list[str]:
    """Каталогийн дарааллыг хадгалсан давхардалгүй жагсаалт."""
    seen: set[str] = set()
    out: list[str] = []
    for val in [*preferred, *vals]:
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _int_or_none(raw: object) -> int | None:
    if raw in (None, "", "бүгд", "all"):
        return None
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _str_or_none(raw: object) -> str | None:
    if raw in (None, "", "бүгд", "all"):
        return None
    return str(raw)


def _filters(raw: dict[str, Any]) -> dict[str, Any]:
    """HTML-ээс ирсэн шүүлтүүрийг `Katalog.shuult`-д өгөх хэлбэрт оруулна."""
    return {
        "hutsel": _int_or_none(raw.get("hutsel")),
        "angilal": _str_or_none(raw.get("angilal")),
        "material": _str_or_none(raw.get("material")),
        "tsep": _int_or_none(raw.get("tsep")),
        "hai": str(raw.get("hai") or "").strip(),
    }


def _filtered(raw: dict[str, Any]) -> tuple[Tulguur, ...]:
    kat = katalog()
    return kat.shuult(**_filters(raw))


def _file_state(t: Tulguur) -> dict[str, Any]:
    """Жагсаалтад харуулах гаралтын файлын төлөв."""
    dwg = _dwg_path(t)
    png = _png_path(t)
    dwg_ok = dwg.is_file()
    png_ok = dwg_ok and _fresh(png, dwg.stat().st_mtime)
    return {
        "dwg": dwg_ok,
        "png": png_ok,
        "dwg_size": dwg.stat().st_size if dwg_ok else 0,
        "dwg_mtime": dwg.stat().st_mtime if dwg_ok else 0,
    }


def _tulguur_json(t: Tulguur) -> dict[str, Any]:
    """`Tulguur` dataclass-ийг браузерт шууд хэрэгтэй JSON болгоно."""
    return {
        "shifr": t.shifr,
        "ner": t.ner,
        "hutsel": t.hutsel,
        "tsep": t.tsep,
        "angilal": t.angilal,
        "material": t.material,
        "hev": t.hev,
        "undur": t.undur,
        "dood": t.dood,
        "suuri": t.suuri,
        "orgil": t.orgil,
        "urgun": t.urgun,
        "tor": [{"z": x.z, "zuun": x.zuun, "baruun": x.baruun} for x in t.tor],
        "uzuur": t.uzuur,
        "tatlaga": t.tatlaga,
        "hol": t.hol,
        "jin": t.jin,
        "jin_ts": t.jin_ts,
        "shem": t.shem,
        "huudas": t.huudas,
        "utas": t.utas,
        "tros": t.tros,
        "mus": t.mus,
        "temdeglel": t.temdeglel,
        "batalgaa": t.batalgaa,
        "files": _file_state(t),
    }


def katalog_json() -> dict[str, Any]:
    """Каталогийн жагсаалт, шүүлтүүрийн сонголтууд, гаралтын зам."""
    kat = katalog()
    items = list(kat.buh)
    return {
        "ok": True,
        "niit": len(kat),
        "outdir": str(OUTDIR),
        "preview": str(PREVIEW),
        "hutseluud": list(kat.hutseluud()),
        "angilal": _unique([t.angilal for t in items], ANGILAL_EHLEH),
        "material": _unique([t.material for t in items], MATERIAL_EHLEH),
        "tsep": sorted({t.tsep for t in items}),
        "hev": _unique([t.hev for t in items]),
        "labels": FIELD_LABELS,
        "tulguur": [_tulguur_json(t) for t in items],
    }


def _render_preview_locked(dwg: Path, png: Path, force: bool) -> bool:
    """PNG-г шаардлагатай үед гаргана. Дуудагч `BUILD_LOCK` авсан байна."""
    if not force and _fresh(png, dwg.stat().st_mtime):
        return False
    png.unlink(missing_ok=True)
    render_png(dwg, png, view="top", shade="wireframe", zoom=0.95)
    return True


def build_one(
    t: Tulguur, *, force: bool = False, preview: bool = True, a3: bool = False
) -> dict[str, Any]:
    """Нэг тулгуурын DWG, шаардвал PNG-г кэш харж үүсгэнэ."""
    OUTDIR.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    dwg = _dwg_path(t, a3=a3)
    png = _png_path(t, a3=a3)
    started = time.monotonic()
    made_dwg = False
    made_png = False

    with BUILD_LOCK:
        try:
            stamp = _source_mtime()
            if force or not _fresh(dwg, stamp):
                ok = neg_huudas(t, dwg) if a3 else bicheh(t, dwg, hemjees=True)
                made_dwg = True
                if not ok or not dwg.is_file():
                    return {"ok": False, "error": "AutoCAD DWG үүсгэж чадсангүй"}
                # DWG шинэчлэгдсэн бол хуучин preview-г кэш гэж үзүүлэхгүй.
                png.unlink(missing_ok=True)

            if preview:
                try:
                    made_png = _render_preview_locked(dwg, png, force or made_dwg)
                except DwgForgeError:
                    png.unlink(missing_ok=True)
                    raise
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    secs = time.monotonic() - started
    state = _file_state(t)
    return {
        "ok": True,
        "shifr": t.shifr,
        "name": t.ner,
        "path": str(dwg),
        "a3": a3,
        "preview": f"/api/preview?name={urllib.parse.quote(dwg.stem)}",
        "seconds": round(secs, 1),
        "cached": not made_dwg and (not preview or not made_png),
        "made_dwg": made_dwg,
        "made_png": made_png,
        "files": state,
    }


def _toim_path(items: tuple[Tulguur, ...]) -> Path:
    """Шүүлтүүрийн үр дүнд тогтвортой нэртэй тойм DWG үүсгэнэ."""
    raw = "\n".join(t.shifr for t in items).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    return OUTDIR / f"toim-{len(items)}-{digest}.dwg"


def build_toim(items: tuple[Tulguur, ...], *, force: bool = False) -> dict[str, Any]:
    """Олон тулгуурыг нэг DWG хуудсанд байрлуулна."""
    if not items:
        return {"ok": False, "error": "шүүлтүүрт тохирох тулгуур алга"}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out = _toim_path(items)
    started = time.monotonic()
    made = False
    with BUILD_LOCK:
        try:
            if force or not _fresh(out, _source_mtime()):
                ok = toim(items, out, bagana=6)
                made = True
                if not ok or not out.is_file():
                    return {"ok": False, "error": "тойм DWG үүсгэж чадсангүй"}
        except Exception as exc:
            traceback.print_exc()
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "path": str(out),
        "name": out.stem,
        "count": len(items),
        "seconds": round(time.monotonic() - started, 1),
        "cached": not made,
    }


def _set_yavts(**vals: Any) -> None:
    with YAVTS_LOCK:
        YAVTS.update(vals)
        YAVTS["updated"] = _now()


def yavts_json() -> dict[str, Any]:
    with YAVTS_LOCK:
        data = dict(YAVTS)
        data["errors"] = list(YAVTS.get("errors", []))
        return data


def _worker_running() -> bool:
    worker = WORKER
    return bool(worker and worker.is_alive())


def _start_worker(kind: str, target: Any, *args: Any) -> dict[str, Any]:
    """Багц thread-ийг ганцаар нь эхлүүлнэ."""
    global WORKER
    busy = False
    worker: threading.Thread | None = None
    with YAVTS_LOCK:
        if _worker_running() or YAVTS.get("running"):
            busy = True
        else:
            STOP_EVENT.clear()
            YAVTS.clear()
            YAVTS.update(_empty_yavts())
            YAVTS.update({"running": True, "kind": kind, "message": "эхэлж байна"})
            YAVTS["updated"] = _now()
            worker = threading.Thread(target=target, args=args, daemon=True)
            WORKER = worker
    if busy:
        return {"ok": False, "error": "өөр багц ажиллагаа явж байна", "yavts": yavts_json()}
    if worker is not None:
        worker.start()
    return {"ok": True, "yavts": yavts_json()}


def _batch_worker(items: tuple[Tulguur, ...], force: bool, a3: bool = False) -> None:
    """Одоогийн шүүлтүүрийн бүх тулгуурыг тус тусад нь DWG болгоно."""
    started = time.monotonic()
    errors: list[str] = []
    _set_yavts(total=len(items), done=0, message="DWG багц үүсгэж байна")
    try:
        for idx, t in enumerate(items, 1):
            if STOP_EVENT.is_set():
                _set_yavts(stopped=True, message="зогсоох хүсэлт авсан")
                break
            _set_yavts(last=t.shifr)
            result = build_one(t, force=force, preview=False, a3=a3)
            if not result.get("ok"):
                errors.append(f"{t.shifr}: {result.get('error', 'тодорхойгүй алдаа')}")
            _set_yavts(done=idx, errors=errors[-30:])
    except Exception as exc:
        traceback.print_exc()
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        stopped = STOP_EVENT.is_set()
        msg = "зогссон" if stopped else "дууссан"
        _set_yavts(
            running=False,
            ok=(not stopped and not errors),
            stopped=stopped,
            errors=errors[-30:],
            message=msg,
            seconds=round(time.monotonic() - started, 1),
        )


def _toim_worker(items: tuple[Tulguur, ...], force: bool) -> None:
    """Тойм хуудсыг тусдаа thread дээр үүсгэнэ."""
    started = time.monotonic()
    errors: list[str] = []
    _set_yavts(total=1, done=0, last=f"{len(items)} тулгуур", message="тойм хуудас үүсгэж байна")
    try:
        if STOP_EVENT.is_set():
            _set_yavts(stopped=True, message="зогсоох хүсэлт авсан")
        else:
            result = build_toim(items, force=force)
            if result.get("ok"):
                _set_yavts(done=1, out=result.get("path", ""))
            else:
                errors.append(str(result.get("error", "тодорхойгүй алдаа")))
    except Exception as exc:
        traceback.print_exc()
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        stopped = STOP_EVENT.is_set()
        msg = "зогссон" if stopped else "дууссан"
        _set_yavts(
            running=False,
            ok=(not stopped and not errors),
            stopped=stopped,
            errors=errors[-30:],
            message=msg,
            seconds=round(time.monotonic() - started, 1),
        )


class Handler(BaseHTTPRequestHandler):
    """Маш жижиг API: HTML, каталог, зураг үүсгэх, явц унших."""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Хүсэлт бүрийг консол руу цутгахгүй."""

    # -- туслах ------------------------------------------------------------
    def _send(
        self, code: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, val in (extra or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _path(self) -> str:
        return urllib.parse.unquote(urllib.parse.urlparse(self.path).path)

    def _query(self) -> dict[str, list[str]]:
        return urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query, encoding="utf-8")

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}

    # -- маршрутууд --------------------------------------------------------
    def do_GET(self) -> None:
        """GET хүсэлт бүр хамгаалалттай: дотоод алдаа сервер унагахгүй."""
        try:
            self._do_GET()
        except Exception as exc:
            traceback.print_exc()
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 500)

    def _do_GET(self) -> None:
        path = self._path()
        if path in ("/", "/index.html"):
            self._send(200, (HERE / "gui.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/katalog":
            self._json(katalog_json())
        elif path == "/api/yavts":
            self._json({"ok": True, "yavts": yavts_json()})
        elif path == "/api/preview":
            self._preview()
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    def _preview(self) -> None:
        """Бэлэн DWG-ийн PNG харагдац. PNG хуучирсан бол AutoCAD-аар шинэчилнэ."""
        q = self._query()
        name = _safe_name((q.get("name") or [""])[0])
        if name is None:
            self._json({"ok": False, "error": "bad request"}, 400)
            return
        dwg = OUTDIR / f"{name}.dwg"
        png = PREVIEW / f"{name}.png"
        if not dwg.is_file():
            self._json({"ok": False, "error": "DWG олдсонгүй"}, 404)
            return
        PREVIEW.mkdir(parents=True, exist_ok=True)
        with BUILD_LOCK:
            try:
                if not _fresh(png, dwg.stat().st_mtime):
                    png.unlink(missing_ok=True)
                    render_png(dwg, png, view="top", shade="wireframe", zoom=0.95)
                body = png.read_bytes()
            except DwgForgeError as exc:
                png.unlink(missing_ok=True)
                self._json({"ok": False, "error": f"зураг гаргаж чадсангүй: {exc}"}, 500)
                return
        self._send(200, body, "image/png")

    def do_POST(self) -> None:
        """POST хүсэлт бүр хамгаалалттай: traceback хэвлээд JSON алдаа буцаана."""
        try:
            self._do_POST()
        except Exception as exc:
            traceback.print_exc()
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 500)

    def _do_POST(self) -> None:
        path = self._path()
        try:
            payload = self._read_json()
        except json.JSONDecodeError as exc:
            self._json({"ok": False, "error": f"буруу JSON: {exc}"}, 400)
            return
        if path == "/api/zurag":
            self._post_zurag(payload)
        elif path in ("/api/багц", "/api/bagts"):
            self._post_bagts(payload)
        elif path == "/api/toim":
            self._post_toim(payload)
        elif path == "/api/zogs":
            STOP_EVENT.set()
            self._json({"ok": True, "yavts": yavts_json()})
        else:
            self._json({"ok": False, "error": "not found"}, 404)

    def _post_zurag(self, payload: dict[str, Any]) -> None:
        shifr = str(payload.get("shifr") or "").strip()
        if not shifr:
            self._json({"ok": False, "error": "шифр хоосон байна"}, 400)
            return
        try:
            t = katalog().ol(shifr)
        except KeyError as exc:
            self._json({"ok": False, "error": str(exc)}, 404)
            return
        result = build_one(
            t, force=bool(payload.get("force")), preview=True, a3=bool(payload.get("a3"))
        )
        if result.get("ok"):
            result["tulguur"] = _tulguur_json(t)
        self._json(result, 200 if result.get("ok") else 500)

    def _post_bagts(self, payload: dict[str, Any]) -> None:
        raw = payload.get("filters") if isinstance(payload.get("filters"), dict) else payload
        items = _filtered(raw)
        if not items:
            self._json({"ok": False, "error": "шүүлтүүрт тохирох тулгуур алга"}, 400)
            return
        result = _start_worker(
            "bagts", _batch_worker, items, bool(payload.get("force")), bool(payload.get("a3"))
        )
        self._json(result, 200 if result.get("ok") else 409)

    def _post_toim(self, payload: dict[str, Any]) -> None:
        raw = payload.get("filters") if isinstance(payload.get("filters"), dict) else payload
        items = _filtered(raw)
        if not items:
            self._json({"ok": False, "error": "шүүлтүүрт тохирох тулгуур алга"}, 400)
            return
        result = _start_worker("toim", _toim_worker, items, bool(payload.get("force")))
        self._json(result, 200 if result.get("ok") else 409)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"tulguur2d GUI  ->  {url}")
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
