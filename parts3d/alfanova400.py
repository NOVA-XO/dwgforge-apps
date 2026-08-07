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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
OUTDIR = HERE / "alfanova"
EXE = Path(r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe")

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
# LISP үүсгэгч
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


def unit_forms(v: Variant, ox: float, oy: float) -> list[str]:
    """Нэг АГРЕГАТЫН бүх LISP мөр. (ox, oy) нь байрлуулах эхлэл."""
    a = v.a
    dia = DN[v.dn]
    z0 = FOOT_H  # их биеийн доод тал

    f: list[str] = [f'(P "--- {v.name} ---")', "(setq E0 (entlast))"]

    # 1. Их бие (ялтсын багц + бүрхүүлийн ялтас)
    f += [
        f'(command "_.BOX" {pt(ox, oy, z0)} {pt(ox + WIDTH, oy + a, z0)} {r(BODY_H)})',
        DRAIN,
    ]

    # 2. Дөрвөн холбоос — урд гадаргуугаас -Y тийш цухуйна
    cx = ox + WIDTH / 2.0
    for sx in (-PORT_DX / 2.0, PORT_DX / 2.0):
        for sz in (0.0, PORT_DZ):
            px = cx + sx
            pz = z0 + (BODY_H - PORT_DZ) / 2.0 + sz
            f += [
                f'(command "_.CYLINDER" {pt(px, oy, pz)} {r(dia / 2.0)}'
                f' "_A" {pt(px, oy - PORT_LEN, pz)})',
                DRAIN,
            ]

    # 3. Хөл: суурийн ялтас + хоёр хөл
    fx = ox + (WIDTH - FOOT_W_OUT) / 2.0
    f += [
        f'(command "_.BOX" {pt(fx, oy, 0.0)}'
        f" {pt(fx + FOOT_W_OUT, oy + FOOT_D, 0.0)} {r(FOOT_PLATE_T)})",
        DRAIN,
    ]
    leg_w = (FOOT_W_OUT - FOOT_W_IN) / 2.0
    for lx in (fx, fx + FOOT_W_OUT - leg_w):
        f += [
            f'(command "_.BOX" {pt(lx, oy, FOOT_PLATE_T)}'
            f" {pt(lx + leg_w, oy + FOOT_D, FOOT_PLATE_T)} {r(FOOT_H - FOOT_PLATE_T)})",
            DRAIN,
        ]

    # 4. Бүх шинэ биеийг нэг болгон нэгтгэнэ
    f += [
        "(setq SS (NEWSS E0))",
        '(if (> (sslength SS) 1) (command "_.UNION" SS ""))',
        DRAIN,
        f'(P (strcat "  {v.name}|solids=" (itoa (NSOL))))',
    ]
    return f


DRAIN = (
    '(setq dn 0) (while (and (/= (getvar "CMDNAMES") "") (< dn 20)) (command "") (setq dn (1+ dn)))'
)

PRELUDE = [
    '(setvar "CMDECHO" 0)',
    '(setvar "FILEDIA" 0)',
    # OSMODE 0 ЗААВАЛ: объект барих нь цэгийн оролтыг таслан авч,
    # командын дараалал алдагдвал бүх геометр эвдэрнэ (туршилтаар нотлогдсон).
    '(setvar "OSMODE" 0)',
    '(setvar "ORTHOMODE" 0)',
    '(defun P (s) (princ (strcat "\\n@@@" s)) (princ))',
    '(defun NSOL () (setq s (ssget "_X" (list (cons 0 "3DSOLID")))) (if s (sslength s) 0))',
    # E0-ээс хойш үүссэн бүх обьектыг цуглуулна (ssget "_X" бол бүх зургийг авна).
    "(defun NEWSS (e0 / ss e) (setq ss (ssadd)) (setq e (if e0 (entnext e0) (entnext)))"
    " (while e (setq ss (ssadd e ss)) (setq e (entnext e))) ss)",
]


def run(forms: list[str], out: Path, label: str) -> bool:
    """LISP мөрүүдийг accoreconsole-оор ажиллуулж, DWG хадгална."""
    out.parent.mkdir(parents=True, exist_ok=True)
    p = out.as_posix()
    body = [
        *PRELUDE,
        *forms,
        f'(if (findfile "{p}") (vl-file-delete "{p}"))',
        f'(command "_.SAVEAS" "2018" "{p}")',
        DRAIN,
        f'(P (strcat "saved|" (if (findfile "{p}") "yes" "no")))',
        '(P "DONE")',
        "(princ)",
    ]
    scr = out.with_suffix(".scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(body) + "\r\n").encode("utf-8"))

    too_long = [ln for ln in body if len(ln) >= 1900]
    if too_long:
        print(f"  !! {len(too_long)} мөр 1900 тэмдэгтээс урт — AutoCAD гацна")
        return False

    proc = subprocess.run(
        [str(EXE), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=600,
        check=False,
        cwd=str(out.parent),
    )
    text = (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")
    out.with_suffix(".log").write_text(text, encoding="utf-8")

    errs = [ln.strip() for ln in text.splitlines() if "; error" in ln.lower()]
    ok = "@@@DONE" in text and out.is_file() and not errs
    size = out.stat().st_size if out.is_file() else 0
    print(f"  {'OK ' if ok else 'FAIL'} {label:34s} {size:>9,} byte")
    for e in errs[:3]:
        print(f"       ! {e[:100]}")
    return ok


# --------------------------------------------------------------------------


def main() -> int:
    if not EXE.is_file():
        print(f"accoreconsole олдсонгүй: {EXE}")
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
    forms: list[str] = []
    gap_x = 900.0
    gap_y = 1400.0
    for row, n in enumerate(plates):
        for col, dn in enumerate(dns):
            forms += unit_forms(Variant(n, dn), ox=col * gap_x, oy=row * gap_y)
    total += 1
    ok += run(forms, OUTDIR / "AlfaNova400-toim.dwg", "toim (9 hувилбар)")

    # 2. Хувилбар тус бүр тусдаа файл — блокын сангийн эд анги
    print("\nТусдаа файлууд:")
    for n in plates:
        for dn in dns:
            v = Variant(n, dn)
            total += 1
            ok += run(unit_forms(v, 0.0, 0.0), OUTDIR / f"{v.name}.dwg", v.name)

    print(f"\n{ok}/{total} амжилттай -> {OUTDIR}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
