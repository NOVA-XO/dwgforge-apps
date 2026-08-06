r"""Эхний ээлжийн 5 эд анги: хоолой, тохой, тройник, шилжилт, фланец.

Хэмжээсийг хоёр аргаар засна:

  1. `hemjees.json` — DN бүрийн гадна диаметр, ханын зузаан, фланецын хэмжээс.
     Эхний ажиллуулалтад автоматаар үүснэ.

  2. Эд анги үүсгэхдээ шууд дамжуулна — хүснэгтийг дарж бичнэ:
         Pipe(dn=100, length=800.0, wall=8.0)
         Elbow(dn=150, angle=45.0, bend_radius=300.0)
         Tee(dn=100, branch_dn=50)

Ажиллуулах:
    cd C:\\Users\\User\\Python\\dwgforge
    .\\.venv\\Scripts\\Activate.ps1
    python "C:\\Users\\User\\OneDrive\\Desktop\\dwgforge-turshilt\\parts.py"
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Гүйцэтгэлийг dwgforge хариуцна: sentinel protocol, хаалтын тэнцвэр,
# мөрийн уртын хязгаар, UTF-16LE тайлалт, timeout, артефакт бичилт.
# Энд зөвхөн 3D геометрийн мөрүүд бидний хариуцлага.
from partsan import PRELUDE, Build, P, Table, load_table

from dwgforge.backends import find_accoreconsole
from dwgforge.backends.accore import AccoreConsoleBackend
from dwgforge.errors import DwgForgeError
from dwgforge.protocol import build_program

OUTDIR = Path(__file__).parent / "parts"
SEED = Path(__file__).parent / "seed" / "seed.dwg"

# accoreconsole нь /i-гүй бол хэрэглэгчийн профайлын загвараас шинэ зураг үүсгэдэг.
# Энэ машин дээр тэр нь Civil 3D-ийн 916 KB загвар — ганц бие агуулсан файл
# 930 KB болдгийн шалтгаан тэр. acadiso нь 31 KB тул үрлэг болгож ашиглана.
# (.dwt-г /i-д өгвөл accoreconsole татгалздаг, гэхдээ .dwg нэртэй хуулбар ажиллана.)
# acadiso.dwt-г хайх байрлалууд. Хэрэглэгчийн нэр, суулгасан бүтээгдэхүүн,
# хувилбар бүрт өөр байдаг тул хатуу зам бичихгүй — эс тэгвээс өөр компьютер
# дээр олдохгүй бөгөөд Civil 3D-ийн 916 KB загвар руу чимээгүй буцна.
SEED_GLOBS = (
    "Autodesk/*/enu/Template/AutoCAD Template/acadiso.dwt",
    "Autodesk/*/enu/Template/acadiso.dwt",
    "Autodesk/*/*/Template/acadiso.dwt",
    "*/UserDataCache/Template/acadiso.dwt",
)


def find_seed_source() -> Path | None:
    """Acadiso загварыг олно. Олдохгүй бол None — профайлын загвар руу буцна."""
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")),
        Path(os.environ.get("APPDATA", "")),
        Path(r"C:\Program Files\Autodesk"),
    ]
    for root in roots:
        if not root or not root.is_dir():
            continue
        for pattern in SEED_GLOBS:
            for hit in sorted(root.glob(pattern), reverse=True):
                if hit.is_file():
                    return hit
    return None


EPS = 0.5  # нүхийг үзүүрээс бага зэрэг цухуйлгана — цэвэр хайчилахын тулд


def ensure_seed() -> Path | None:
    """Үрлэг зургийг бэлдэнэ. Олдохгүй бол None — профайлын загвар руу буцна."""
    if SEED.is_file():
        return SEED
    src = find_seed_source()
    if src is None:
        return None
    SEED.parent.mkdir(parents=True, exist_ok=True)
    SEED.write_bytes(src.read_bytes())
    return SEED


@dataclass
class Pipe:
    """Шулуун хоолой, X тэнхлэгийн дагуу."""

    dn: int = 100
    length: float = 500.0
    od: float | None = None
    wall: float | None = None

    def name(self) -> str:
        return f"Pipe-DN{self.dn}-L{self.length:.0f}"

    def build(self, b: Build, t: Table) -> None:
        od = self.od if self.od is not None else t.od(self.dn)
        wall = self.wall if self.wall is not None else t.wall(self.dn)
        bore = od - 2.0 * wall

        m0 = b.mark()
        b.cyl((0.0, 0.0, 0.0), od / 2.0, (self.length, 0.0, 0.0))
        m1 = b.mark()
        b.cyl((-EPS, 0.0, 0.0), bore / 2.0, (self.length + EPS, 0.0, 0.0))
        b.subtract_since(m0, m1)


@dataclass
class Elbow:
    """Тохой. Гулзайлтын радиус өгөгдмөлөөр 1.5 x DN (long radius)."""

    dn: int = 100
    angle: float = 90.0
    bend_radius: float | None = None
    od: float | None = None
    wall: float | None = None

    def name(self) -> str:
        return f"Elbow-DN{self.dn}-{self.angle:.0f}deg"

    def build(self, b: Build, t: Table) -> None:
        od = self.od if self.od is not None else t.od(self.dn)
        wall = self.wall if self.wall is not None else t.wall(self.dn)
        bore = od - 2.0 * wall
        rb = self.bend_radius if self.bend_radius is not None else 1.5 * self.dn

        cut_r = rb + od  # секторын призм нь торыг бүрэн хамрах ёстой
        cut_h = od

        # 1. Гадна их бие: бүтэн тор -> сектороор огтолно
        m0 = b.mark()
        b.torus((0.0, 0.0, 0.0), rb, od / 2.0)
        b.pie(cut_r, self.angle, cut_h)
        b.intersect_since(m0)

        # 2. Дотоод нүх: ижил зүйл, жижиг хоолойгоор
        m1 = b.mark()
        b.torus((0.0, 0.0, 0.0), rb, bore / 2.0)
        b.pie(cut_r, self.angle, cut_h)
        b.intersect_since(m1)

        b.subtract_since(m0, m1)


@dataclass
class Tee:
    """Тройник. Гол шугам X дагуу, салаа +Y тийш."""

    dn: int = 100
    branch_dn: int | None = None
    run_length: float | None = None
    branch_length: float | None = None

    def name(self) -> str:
        bdn = self.branch_dn if self.branch_dn is not None else self.dn
        return f"Tee-DN{self.dn}x{bdn}"

    def build(self, b: Build, t: Table) -> None:
        od, bore = t.od(self.dn), t.id_(self.dn)
        bdn = self.branch_dn if self.branch_dn is not None else self.dn
        bod, bbore = t.od(bdn), t.id_(bdn)

        rl = self.run_length if self.run_length is not None else 3.0 * od
        bl = self.branch_length if self.branch_length is not None else 1.5 * od
        cx = rl / 2.0

        m0 = b.mark()
        b.cyl((0.0, 0.0, 0.0), od / 2.0, (rl, 0.0, 0.0))
        b.cyl((cx, 0.0, 0.0), bod / 2.0, (cx, bl, 0.0))
        b.union_since(m0)

        m1 = b.mark()
        b.cyl((-EPS, 0.0, 0.0), bore / 2.0, (rl + EPS, 0.0, 0.0))
        b.cyl((cx, 0.0, 0.0), bbore / 2.0, (cx, bl + EPS, 0.0))
        b.subtract_since(m0, m1)


@dataclass
class Reducer:
    """Төвлөрсөн шилжилт: том -> жижиг, X дагуу."""

    dn: int = 100
    dn_small: int = 80
    length: float | None = None

    def name(self) -> str:
        return f"Reducer-DN{self.dn}x{self.dn_small}"

    def build(self, b: Build, t: Table) -> None:
        od1, od2 = t.od(self.dn), t.od(self.dn_small)
        id1, id2 = t.id_(self.dn), t.id_(self.dn_small)
        ln = self.length if self.length is not None else max(3.0 * (od1 - od2), od1)

        m0 = b.mark()
        b.cone((0.0, 0.0, 0.0), od1 / 2.0, od2 / 2.0, (ln, 0.0, 0.0))

        # Нүх нь хоёр үзүүрээс цухуйна. Налууг хадгалахын тулд радиусыг
        # сунгасан хэмжээгээр нь тохируулна, эс тэгвээс хана жигд бус болно.
        m1 = b.mark()
        k = (id1 - id2) / 2.0 / ln
        b.cone(
            (-EPS, 0.0, 0.0),
            id1 / 2.0 + k * EPS,
            id2 / 2.0 - k * EPS,
            (ln + EPS, 0.0, 0.0),
        )
        b.subtract_since(m0, m1)


@dataclass
class Flange:
    """Гагнуурын хүзүүтэй фланец (хялбаршуулсан): диск + хүзүү + болтын нүх."""

    dn: int = 100
    hub_length: float | None = None
    outer: float | None = None
    thickness: float | None = None
    bolt_circle: float | None = None
    bolt_hole: float | None = None
    bolt_count: int | None = None

    def name(self) -> str:
        return f"Flange-DN{self.dn}"

    def build(self, b: Build, t: Table) -> None:
        row = t.fl(self.dn)
        fo = self.outer if self.outer is not None else row[0]
        ft = self.thickness if self.thickness is not None else row[1]
        bc = self.bolt_circle if self.bolt_circle is not None else row[2]
        bh = self.bolt_hole if self.bolt_hole is not None else row[3]
        nb = int(self.bolt_count if self.bolt_count is not None else row[4])

        od, bore = t.od(self.dn), t.id_(self.dn)
        hl = self.hub_length if self.hub_length is not None else 1.5 * ft
        hub_base = od * 1.36  # хүзүүний суурийн диаметр

        m0 = b.mark()
        b.cyl((0.0, 0.0, 0.0), fo / 2.0, (ft, 0.0, 0.0))
        b.cone((ft, 0.0, 0.0), hub_base / 2.0, od / 2.0, (ft + hl, 0.0, 0.0))
        b.union_since(m0)

        m1 = b.mark()
        b.cyl((-EPS, 0.0, 0.0), bore / 2.0, (ft + hl + EPS, 0.0, 0.0))
        for i in range(nb):
            ang = 2.0 * math.pi * i / nb
            y = bc / 2.0 * math.cos(ang)
            z = bc / 2.0 * math.sin(ang)
            b.cyl((-EPS, y, z), bh / 2.0, (ft + EPS, y, z))
        b.subtract_since(m0, m1)


@dataclass
class CheckValve:
    """Bray/Rite Series 210 маягийн wafer буцах хавхлага.

    Бүх үндсэн хэмжээс нь Bray-гийн IOM гарын авлагын "THE RITE DIMENSIONS"
    хүснэгтээс (Class 125/150) ирнэ — таамаглаагүй. Дотоод нүхийг хоолойн
    хүснэгтээс авна: суудлын нүх нь шугамын дотоод диаметртэй тэнцүү гэж үзэв.

    Загварт орсон зүйл: их бие, урсгалын нүх, оролтын хэлбэржүүлэлт, өргөх
    цагираг. Дотоод хаалт, нугас, пүрш, суудлын хатуу давхарга ЭНД БАЙХГҮЙ —
    Plant 3D-ийн эд ангид гадна хэлбэр ба нүх л чухал.
    """

    dn: int = 100
    face_to_face: float | None = None  # None -> Bray хүснэгтээс
    body_od: float | None = None  # None -> Bray хүснэгтээс
    bore: float | None = None  # None -> хоолойн дотоод диаметр
    eye: bool = True  # өргөх цагираг зурах эсэх

    def name(self) -> str:
        return f"CheckValve-DN{self.dn}"

    def build(self, b: Build, t: Table) -> None:
        row = t.chk(self.dn)
        ff = self.face_to_face if self.face_to_face is not None else row[0]
        od = self.body_od if self.body_od is not None else row[1]
        top = row[2]  # тэнхлэгээс дээших нийт өндөр; 0 бол өгөгдөөгүй
        bore = self.bore if self.bore is not None else t.id_(self.dn)

        if bore >= od:
            msg = f"DN{self.dn}: нүх ({bore}) их биеэс ({od}) том байж болохгүй"
            raise ValueError(msg)

        cx = ff / 2.0
        rise = top - od / 2.0 if top > 0.0 else od * 0.32

        # 1. Гадна: их бие + өргөх цагирагийн иш, цагираг
        m0 = b.mark()
        b.cyl((0.0, 0.0, 0.0), od / 2.0, (ff, 0.0, 0.0))

        ring_ro = ring_t = ring_cz = 0.0
        if self.eye and rise > 8.0:
            ring_ro = rise * 0.26
            ring_t = ring_ro * 0.60
            ring_cz = od / 2.0 + rise - ring_ro
            stem_r = max(4.0, rise * 0.11)
            # Иш нь их бие рүү бага зэрэг оршино — нэгтгэхэд цоорхой үлдэхгүй.
            b.cyl((cx, 0.0, od / 2.0 - 3.0), stem_r, (cx, 0.0, ring_cz))
            # Цагирагийг Y тэнхлэгийн дагуух цилиндрээр хийнэ: эргүүлэх
            # шаардлагагүй бөгөөд TORUS нь зөвхөн XY хавтгайд үүсдэг.
            b.cyl((cx, -ring_t / 2.0, ring_cz), ring_ro, (cx, ring_t / 2.0, ring_cz))
        b.union_since(m0)

        # 2. Дотоод: урсгалын нүх, оролтын хэлбэржүүлэлт, цагирагийн нүх
        m1 = b.mark()
        b.cyl((-EPS, 0.0, 0.0), bore / 2.0, (ff + EPS, 0.0, 0.0))
        # Оролт талд өргөсгөсөн конус — каталогийн "elliptical inlet shape
        # designed to accelerate line media" гэсэн онцлогийн хялбаршуулалт.
        inlet = min(bore * 1.16, od - 8.0)
        b.cone((-EPS, 0.0, 0.0), inlet / 2.0, bore / 2.0, (ff * 0.34, 0.0, 0.0))
        if ring_ro > 0.0:
            b.cyl(
                (cx, -ring_t / 2.0 - EPS, ring_cz),
                ring_ro * 0.46,
                (cx, ring_t / 2.0 + EPS, ring_cz),
            )
        b.subtract_since(m0, m1)


# --------------------------------------------------------------------------
# Ажиллуулагч
# --------------------------------------------------------------------------


def emit(parts: list, t: Table, spacing: float = 0.0) -> list[str]:
    """Хэд хэдэн эд ангийг нэг LISP хөтөлбөр болгоно."""
    b = Build()
    for i, p in enumerate(parts):
        b.note(f"--- {p.name()} ---")
        start = b.mark()
        p.build(b, t)
        if spacing:
            b.lines.append(f"(setq _ss (SINCE {start}))")
            b.cmd(
                f'(if (> (sslength _ss) 0) (command "_.MOVE" _ss "" '
                f"{P(0.0, 0.0, 0.0)} {P(0.0, i * spacing, 0.0)}))"
            )
        b.lines.append(f'(PR (strcat "  {p.name()}|solids=" (itoa (NSOL))))')
    return b.lines


def run(body: list[str], out: Path) -> bool:
    """LISP-ийн биеийг dwgforge-ийн бүрхүүлд оруулж гүйцэтгэнэ.

    build_program нь prelude/SAVEAS/epilogue-г нэмээд хаалтын тэнцвэр, мөрийн
    урт, sentinel-ийн хуурамчлалыг шалгана — тэдгээрийн аль нэг нь эвдэрвэл
    accoreconsole үүрд гацдаг тул файл бичихээс ӨМНӨ таслах ёстой.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    target = out.resolve()
    try:
        program = build_program(
            [*PRELUDE, *body],
            dwg_out=target,
            dwg_format="2018",
            max_line=AccoreConsoleBackend.max_line,
        )
    except DwgForgeError as exc:
        print(f"  FAIL {out.stem:24s} бүтээхэд алдав: {exc}")
        return False

    backend = AccoreConsoleBackend(template=ensure_seed())
    result = backend.run(program, target, timeout=900.0)

    rep = [
        ln.strip()[5:] for ln in result.transcript.splitlines() if ln.strip().startswith("@@@  ")
    ]
    size = target.stat().st_size if target.is_file() else 0
    mark = "OK  " if result.ok else "FAIL"
    print(f"  {mark} {out.stem:24s} {size:>9,}  {' '.join(rep)}")
    if not result.ok:
        for note in result.notes[:2]:
            print(f"       ! {note[:110]}")
        for tag, message in result.failures[:3]:
            print(f"       ! {tag}: {message[:90]}")
    return result.ok


