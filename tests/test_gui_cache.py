r"""GUI-ийн кэшийн зан төлөв — AutoCAD ХЭРЭГГҮЙ.

Экспортлогчийг аажим бичдэг хуурамчаар сольж, зэрэгцээ хүсэлтүүдийг бодитоор
явуулна. Эдгээр тест бүр нэг тодорхой алдааг хамгаална; тайлбарт нь алдаа
ямар байсныг бичсэн — учир нь буруу хариулт энд алдаа өгдөггүй, зүгээр
хагас файл болж хүрдэг.
"""

from __future__ import annotations

import dataclasses
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import gui
import pytest

# Хуурамч мешийн хэмжээ: хоёртын STL нь 84 + 50*n байт.
TRIANGLES = 200
FULL_STL = 84 + 50 * TRIANGLES
CHUNKS = 6

# PNG-ийн хувьд агуулга нь хамаагүй, зөвхөн урт нь чухал.
FULL_PNG = 4096


def _stl_bytes() -> bytes:
    body = b"\x00" * 80 + TRIANGLES.to_bytes(4, "little") + b"\xab" * (50 * TRIANGLES)
    assert len(body) == FULL_STL
    return body


class Server:
    """Түр порт дээр асаасан GUI, түүнд хандах туслахуудтай."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), gui.Handler)
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._thread.start()

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str) -> tuple[int, bytes, dict[str, str]]:
        """Хариуг (код, бие, толгойнууд) болгож буцаана. Алдаа ч гэсэн бие авчирна."""
        try:
            with urllib.request.urlopen(self.url(path), timeout=60) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Server]:
    """Гаралтын хавтсыг түр хавтас руу чиглүүлсэн, асаалттай GUI."""
    monkeypatch.setattr(gui, "OUTDIR", tmp_path)
    monkeypatch.setattr(gui, "PREVIEW", tmp_path / ".preview")
    (tmp_path / ".preview").mkdir()
    server = Server(tmp_path)
    try:
        yield server
    finally:
        server.close()


def _part(tmp_path: Path, name: str = "Pipe-DN100-L200") -> str:
    """Зурагт зөвхөн БАЙХ шаардлагатай — экспортлогчийг хуурамчаар солино."""
    (tmp_path / f"{name}.dwg").write_bytes(b"not a real dwg")
    return name


class Gate:
    """Экспортын дундуур зогсоож, тэр агшинд өөр хүсэлт оруулах боломж."""

    def __init__(self) -> None:
        self.partial = threading.Event()  # файл үүсээд хагас бичигдсэн
        self.release = threading.Event()  # цааш бичихийг зөвшөөрөх
        self.calls = 0


def _slow_writer(gate: Gate, payload: bytes) -> Any:
    """AutoCAD-ыг дуурайна: эцсийн зам руу ШУУД, аажим бичнэ.

    Сан нь яг үүнийг хийдэг — түр файл ашиглаад нэрлэдэггүй. Тиймээс файл нь
    бүрэн бэлэн болохоос ӨМНӨ дискэн дээр харагдана.
    """

    def write(dwg: Path, out: Path, **_: object) -> Any:
        gate.calls += 1
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)
        half = len(payload) // CHUNKS
        with out.open("wb") as fh:
            fh.write(payload[:half])
            fh.flush()
            gate.partial.set()
            gate.release.wait(timeout=30)
            fh.write(payload[half:])
        return _FakeMesh()

    return write


class _FakeMesh:
    """`MeshResult`-ийн орлуулагч: хязгаар нь тодорхойгүй."""

    extents_min = None
    extents_max = None


def _concurrent_read(app: Server, path: str, gate: Gate) -> tuple[int, bytes]:
    """Экспорт дундуур байхад ХОЁР ДАХЬ хүсэлт явуулж, түүний хариуг буцаана."""
    first: dict[str, tuple[int, bytes, dict[str, str]]] = {}
    second: dict[str, tuple[int, bytes, dict[str, str]]] = {}

    t1 = threading.Thread(target=lambda: first.setdefault("r", app.get(path)))
    t1.start()
    assert gate.partial.wait(timeout=30), "экспорт эхлээгүй"

    t2 = threading.Thread(target=lambda: second.setdefault("r", app.get(path)))
    t2.start()
    # Хоёр дахь хүсэлтэд буруу уншилт хийх БОЛОМЖ өгнө: засваргүй кодод энэ
    # хугацаанд тэр хагас файлыг уншаад явчихдаг.
    time.sleep(0.3)
    gate.release.set()

    t1.join(timeout=60)
    t2.join(timeout=60)
    code, body, _ = second["r"]
    assert first["r"][0] == 200, "эхний хүсэлт амжилтгүй"
    return code, body


# --------------------------------------------------------------------------
# D1 — экспорт дуусаагүй байхад хоёр дахь хүсэлт хагас файл авдаг байсан
# --------------------------------------------------------------------------


def test_a_mesh_read_during_export_is_never_truncated(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Хоёр таб нэг эд ангийг зэрэг нээхэд хоёулаа БҮТЭН меш авна.

    Байсан алдаа: `is_file()`-ийн давхар шалгалт нь түгжээний ГАДНА байсан тул
    AutoCAD бичиж дуусаагүй файлыг хоёр дахь хүсэлт олоод, түгжээг алгасаж,
    хагас STL-ийг HTTP 200-аар үйлчилдэг байв.
    """
    name = _part(tmp_path)
    gate = Gate()
    monkeypatch.setattr(gui, "export_stl", _slow_writer(gate, _stl_bytes()))

    code, body = _concurrent_read(app, f"/api/mesh?name={name}", gate)

    assert code == 200
    assert len(body) == FULL_STL, f"хагас меш очив: {len(body)} != {FULL_STL}"
    assert gate.calls == 1, "AutoCAD хоёр удаа ажиллав — кэш ажиллахгүй байна"


