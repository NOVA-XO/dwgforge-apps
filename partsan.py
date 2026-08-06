r"""Параметрт 3D эд ангийн сан — хоолой, тохой, тройник, шилжилт, фланец, хавхлага.

БҮХ ХЭМЖЭЭСИЙГ ЗАСАЖ БОЛНО. Хоёр арга:

  1. `hemjees.json` файлыг засах (эхний ажиллуулалтад автоматаар үүснэ).
     Тэнд DN бүрийн гадна диаметр, ханын зузаан, фланецын хэмжээс байна.

  2. Эд анги үүсгэхдээ шууд дамжуулах:
         Pipe(dn=100, length=800, wall=8.0)
         Elbow(dn=150, angle=45, bend_radius=1.5)

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe parts3d\\partsan.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

# Гүйцэтгэлийн давхаргыг өөрсдөө бичихгүй — dwgforge-д тестлэгдсэн байгаа.
from dwgforge.lisp import lisp_real

HERE = Path(__file__).parent
OUTDIR = HERE / "partsan"
CONFIG = HERE / "hemjees.json"
EXE = Path(r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe")

# --------------------------------------------------------------------------
# ХЭМЖЭЭСИЙН ХҮСНЭГТ — засаж болно (hemjees.json дотор гарна)
# --------------------------------------------------------------------------

# DN -> (гадна диаметр мм, ханын зузаан мм)   ASME B36.10 Sch40
DN_DEFAULT: dict[str, list[float]] = {
    "15": [21.3, 2.77],
    "20": [26.7, 2.87],
    "25": [33.4, 3.38],
    "32": [42.2, 3.56],
    "40": [48.3, 3.68],
    "50": [60.3, 3.91],
    "65": [73.0, 5.16],
    "80": [88.9, 5.49],
    "100": [114.3, 6.02],
    "125": [141.3, 6.55],
    "150": [168.3, 7.11],
    "200": [219.1, 8.18],
    "250": [273.0, 9.27],
    "300": [323.8, 10.31],
}

# DN -> (фланецын гадна диаметр, зузаан, болтын тойргийн диаметр, болтын нүх, болтын тоо)
# EN 1092-1 PN16 ойролцоо утга. Тодорхой стандартад тааруулж засна уу.
FLANGE_DEFAULT: dict[str, list[float]] = {
    "15": [95.0, 14.0, 65.0, 14.0, 4],
    "20": [105.0, 16.0, 75.0, 14.0, 4],
    "25": [115.0, 16.0, 85.0, 14.0, 4],
    "32": [140.0, 18.0, 100.0, 18.0, 4],
    "40": [150.0, 18.0, 110.0, 18.0, 4],
    "50": [165.0, 20.0, 125.0, 18.0, 4],
    "65": [185.0, 20.0, 145.0, 18.0, 8],
    "80": [200.0, 20.0, 160.0, 18.0, 8],
    "100": [220.0, 22.0, 180.0, 18.0, 8],
    "125": [250.0, 22.0, 210.0, 18.0, 8],
    "150": [285.0, 24.0, 240.0, 22.0, 8],
    "200": [340.0, 26.0, 295.0, 22.0, 12],
    "250": [405.0, 29.0, 355.0, 26.0, 12],
    "300": [460.0, 32.0, 410.0, 26.0, 12],
}


# ------------------------------------------------------------------------
# Үйлдвэрлэгчийн каталогийн хэмжээс энэ repo-д ОРОХГҮЙ.
#
# Bray, Alfa Laval зэрэг компаниуд гарын авлагадаа "shall not be copied,
# transferred, conveyed, or displayed ... without express written permission"
# гэсэн заалттай. Код нь нээлттэй тул тэдгээрийн хүснэгтийг дахин нийтлэхгүй:
# `parts3d/local/` хавтаснаас уншина, тэр хавтас нь gitignore хийгдсэн.
#
# Өөрийн өгөгдлөө оруулах: `parts3d/local/bray_check.json` файлыг үүсгээд
#   { "100": [face_to_face, body_od, C, D], ... }   бүгд мм
# гэсэн бүтэцтэй бичнэ. Эх сурвалж нь тухайн үйлдвэрлэгчийн гарын авлага.
# Файл байхгүй бол буцах хавхлагын эд анги тодорхой алдаа өгнө.
# ------------------------------------------------------------------------
LOCAL = HERE / "local"


def load_local(name: str) -> dict[str, list[float]]:
    """`local/<name>.json`-оос хэмжээс уншина. Байхгүй бол хоосон буцаана."""
    f = LOCAL / f"{name}.json"
    if not f.is_file():
        return {}
    raw = json.loads(f.read_text(encoding="utf-8"))
    return {k: [float(x) for x in v] for k, v in raw.items() if not k.startswith("_")}


CHECK_DEFAULT: dict[str, list[float]] = load_local("bray_check")


@dataclass
class Table:
    """Ажиллах үеийн хэмжээсийн хүснэгт. hemjees.json-оос уншина."""

    dn: dict[str, list[float]] = field(default_factory=lambda: dict(DN_DEFAULT))
    flange: dict[str, list[float]] = field(default_factory=lambda: dict(FLANGE_DEFAULT))
    check: dict[str, list[float]] = field(default_factory=lambda: dict(CHECK_DEFAULT))

    def od(self, dn: int) -> float:
        """Хоолойн гадна диаметр, мм."""
        return self._row(self.dn, dn, "DN")[0]

    def wall(self, dn: int) -> float:
        """Ханын зузаан, мм."""
        return self._row(self.dn, dn, "DN")[1]

    def id_(self, dn: int) -> float:
        """Дотоод диаметр (гадна - 2 x хана), мм."""
        return self.od(dn) - 2.0 * self.wall(dn)

    def fl(self, dn: int) -> list[float]:
        """Фланец: [гадна D, зузаан, болтын тойрог, нүхний D, болтын тоо]."""
        return self._row(self.flange, dn, "фланец")

    def chk(self, dn: int) -> list[float]:
        """Буцах хавхлага: [face-to-face, их биеийн гадна D, C, D] мм."""
        if not self.check:
            msg = (
                "Буцах хавхлагын хэмжээсийн хүснэгт хоосон байна. Үйлдвэрлэгчийн "
                "өгөгдлийг энэ repo-д оруулаагүй (лицензийн шалтгаанаар). "
                f"{LOCAL / 'bray_check.json'} файлыг үүсгэж "
                '{"<DN>": [<face_to_face>, <body_od>, <C>, <D>], ...} '
                "хэлбэрээр бичнэ үү (бүгд мм)."'
            )
            raise KeyError(msg)
        return self._row(self.check, dn, "буцах хавхлага")

    @staticmethod
    def _row(src: dict[str, list[float]], dn: int, what: str) -> list[float]:
        key = str(dn)
        if key not in src:
            have = ", ".join(sorted(src, key=int))
            msg = f"{what} хүснэгтэд DN{dn} алга. Байгаа: {have}"
            raise KeyError(msg)
        return src[key]


def load_table() -> Table:
    """hemjees.json-оос уншина. Байхгүй бол өгөгдмөлөөр үүсгэнэ."""
    if not CONFIG.is_file():
        CONFIG.write_text(
            json.dumps(
                {
                    "_тайлбар": "Хэмжээсийг энд засна. dn: [гадна_диаметр, ханын_зузаан]. "
                    "flange: [гадна_D, зузаан, болтын_тойрог, нүхний_D, болтын_тоо]",
                    "dn": DN_DEFAULT,
                    "flange": FLANGE_DEFAULT,
                    "check": CHECK_DEFAULT,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Хэмжээсийн файл үүслээ: {CONFIG.name}  (засаж болно)")
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    return Table(
        dn=raw.get("dn", DN_DEFAULT),
        flange=raw.get("flange", FLANGE_DEFAULT),
        check=raw.get("check", CHECK_DEFAULT),
    )


# --------------------------------------------------------------------------
# AutoLISP үүсгэгч
# --------------------------------------------------------------------------


def r(v: float) -> str:
    """Python float -> AutoLISP REAL.

    dwgforge-ийн хувиргагчийг дуудна: inf/nan-г AutoLISP тоо биш ТЭМДЭГ гэж
    уншдаг тул тэдгээрийг таслах ёстой, мөн ".5" нь уншигчийн хатуу алдаа.
    Тэр логик тэнд 437 тестээр батлагдсан — энд давхардуулах нь эрсдэлтэй.
    """
    return lisp_real(v)


def P(x: float, y: float, z: float) -> str:
    return f"(list {r(x)} {r(y)} {r(z)})"


DRAIN = (
    '(setq _d 0) (while (and (/= (getvar "CMDNAMES") "") (< _d 30)) (command "") (setq _d (1+ _d)))'
)

# Эдгээр нь dwgforge-ийн бүрхүүлийн ДОТОР, биеийн эхэнд ажиллана.
# CMDECHO / FILEDIA / OSMODE / ORTHOMODE-ыг dwgforge-ийн prelude өөрөө
# тавьж, ажил дууссаны дараа сэргээдэг тул энд давхардуулахгүй.
PRELUDE = [
    '(setvar "ISOLINES" 16)',
    '(setvar "DISPSILH" 1)',
    # INSUNITS 4 = миллиметр. Заавал: загварын өгөгдмөл нь метр (6) бөгөөд
    # ингэвэл эд анги мм-ийн зурагт орохдоо 1000 дахин томорно.
    '(setvar "INSUNITS" 4)',
    '(setvar "MEASUREMENT" 1)',
    '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
    # M-ээс хойш үүссэн бүх объектыг сонголтын багц болгоно.
    "(defun SINCE (m / ss e) (setq ss (ssadd)) (setq e (if m (entnext m) (entnext)))"
    " (while e (setq ss (ssadd e ss)) (setq e (entnext e))) ss)",
    '(defun NSOL () (setq _s (ssget "_X" (list (cons 0 "3DSOLID")))) (if _s (sslength _s) 0))',
]


class Build:
    """3D биет үүсгэх үйлдлүүдийг цуглуулж AutoLISP болгоно.

    Загвар: `mark()` -> хэдэн бие үүсгэх -> `union_since()` / `subtract_since()`.
    Бүх боолийн үйлдэл тэмдэглэсэн цэгээс хойшхи биетүүд дээр ажиллана, тул
    аль биет аль нь болохыг гараар хөтлөх шаардлагагүй.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []
        self._n = 0

    # -- дотоод -----------------------------------------------------------
    def cmd(self, form: str) -> None:
        """Нэг команд + асуултын үлдэгдлийг цэвэрлэх хамгаалалт."""
        self.lines.append(form)
        self.lines.append(DRAIN)

    def mark(self) -> str:
        """Одоогийн сүүлчийн объектыг тэмдэглэж, хувьсагчийн нэрийг буцаана."""
        self._n += 1
        var = f"M{self._n}"
        self.lines.append(f"(setq {var} (entlast))")
        return var

    def note(self, text: str) -> None:
        self.lines.append(f'(PR "{text}")')

    # -- примитивүүд ------------------------------------------------------
    def box(self, x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> None:
        """Тэгш өнцөгт бие. (x0,y0,z0) нь суурийн булан."""
        self.cmd(f'(command "_.BOX" {P(x0, y0, z0)} {P(x0 + dx, y0 + dy, z0)} {r(dz)})')

    def cyl(
        self, c: tuple[float, float, float], rad: float, axis: tuple[float, float, float]
    ) -> None:
        """Цилиндр. `c` нь суурийн төв, `axis` нь тэнхлэгийн нөгөө үзүүр."""
        self.cmd(f'(command "_.CYLINDER" {P(*c)} {r(rad)} "_A" {P(*axis)})')

    def cone(
        self,
        c: tuple[float, float, float],
        r_base: float,
        r_top: float,
        axis: tuple[float, float, float],
    ) -> None:
        """Таслагдсан конус (шилжилтэд). `r_top`-ыг өгвөл дээд тал нь хавтгай."""
        self.cmd(f'(command "_.CONE" {P(*c)} {r(r_base)} "_T" {r(r_top)} "_A" {P(*axis)})')

    def sphere(self, c: tuple[float, float, float], rad: float) -> None:
        self.cmd(f'(command "_.SPHERE" {P(*c)} {r(rad)})')

    def torus(self, c: tuple[float, float, float], ring: float, tube: float) -> None:
        """Тор (тохойн үндэс). `ring` нь гулзайлтын радиус, `tube` нь хоолойных."""
        self.cmd(f'(command "_.TORUS" {P(*c)} {r(ring)} {r(tube)})')

    def pie(self, radius: float, angle_deg: float, half_h: float) -> None:
        """Дугуй секторын призм — торыг хэрчиж тохой гаргахад ашиглана.

        0°-ээс `angle_deg` хүртэлх сектор, XY хавтгайд, Z тэнхлэгийн дагуу
        -half_h ... +half_h хооронд сунгагдана.
        """
        th = math.radians(angle_deg)
        bulge = math.tan(th / 4.0)
        x1, y1 = radius, 0.0
        x2, y2 = radius * math.cos(th), radius * math.sin(th)
        self.lines.append(
            '(entmake (list (cons 0 "LWPOLYLINE") (cons 100 "AcDbEntity")'
            ' (cons 100 "AcDbPolyline") (cons 90 3) (cons 70 1)'
            f" (cons 38 {r(-half_h)})"
            f" (list 10 {r(0.0)} {r(0.0)})"
            f" (list 10 {r(x1)} {r(y1)}) (cons 42 {r(bulge)})"
            f" (list 10 {r(x2)} {r(y2)})))"
        )
        self.cmd(f'(command "_.EXTRUDE" (entlast) "" {r(2.0 * half_h)})')

    # -- боолийн үйлдлүүд -------------------------------------------------
    def union_since(self, mark: str) -> None:
        """`mark`-аас хойшхи бүх биетийг нэг болгоно."""
        self.lines.append(f"(setq _ss (SINCE {mark}))")
        self.cmd('(if (> (sslength _ss) 1) (command "_.UNION" _ss ""))')

    def subtract_since(self, keep_mark: str, cut_mark: str) -> None:
        """`keep_mark`..`cut_mark` хоорондын биетээс, `cut_mark`-аас хойшхийг хасна."""
        self.lines.append(f"(setq _keep (SINCE {keep_mark}))")
        self.lines.append(f"(setq _cut (SINCE {cut_mark}))")
        # _keep дотор хасагдах биетүүд бас багтсан тул тэдгээрийг хасна.
        self.lines.append(
            "(setq _i 0) (while (< _i (sslength _cut))"
            " (ssdel (ssname _cut _i) _keep) (setq _i (1+ _i)))"
        )
        self.cmd(
            "(if (and (> (sslength _keep) 0) (> (sslength _cut) 0))"
            ' (command "_.SUBTRACT" _keep "" _cut ""))'
        )

    def intersect_since(self, mark: str) -> None:
        """`mark`-аас хойшхи биетүүдийн огтлолцлыг авна."""
        self.lines.append(f"(setq _ss (SINCE {mark}))")
        self.cmd('(if (> (sslength _ss) 1) (command "_.INTERSECT" _ss ""))')
