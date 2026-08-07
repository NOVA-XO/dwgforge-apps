r"""DWG -> STL меш. Браузерын 3D үзүүлэлт үүнийг уншина.

Яагаад STL вэ: AutoCAD өөрөө `STLOUT` командаар солидоо гурвалжлан гаргадаг.
Гуравдагч этгээдийн хөрвүүлэгч хэрэггүй бөгөөд меш нь ЯГ тэр солидоос гарна —
хоёр өөр геометр хөтлөх шаардлагагүй.

STLOUT-ийн хоёр онцлогийг туршиж тогтоов:

  * Асуултын дараалал нь  биетүүд -> "хоёртын файл уу?" -> файлын нэр.
  * Гаралт нь эерэг октант руу ШИЛЖДЭГ. Гэхдээ бүх биет НЭГ ижил вектороор
    шилждэг тул харилцан байрлал нь эвдрэхгүй (хоёр цилиндрээр шалгав).
    Жинхэнэ байрлалыг сэргээхийн тулд зургийн хязгаарыг хажууд нь `.ext`
    файлд бичээд, үзүүлэлт дээр нь мешийн төвийг хязгаарын төвд тааруулна.

Ажиллуулах (нэг DWG-г гараар хөрвүүлэх):
    .\\.venv\\Scripts\\python.exe parts3d\\mesh.py parts3d\\parts\\Flange-DN100.dwg
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge.backends import find_accoreconsole

DRAIN = (
    '(setq _d 0) (while (and (/= (getvar "CMDNAMES") "") (< _d 30)) (command "") (setq _d (1+ _d)))'
)

# FACETRES 0.01..10. Өндөр нь гөлгөр меш: DN100 фланец 8-д ~3200 гурвалжин
# (160 KB) гардаг — локал сүлжээнд хормын дотор ачаалагдана.
FACETRES = 8.0


def ext_path(stl: Path) -> Path:
    """STL-ийн хажуугийн хязгаарын файл."""
    return stl.with_suffix(".ext")


def stl_forms(stl: Path, ext: Path) -> list[str]:
    """Бүх солидыг STL болгож, зургийн хязгаарыг бичих LISP мөрүүд.

    Эдгээрийг эд анги үүсгэх хөтөлбөрийн ард залгаж ч болно (нэг л AutoCAD
    ажиллуулалтаар DWG ба STL хоёулаа гарна), тусад нь ч ажиллуулж болно.
    """
    s, e = stl.as_posix(), ext.as_posix()
    return [
        f'(setvar "FACETRES" {FACETRES})',
        # ZOOM E нь EXTMIN/EXTMAX-ыг шинэчилнэ — солидын жинхэнэ хязгаар тэндээс.
        '(command "_.ZOOM" "_E")',
        DRAIN,
        '(setq _lo (getvar "EXTMIN") _hi (getvar "EXTMAX"))',
        '(setq _ss (ssget "_X" (list (cons 0 "3DSOLID"))))',
        f'(if _ss (command "_.STLOUT" _ss "" "_Y" "{s}"))',
        DRAIN,
        f'(setq _f (if _ss (open "{e}" "w")))',
        "(if _f (progn (write-line (strcat"
        ' (rtos (car _lo) 2 6) " " (rtos (cadr _lo) 2 6) " " (rtos (caddr _lo) 2 6) " "'
        ' (rtos (car _hi) 2 6) " " (rtos (cadr _hi) 2 6) " " (rtos (caddr _hi) 2 6))'
        " _f) (close _f)))",
    ]


def export_stl(dwg: Path, stl: Path) -> Path | None:
    """Байгаа DWG-г STL болгоно. Амжилтгүй бол None (лог нь `.log` дотор)."""
    exe = find_accoreconsole()
    if exe is None or not dwg.is_file():
        return None

    stl.parent.mkdir(parents=True, exist_ok=True)
    ext = ext_path(stl)
    stl.unlink(missing_ok=True)
    ext.unlink(missing_ok=True)

    forms = [
        '(setvar "CMDECHO" 0)',
        '(setvar "FILEDIA" 0)',
        # Объектын зүүлт асаалттай бол цэгүүд "наалдаж" командууд нурдаг.
        '(setvar "OSMODE" 0)',
        *stl_forms(stl, ext),
        "(princ)",
    ]
    scr = stl.with_suffix(".scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(forms) + "\r\n").encode("utf-8"))

    proc = subprocess.run(
        [str(exe), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=600,
        check=False,
        cwd=str(stl.parent),
    )
    text = (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")
    scr.unlink(missing_ok=True)

    if not stl.is_file():
        stl.with_suffix(".log").write_text(text, encoding="utf-8")
        return None
    return stl


def read_extents(ext: Path) -> list[float] | None:
    """`.ext` файлаас [minx miny minz maxx maxy maxz]. Уншигдахгүй бол None."""
    if not ext.is_file():
        return None
    try:
        nums = [float(v) for v in ext.read_text(encoding="utf-8").split()]
    except ValueError:
        return None
    return nums if len(nums) == 6 else None


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(2)
    src = Path(args[0]).resolve()
    out = src.parent / ".preview" / f"{src.stem}.stl"
    got = export_stl(src, out)
    if got is None:
        print(f"амжилтгүй — {out.with_suffix('.log')} харна уу")
        raise SystemExit(1)
    tris = max(got.stat().st_size - 84, 0) // 50
    print(f"OK  {got}  ({tris:,} гурвалжин)  хязгаар: {read_extents(ext_path(got))}")