def test_a_preview_read_during_render_is_never_truncated(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Урьдчилсан зураг дээр ч мөн адил — хагас PNG хөтөч рүү явж болохгүй."""
    name = _part(tmp_path)
    gate = Gate()
    monkeypatch.setattr(
        gui, "render_png", _slow_writer(gate, b"\x89PNG" + b"\x00" * (FULL_PNG - 4))
    )

    code, body = _concurrent_read(app, f"/api/preview?name={name}&view=swiso", gate)

    assert code == 200
    assert len(body) == FULL_PNG, f"хагас зураг очив: {len(body)} != {FULL_PNG}"
    assert gate.calls == 1


# --------------------------------------------------------------------------
# D4 — хязгаар тодорхойгүй үед хуучин хажуугийн файл үлдэж, ШИНЭ мешийг
#      ХУУЧИН координатаар байрлуулдаг байсан
# --------------------------------------------------------------------------


def test_unknown_extents_remove_a_stale_sidecar(tmp_path: Path) -> None:
    """Хязгаар нь тодорхойгүй бол хуучин `.ext` файл ҮЛДЭХГҮЙ.

    Байсан алдаа: `save_extents` нь юу ч бичихгүй эргэж таардаг байсан тул
    өмнөх ажиллалтын `.ext` газраа хэвээр үлдэж, шинэ мешийн `X-Extents`
    болж явдаг байв. Загвар чимээгүй буруу байранд гарна.
    """
    stl = tmp_path / "Pipe.stl"
    stl.write_bytes(b"stl")
    stale = gui.extents_path(stl)
    stale.write_text("1 2 3 4 5 6", encoding="utf-8")

    gui.save_extents(stl, _FakeMesh())

    assert not stale.exists(), "хуучин хажуугийн файл үлдэв"
    assert gui.read_extents(stl) is None


def test_a_failed_export_does_not_poison_the_cache(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Таслагдсан экспортын үлдэгдэл кэш болж хувирахгүй.

    Байсан алдаа: AutoCAD timeout болвол хагас STL диск дээр ҮЛДДЭГ ба
    `save_extents` хүртэл хүрдэггүй тул өмнөх ажиллалтын `.ext` хажууд нь
    үлдэнэ. Дараагийн хүсэлт `is_file()`-ийг харан экспортыг алгасаж,
    таслагдсан мешийг хуучин координаттай HTTP 200-аар ҮҮРД үйлчилдэг байв.
    """
    name = _part(tmp_path)
    stl = (tmp_path / ".preview") / f"{name}.stl"
    gui.extents_path(stl).write_text("1 2 3 4 5 6", encoding="utf-8")
    calls = {"n": 0}

    def flaky(dwg: Path, out: Path, **_: object) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 200)  # хагас бичигдээд таслагдав
            raise gui.DwgForgeError("accore timed out")
        out.write_bytes(_stl_bytes())
        return _FakeMesh()

    monkeypatch.setattr(gui, "export_stl", flaky)

    assert app.get(f"/api/mesh?name={name}")[0] == 500
    assert not stl.exists(), "хагас STL кэшид үлдэв"
    assert not gui.extents_path(stl).exists(), "хуучин хажуугийн файл үлдэв"

    code, body, headers = app.get(f"/api/mesh?name={name}")
    assert code == 200
    assert len(body) == FULL_STL, "таслагдсан кэш дахин үйлчлэв"
    assert calls["n"] == 2, "дахин экспорт хийсэнгүй"
    assert "X-Extents" not in headers


