r"""Alfa Laval AlfaNova 400 / HP 400 — параметрт 3D загвар үүсгэгч (ПРОТОТИП).

Каталогийн хуудаснаас (CHE00049-7-EN-GB) авсан томьёо:
    A (ялтсын багцын зузаан) = 14 + 2.65 * n     мм
    Жин                       = 22 + 1.40 * n     кг
    n = 10 … 270 ялтас

Энэ бол ПРОТОТИП. Доорх PARAMS доторх бүх тоог нэг дор засаж болно.
Тодорхойгүй хэмжээсүүдийг "?" гэж тэмдэглэсэн — хуудсанд байхгүй эсвэл
зурган дээрх аль элементэд харьяалагдах нь текстээс ялгагдахгүй байсан.

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe parts3d\\alfanova400.py
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Гүйцэтгэл ба солид үүсгэлтийг бүхэлд нь dwgforge хариуцна. Энэ файл нэгэн цагт
# өөрийн r(), pt(), DRAIN, PRELUDE, run()-тэй байсан — бүгд нь сангийн дутуу
# хуулбар: `.scr`-ээ бичсэн ХОЙНО мөрийн уртаа шалгадаг (гацдаг файлыг дискэн
# дээр үлдээгээд татгалздаг), амжилтыг "@@@DONE" мөр байгаа эсэхээр шалгадаг
# (скрипт өөрийн эх кодоо цуурайтуулдаг тул түүнийг хуурамчилж болно) байв.
from dwgforge import SolidModel, solid_count, write_dwg
from dwgforge.backends import find_accoreconsole
from dwgforge.backends.accore import AccoreConsoleBackend
from dwgforge.errors import DwgForgeError
from parts import ensure_seed

HERE = Path(__file__).parent
OUTDIR = HERE / "alfanova"

# --------------------------------------------------------------------------
# ПАРАМЕТРҮҮД — засах бол зөвхөн энэ хэсгийг
# --------------------------------------------------------------------------

# Хэмжээсийг `local/alfanova400.json`-оос уншина. Alfa Laval-ын хуудсанд
# "No part of this document may be copied, re-produced or transmitted ...
# without Alfa Laval's prior express written permission" гэсэн заалттай тул
# тэдгээрийг энэ нээлттэй repo-д оруулаагүй. Файлын бүтцийг README-гээс үз.
_LOCAL = HERE / "local" / "alfanova400.json"
if not _LOCAL.is_file():
    _MSG = (
        f"{_LOCAL} олдсонгүй. AlfaNova 400-ийн хэмжээсийг үйлдвэрлэгчийн "
        "хуудаснаас авч энэ файлд бичнэ үү (бүтцийг parts3d/README.md-ээс үз)."
    )
    raise SystemExit(_MSG)
_D = json.loads(_LOCAL.read_text(encoding="utf-8"))

_B = _D["body"]
WIDTH = _B["WIDTH"]
BODY_H = _B["BODY_H"]
TOTAL_H = _B["TOTAL_H"]
PORT_DX = _B["PORT_DX"]
PORT_DZ = _B["PORT_DZ"]
FOOT_W_OUT = _B["FOOT_W_OUT"]
FOOT_W_IN = _B["FOOT_W_IN"]
FOOT_D = _B["FOOT_D"]
DN = {int(k): v for k, v in _D["connections_od_mm"].items()}

# Эдгээр нь каталогт БАЙХГҮЙ — хассан эсвэл таамагласан утга, тул кодод үлдэнэ.
FOOT_H = TOTAL_H - BODY_H  # хуудсанд шууд байхгүй, 1253 - 990 гэж хасав
FOOT_PLATE_T = 20.0  # ? хөлний ялтасны зузаан — таамаг
PORT_LEN = 60.0  # ? холбоосын цухуйх урт — таамаг

# ? Хуудсанд ашиглагдаагүй үлдсэн хэмжээс: 242 (9.53), 200+A, 260+A.


@dataclass(frozen=True)
class Variant:
    """Нэг хувилбар: ялтсын тоо ба холбоосын хэмжээ."""

    plates: int
    dn: int

    @property
    def a(self) -> float:
        """Ялтсын багцын зузаан, мм."""
        return 14.0 + 2.65 * self.plates

    @property
    def weight(self) -> float:
        """Жин, кг (холбоосгүйгээр)."""
        return 22.0 + 1.40 * self.plates

    @property
    def name(self) -> str:
        return f"AlfaNova400-n{self.plates}-DN{self.dn}"


# --------------------------------------------------------------------------
# Геометр
# --------------------------------------------------------------------------


def r(v: float) -> str:
    """Python float -> AutoLISP REAL. Заавал бутархай цэгтэй."""
    s = repr(float(v))
    if "e" in s or "E" in s:
        m, _, e = s.partition("e")
        s = (m if "." in m else m + ".0") + "e" + e
    elif "." not in s:
        s += ".0"
    return s


def pt(x: float, y: float, z: float) -> str:
    return f"(list {r(x)} {r(y)} {r(z)})"


def add_unit(model: SolidModel, v: Variant, ox: float, oy: float) -> None:
    """Нэг агрегатыг модельд нэмнэ. (ox, oy) нь байрлуулах эхлэл."""
    a = v.a
    dia = DN[v.dn]
    z0 = FOOT_H  # их биеийн доод тал

    model.note(f"--- {v.name} ---")
    start = model.mark()

    # 1. Их бие (ялтсын багц + бүрхүүлийн ялтас)
    model.box((ox, oy, z0), (WIDTH, a, BODY_H))

    # 2. Дөрвөн холбоос — урд гадаргуугаас -Y тийш цухуйна
    cx = ox + WIDTH / 2.0
    for sx in (-PORT_DX / 2.0, PORT_DX / 2.0):
        for sz in (0.0, PORT_DZ):
            px = cx + sx
            pz = z0 + (BODY_H - PORT_DZ) / 2.0 + sz
            model.cylinder((px, oy, pz), dia / 2.0, (px, oy - PORT_LEN, pz))

    # 3. Хөл: суурийн ялтас + хоёр хөл
    fx = ox + (WIDTH - FOOT_W_OUT) / 2.0
    model.box((fx, oy, 0.0), (FOOT_W_OUT, FOOT_D, FOOT_PLATE_T))
    leg_w = (FOOT_W_OUT - FOOT_W_IN) / 2.0
    for lx in (fx, fx + FOOT_W_OUT - leg_w):
        model.box((lx, oy, FOOT_PLATE_T), (leg_w, FOOT_D, FOOT_H - FOOT_PLATE_T))

    # 4. Бүх шинэ биеийг нэг болгон нэгтгэнэ
    model.union_since(start)


def run(model: SolidModel, out: Path, label: str) -> bool:
    """Моделийг гүйцэтгэж DWG хадгална."""
    out.parent.mkdir(parents=True, exist_ok=True)
    backend = AccoreConsoleBackend(template=ensure_seed())
    try:
        result = write_dwg(model, out, backend=backend, timeout=900.0, check=False)
    except DwgForgeError as exc:
        print(f"  FAIL {label:34s} бүтээхэд алдав: {exc}")
        return False
    size = out.stat().st_size if out.is_file() else 0
    mark = "OK  " if result.ok else "FAIL"
    print(f"  {mark} {label:34s} {size:>9,} byte  биет={solid_count(result)}")
    for tag, message in result.failures[:3]:
        print(f"       ! {tag}: {message[:90]}")
    return result.ok


# --------------------------------------------------------------------------


def main() -> int:
    if find_accoreconsole() is None:
        print("accoreconsole олдсонгүй. DWGFORGE_ACCORECONSOLE-ыг тохируулна уу.")
        return 1

    plates = (10, 100, 270)
    dns = (80, 100, 150)

    print("AlfaNova 400 — параметрт хувилбарууд")
    print(f"{'ялтас':>6} {'A (мм)':>9} {'жин (кг)':>10}")
    for n in plates:
        v = Variant(n, 100)
        print(f"{n:>6} {v.a:>9.1f} {v.weight:>10.1f}")
    print()

    ok = 0
    total = 0

    # 1. Тойм зураг: 3 ялтас × 3 DN сүлжээгээр нэг файлд
    print("Тойм зураг (3 x 3 сүлжээ):")
    overview = SolidModel()
    gap_x = 900.0
    gap_y = 1400.0
    for row, n in enumerate(plates):
        for col, dn in enumerate(dns):
            add_unit(overview, Variant(n, dn), ox=col * gap_x, oy=row * gap_y)
    total += 1
    ok += run(overview, OUTDIR / "AlfaNova400-toim.dwg", "toim (9 hувилбар)")

    # 2. Хувилбар тус бүр тусдаа файл — блокын сангийн эд анги
    print("\nТусдаа файлууд:")
    for n in plates:
        for dn in dns:
            v = Variant(n, dn)
            model = SolidModel()
            add_unit(model, v, 0.0, 0.0)
            total += 1
            ok += run(model, OUTDIR / f"{v.name}.dwg", v.name)

    print(f"\n{ok}/{total} амжилттай -> {OUTDIR}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
