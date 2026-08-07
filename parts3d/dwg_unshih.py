r"""Байгаа DWG файлыг задлан шинжилнэ — AutoCAD-аар дамжуулж.

DWG бол хаалттай хоёртын формат тул шууд уншиж болохгүй. Энэ хэрэгсэл нь
accoreconsole-оор файлыг нээж, дотоод бүтцийг бүхэлд нь текст болгож гаргана:

  * зургийн хязгаар (extents), нэгж
  * давхаргууд — нэр, өнгө, төрөл
  * entity-үүд — төрөл тус бүрийн тоо, давхарга
  * блокийн тодорхойлолтууд — нэр, доторх entity
  * 3DSOLID бүрийн эзэлхүүн, талбай, хүндийн төв, хязгаарын хайрцаг

Ажиллуулах:
    python dwg_unshih.py <файл.dwg> [<файл2.dwg> ...]
    python dwg_unshih.py C:\\zam\\hawtas\\*.dwg
"""

from __future__ import annotations

import glob
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from partsan import EXE

DRAIN = (
    '(setq _d 0) (while (and (/= (getvar "CMDNAMES") "") (< _d 30)) (command "") (setq _d (1+ _d)))'
)

FORMS = [
    '(setvar "CMDECHO" 0)',
    '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
    "(defun F (x) (rtos x 2 4))",
    '(defun PT3 (p) (strcat (F (car p)) "," (F (cadr p)) "," (F (caddr p))))',
    # --- ерөнхий мэдээлэл ---
    '(command "_.ZOOM" "_E")',
    DRAIN,
    '(PR (strcat "EXTMIN|" (PT3 (getvar "EXTMIN"))))',
    '(PR (strcat "EXTMAX|" (PT3 (getvar "EXTMAX"))))',
    '(PR (strcat "INSUNITS|" (itoa (getvar "INSUNITS"))))',
    '(PR (strcat "DWGNAME|" (getvar "DWGNAME")))',
    '(PR (strcat "ACADVER|" (getvar "ACADVER")))',
    # --- давхаргууд ---
    '(setq L (tblnext "LAYER" T))',
    '(while L (PR (strcat "LAYER|" (cdr (assoc 2 L)) "|color=" (itoa (cdr (assoc 62 L)))'
    ' "|ltype=" (cdr (assoc 6 L)) "|flags=" (itoa (cdr (assoc 70 L)))))'
    ' (setq L (tblnext "LAYER")))',
    # --- блокийн тодорхойлолт ---
    '(setq B (tblnext "BLOCK" T))',
    '(while B (if (not (wcmatch (cdr (assoc 2 B)) "`**"))'
    ' (PR (strcat "BLOCK|" (cdr (assoc 2 B)) "|origin=" (PT3 (cdr (assoc 10 B))))))'
    ' (setq B (tblnext "BLOCK")))',
    # --- entity-үүдийг тоолох ---
    "(setq E (entnext) N 0 TYPES nil)",
    "(while E"
    ' (setq D (entget E) TY (cdr (assoc 0 D)) LA (cdr (assoc 8 D)) K (strcat TY "\\t" LA))'
    " (setq P (assoc K TYPES))"
    " (if P (setq TYPES (subst (cons K (1+ (cdr P))) P TYPES))"
    "        (setq TYPES (cons (cons K 1) TYPES)))"
    " (setq N (1+ N) E (entnext E)))",
    '(PR (strcat "ENTITIES|" (itoa N)))',
    '(foreach p TYPES (PR (strcat "TYPE|" (car p) "|" (itoa (cdr p)))))',
    # --- 3DSOLID бүрийг тусад нь хэмжих ---
    '(setq SS (ssget "_X" (list (cons 0 "3DSOLID"))))',
    '(PR (strcat "SOLIDCOUNT|" (if SS (itoa (sslength SS)) "0")))',
    # MASSPROP нь бие бүрт AutoCAD-ыг бодуулдаг тул эхний хэдийг л хэмжинэ.
    "(setq i 0 MAXS 20)",
    "(while (and SS (< i (sslength SS)) (< i MAXS))"
    ' (setq e1 (ssname SS i)) (PR (strcat "SOLID|" (itoa i) "|layer="'
    " (cdr (assoc 8 (entget e1)))))"
    ' (command "_.MASSPROP" (ssadd e1) "" "_N")'
    f" {DRAIN}"
    " (setq i (1+ i)))",
    '(if (and SS (> (sslength SS) MAXS)) (PR (strcat "SOLIDSKIP|" (itoa (- (sslength SS) MAXS)))))',
    '(PR "DONE")',
    "(princ)",
]