def test_a_failed_render_does_not_poison_the_cache(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Урьдчилсан зураг дээр ч мөн адил — хагас PNG кэш болохгүй."""
    name = _part(tmp_path)
    png = (tmp_path / ".preview") / f"{name}-swiso.png"
    calls = {"n": 0}

    def flaky(dwg: Path, out: Path, **_: object) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x89PNG" + b"\x00" * 40)
            raise gui.DwgForgeError("plot failed")
        out.write_bytes(b"\x89PNG" + b"\x00" * (FULL_PNG - 4))
        return None

    monkeypatch.setattr(gui, "render_png", flaky)

    assert app.get(f"/api/preview?name={name}&view=swiso")[0] == 500
    assert not png.exists(), "хагас PNG кэшид үлдэв"

    code, body, _ = app.get(f"/api/preview?name={name}&view=swiso")
    assert code == 200
    assert len(body) == FULL_PNG
    assert calls["n"] == 2


def test_a_corrupt_sidecar_reads_as_unknown(tmp_path: Path) -> None:
    """Эвдэрсэн `.ext` нь таамаг болж хувирахгүй — `None` болно."""
    stl = tmp_path / "Pipe.stl"
    stl.write_bytes(b"stl")
    gui.extents_path(stl).write_text("1 2 3 nonsense", encoding="utf-8")

    assert gui.read_extents(stl) is None


def test_a_mesh_without_extents_omits_the_header(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Хязгаар мэдэгдэхгүй бол `X-Extents` толгой ЯВАХГҮЙ (таамаг явуулахгүй)."""
    name = _part(tmp_path)
    gate = Gate()
    gate.release.set()
    monkeypatch.setattr(gui, "export_stl", _slow_writer(gate, _stl_bytes()))

    code, body, headers = app.get(f"/api/mesh?name={name}")

    assert code == 200
    assert len(body) == FULL_STL
    assert "X-Extents" not in headers


# --------------------------------------------------------------------------
# D2 — дахин барих үеийн кэш устгалт нислэг дэх уншилттай мөргөлддөг байсан
# --------------------------------------------------------------------------


def test_a_rebuild_never_serves_a_half_deleted_cache(
    app: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Дахин барилт явж байхад ирсэн хүсэлт бүтэн хариу авна.

    Байсан алдаа: `build_part` нь хуучин кэшээ түгжээ ТАВЬСНЫ ДАРАА устгадаг
    байсан тул зэрэгцээ хүсэлт `is_file()` ба `read_bytes()` хоёрын хооронд
    устгалтад өртөж, хуучин байт эсвэл `FileNotFoundError` авдаг байв.
    """
    name = _part(tmp_path)
    stl = (tmp_path / ".preview") / f"{name}.stl"
    stl.write_bytes(b"HUUCHIN" * 10)
    gui.extents_path(stl).write_text("9 9 9 9 9 9", encoding="utf-8")

    gate = Gate()
    monkeypatch.setattr(gui, "export_stl", _slow_writer(gate, _stl_bytes()))

    started = threading.Event()
    finish = threading.Event()

    def slow_build(*_: object, **__: object) -> bool:
        started.set()
        finish.wait(timeout=30)
        (tmp_path / f"{name}.dwg").write_bytes(b"rebuilt")
        return True

    monkeypatch.setattr(gui, "run", slow_build)
    monkeypatch.setattr(gui, "emit", lambda *a, **k: [])
    monkeypatch.setattr(gui, "load_table", lambda: None)

    # `build_part` нь талбаруудыг `dataclasses.fields`-ээр уншдаг тул энэ нь
    # жинхэнэ dataclass байх ёстой (талбаргүй ч гэсэн).
    @dataclasses.dataclass
    class FakePart:
        def name(self) -> str:
            return name

    monkeypatch.setitem(gui.PART_TYPES, "Fake", FakePart)

    result: dict[str, dict[str, object]] = {}
    builder = threading.Thread(
        target=lambda: result.setdefault("r", gui.build_part("Fake", {})),
    )
    builder.start()
    assert started.wait(timeout=30), "барилт эхлээгүй"

    reader: dict[str, tuple[int, bytes, dict[str, str]]] = {}
    t = threading.Thread(target=lambda: reader.setdefault("r", app.get(f"/api/mesh?name={name}")))
    t.start()
    time.sleep(0.3)
    finish.set()
    gate.release.set()
    builder.join(timeout=60)
    t.join(timeout=60)

    assert result["r"]["ok"] is True
    code, body, _ = reader["r"]
    assert code == 200
    # Хуучин кэш устсан тул ШИНЭ меш гарах ёстой — хагас ч биш, хуучин ч биш.
    assert len(body) == FULL_STL, f"буруу урт: {len(body)}"
    assert gate.calls == 1
