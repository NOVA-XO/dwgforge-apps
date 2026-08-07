"""Гүнзгий шинжилгээ: блокийн ДОТОРХ геометрийг задалж хэмжинэ.

`dwg_unshih.py` нь зөвхөн model space-ийг хардаг. Эд ангийн файлд геометр нь
ихэвчлэн блокийн тодорхойлолт дотор байдаг тул тэнд юу ч олдохгүй.

Энэ хэрэгсэл нь:
  1. Блок бүрийн доторх entity-үүдийг тоолно (задлахгүйгээр)
  2. Дараа нь САНАХ ОЙД бүх INSERT-ийг задалж (EXPLODE), бодит 3D биетүүдийг
     хэмжинэ. Файлыг ХЭЗЭЭ Ч ХАДГАЛАХГҮЙ — эх файл хэвээр үлдэнэ.
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
    '(setvar "QAFLAGS" 0)',
    '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
    # ---- 1. Блок бүрийн доторх entity-үүдийг тоолох ----
    # Бүлэг -2 нь блокийн эхний entity-г заана.
    '(setq B (tblnext "BLOCK" T))',
    "(while B",
    ' (if (not (wcmatch (cdr (assoc 2 B)) "`**"))',
    "   (progn (setq nm (cdr (assoc 2 B)) e (cdr (assoc -2 B)) cnt 0 tys nil)",
    "     (while e (setq ty (cdr (assoc 0 (entget e))) cnt (1+ cnt))",
    "       (setq pp (assoc ty tys))",
    "       (if pp (setq tys (subst (cons ty (1+ (cdr pp))) pp tys))",
    "              (setq tys (cons (cons ty 1) tys)))",
    "       (setq e (entnext e)))",
    '     (PR (strcat "BLK|" nm "|" (itoa cnt)))',
    '     (foreach q tys (PR (strcat "BLKTYPE|" nm "|" (car q) "|" (itoa (cdr q)))))))',
    ' (setq B (tblnext "BLOCK")))',
    # ---- 2. Санах ойд бүх INSERT-ийг задлах ----
    "(setq pass 0)",
    "(while (and (< pass 6)",
    '            (setq SS (ssget "_X" (list (cons 0 "INSERT")))))',
    ' (PR (strcat "EXPLODE|pass" (itoa pass) "|" (itoa (sslength SS))))'
    ' (command "_.EXPLODE" SS "")'
    f" {DRAIN}"
    " (setq pass (1+ pass)))",
    # ---- 3. Задалсны дараах бодит бүтэц ----
    "(setq E (entnext) N 0 TYPES nil)",
    "(while E"
    " (setq D (entget E) TY (cdr (assoc 0 D)) K TY)"
    " (setq P (assoc K TYPES))"
    " (if P (setq TYPES (subst (cons K (1+ (cdr P))) P TYPES))"
    "        (setq TYPES (cons (cons K 1) TYPES)))"
    " (setq N (1+ N) E (entnext E)))",
    '(PR (strcat "FLATENTS|" (itoa N)))',
    '(foreach p TYPES (PR (strcat "FLATTYPE|" (car p) "|" (itoa (cdr p)))))',
    # ---- 4. 3D биетүүдийг хэмжих ----
    '(setq SS (ssget "_X" (list (cons 0 "3DSOLID"))))',
    '(PR (strcat "SOLIDCOUNT|" (if SS (itoa (sslength SS)) "0")))',
    "(setq i 0 MAXS 25 TOTV 0.0)",
    "(while (and SS (< i (sslength SS)) (< i MAXS))"
    ' (command "_.MASSPROP" (ssadd (ssname SS i)) "" "_N")'
    f" {DRAIN}"
    " (setq i (1+ i)))",
    '(if (and SS (> (sslength SS) MAXS)) (PR (strcat "SOLIDSKIP|" (itoa (- (sslength SS) MAXS)))))',
    # ---- 5. Задалсны дараах нийт хязгаар ----
    '(command "_.ZOOM" "_E")',
    DRAIN,
    "(defun F (x) (rtos x 2 3))",
    '(PR (strcat "FLATMIN|" (F (car (getvar "EXTMIN"))) "," (F (cadr (getvar "EXTMIN")))'
    ' "," (F (caddr (getvar "EXTMIN")))))',
    '(PR (strcat "FLATMAX|" (F (car (getvar "EXTMAX"))) "," (F (cadr (getvar "EXTMAX")))'
    ' "," (F (caddr (getvar "EXTMAX")))))',
    '(PR "DONE")',
    # ХАДГАЛАХГҮЙ — эх файл хөндөгдөхгүй.
    "(princ)",
]


def inspect(dwg: Path) -> str:
    scr = dwg.parent / (dwg.stem + "-deep.scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(FORMS) + "\r\n").encode("utf-8"))
    proc = subprocess.run(
        [str(EXE), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=1800,
        check=False,
        cwd=str(dwg.parent),
    )
    scr.unlink(missing_ok=True)
    return (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")


def report(dwg: Path, text: str) -> None:
    def tags(name: str) -> list[str]:
        pre = "@@@" + name + "|"
        return [ln.strip()[len(pre) :] for ln in text.splitlines() if ln.strip().startswith(pre)]

    print("\n" + "=" * 74)
    print(f"{dwg.name}   ({dwg.stat().st_size:,} byte)")
    print("=" * 74)

    if "@@@DONE" not in text:
        print("  !! дуусгаж чадсангүй")
        for e in [ln.strip() for ln in text.splitlines() if "; error" in ln.lower()][:5]:
            print(f"     {e[:110]}")
        return

    blks = tags("BLK")
    if blks:
        print(f"\n  Блокийн агуулга ({len(blks)}):")
        for b in blks:
            nm, _, cnt = b.rpartition("|")
            inner = [t for t in tags("BLKTYPE") if t.startswith(nm + "|")]
            detail = ", ".join(t[len(nm) + 1 :].replace("|", " x") for t in inner)
            print(f"    {nm:<28s} {cnt:>5s} entity   {detail}")

    ex = tags("EXPLODE")
    if ex:
        print("\n  Задлалт:")
        for e in ex:
            p, _, n = e.rpartition("|")
            print(f"    {p}: {n} INSERT задлав")

    print(f"\n  Задалсны дараах entity: {(tags('FLATENTS') or ['?'])[0]}")
    for line in tags("FLATTYPE"):
        ty, _, cnt = line.rpartition("|")
        print(f"    {ty:<20s} {cnt:>6s}")

    lo = (tags("FLATMIN") or ["?"])[0]
    hi = (tags("FLATMAX") or ["?"])[0]
    print(f"\n  Хязгаар: {lo}  ->  {hi}")
    try:
        a = [float(x) for x in lo.split(",")]
        c = [float(x) for x in hi.split(",")]
        print(f"  Хэмжээ : {c[0] - a[0]:.1f} x {c[1] - a[1]:.1f} x {c[2] - a[2]:.1f}")
    except (ValueError, IndexError):
        pass

    ns = (tags("SOLIDCOUNT") or ["0"])[0]
    vols = [float(v) for v in re.findall(r"Volume:\s*([\d.eE+-]+)", text)]
    if vols:
        print(f"\n  3D бие ({ns}), эхний {len(vols)}-г хэмслээ:")
        for i, v in enumerate(vols):
            print(f"    #{i:<3d} {v:>14,.0f} мм³ = {v / 1e6:>9.4f} л")
        print(f"    {'НИЙТ':<4s} {sum(vols):>14,.0f} мм³ = {sum(vols) / 1e6:>9.4f} л")
    skip = tags("SOLIDSKIP")
    if skip:
        print(f"    (бас {skip[0]} бие хэмжигдээгүй)")


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
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