def main() -> int:
    exe = find_accoreconsole()
    if exe is None:
        print("accoreconsole олдсонгүй. DWGFORGE_ACCORECONSOLE-ыг тохируулна уу.")
        return 1
    print(f"accoreconsole: {exe}")
    t = load_table()

    # ------------- ЭНД ЗАСНА: ямар эд анги, ямар хэмжээтэй -------------
    parts = [
        Pipe(dn=100, length=500.0),
        Elbow(dn=100, angle=90.0),
        Elbow(dn=100, angle=45.0),
        Tee(dn=100),
        Reducer(dn=100, dn_small=80),
        Flange(dn=100),
    ]
    # -------------------------------------------------------------------

    print(f"DN100:  гадна={t.od(100)}  хана={t.wall(100)}  дотоод={t.id_(100):.2f} мм")
    print(f"Фланец DN100: {t.fl(100)}\n")

    ok = total = 0
    print("Тусдаа файлууд:")
    for part in parts:
        total += 1
        ok += run(emit([part], t), OUTDIR / f"{part.name()}.dwg")

    print("\nТойм (бүгд нэг файлд):")
    total += 1
    ok += run(emit(parts, t, spacing=500.0), OUTDIR / "toim.dwg")

    print(f"\n{ok}/{total} амжилттай -> {OUTDIR}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