def inspect(dwg: Path) -> str:
    scr = dwg.with_name(dwg.stem + "-inspect.scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(FORMS) + "\r\n").encode("utf-8"))
    proc = subprocess.run(
        [str(EXE), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=600,
        check=False,
        cwd=str(dwg.parent),
    )
    scr.unlink(missing_ok=True)
    return (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")


def report(dwg: Path, text: str) -> None:
    def tags(name: str) -> list[str]:
        return [
            ln.strip()[3 + len(name) + 1 :]
            for ln in text.splitlines()
            if ln.strip().startswith(f"@@@{name}|")
        ]

    def one(name: str) -> str:
        v = tags(name)
        return v[0] if v else "?"

    print(f"\n{'=' * 72}\n{dwg.name}   ({dwg.stat().st_size:,} byte)\n{'=' * 72}")
    if "@@@DONE" not in text:
        print("  !! унших боломжгүй — AutoCAD дуусгаж чадсангүй")
        errs = [ln.strip() for ln in text.splitlines() if "; error" in ln.lower()]
        for e in errs[:5]:
            print(f"     {e[:110]}")
        return

    units = {0: "тодорхойгүй", 1: "инч", 2: "фут", 3: "миль", 4: "мм", 5: "см", 6: "м"}
    iu = one("INSUNITS")
    print(f"  AutoCAD хувилбар : {one('ACADVER')}")
    print(f"  Нэгж             : {units.get(int(iu) if iu.isdigit() else -1, iu)}")
    lo, hi = one("EXTMIN"), one("EXTMAX")
    print(f"  Хязгаар min      : {lo}")
    print(f"  Хязгаар max      : {hi}")
    try:
        a = [float(x) for x in lo.split(",")]
        c = [float(x) for x in hi.split(",")]
        print(f"  Хэмжээ (X,Y,Z)   : {c[0] - a[0]:.2f} x {c[1] - a[1]:.2f} x {c[2] - a[2]:.2f}")
    except (ValueError, IndexError):
        pass

    def show(title: str, items: list[str], cap: int = 25) -> None:
        """Урт жагсаалтыг таслаж хэвлэнэ — загварын давхарга олон зуугаараа байдаг."""
        if not items:
            return
        print()
        print(f"  {title} ({len(items)}):")
        for line in items[:cap]:
            print(f"    {line}")
        if len(items) > cap:
            print(f"    ... бас {len(items) - cap} ширхэг")

    show("Давхарга", tags("LAYER"))
    show("Блок", tags("BLOCK"))

    print(f"\n  Entity нийт: {one('ENTITIES')}")
    for line in tags("TYPE"):
        # LISP-ийн формат: <төрөл><tab><давхарга>|<тоо>
        head, _, cnt = line.rpartition("|")
        ty, _, la = head.partition("\t")
        print(f"    {ty:<16s} давхарга={la:<26s} {cnt:>6s}")

    ns = one("SOLIDCOUNT")
    if ns not in ("?", "0"):
        print(f"\n  3D бие ({ns}):")
        vols = re.findall(r"Volume:\s*([\d.eE+-]+)", text)
        areas = re.findall(r"Surface area:\s*([\d.eE+-]+)", text)
        cents = re.findall(
            r"Centroid:\s*X:\s*([\d.eE+-]+)\s*Y:\s*([\d.eE+-]+)\s*Z:\s*([\d.eE+-]+)", text
        )
        for i, v in enumerate(vols):
            vv = float(v)
            extra = f"  талбай={float(areas[i]):,.0f} мм²" if i < len(areas) else ""
            cc = (
                f"  төв=({float(cents[i][0]):.1f},{float(cents[i][1]):.1f},{float(cents[i][2]):.1f})"
                if i < len(cents)
                else ""
            )
            print(f"    #{i}  эзэлхүүн={vv:,.0f} мм³ = {vv / 1e6:.4f} л{extra}{cc}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    files: list[Path] = []
    for a in argv:
        files.extend(Path(p) for p in glob.glob(a))
    files = [f for f in files if f.suffix.lower() == ".dwg" and f.is_file()]
    if not files:
        print("DWG файл олдсонгүй")
        return 1
    for f in sorted(files):
        report(f, inspect(f))
    print(f"\n{len(files)} файл шинжиллээ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
