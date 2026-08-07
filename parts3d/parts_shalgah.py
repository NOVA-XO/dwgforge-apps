"""Эд ангиудын эзэлхүүнийг хэмжиж, дотоод нүх цоологдсон эсэхийг батална.

MASSPROP нь ACIS модельчлэгчээр бодит эзэлхүүнийг тооцно. Хоолой бүтэн
цилиндр байвал энэ шалгалт шууд илчилнэ.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from partsan import EXE, load_table

OUTDIR = Path(__file__).parent / "parts"

FORMS = [
    '(setvar "CMDECHO" 0)',
    '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
    '(setq ss (ssget "_X" (list (cons 0 "3DSOLID"))))',
    '(PR (strcat "SOLIDS|" (if ss (itoa (sslength ss)) "0")))',
    '(if ss (command "_.MASSPROP" ss "" "_N"))',
    '(setq d 0) (while (and (/= (getvar "CMDNAMES") "") (< d 20)) (command "") (setq d (1+ d)))',
    '(PR "DONE")',
    "(princ)",
]


def measure(dwg: Path) -> tuple[int, float] | None:
    scr = dwg.with_name(dwg.stem + "-mass.scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(FORMS) + "\r\n").encode("utf-8"))
    proc = subprocess.run(
        [str(EXE), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=300,
        check=False,
        cwd=str(dwg.parent),
    )
    text = (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")
    scr.unlink(missing_ok=True)
    ns = re.search(r"@@@SOLIDS\|(\d+)", text)
    vol = re.search(r"Volume:\s*([\d.eE+-]+)", text)
    if ns is None or vol is None:
        return None
    return int(ns[1]), float(vol[1])


def main() -> int:
    t = load_table()
    od, idd = t.od(100), t.id_(100)
    ro, ri = od / 2.0, idd / 2.0

    # Хоолой ба тохойн эзэлхүүнийг яг тааруулж бодож болно.
    pipe_exact = math.pi * (ro**2 - ri**2) * 500.0
    # Тохой: торын хэсэг. Бүтэн тор = 2*pi^2*R*r^2
    rb = 1.5 * 100
    elbow90 = (90.0 / 360.0) * 2 * math.pi**2 * rb * (ro**2 - ri**2)
    elbow45 = (45.0 / 360.0) * 2 * math.pi**2 * rb * (ro**2 - ri**2)
    # Шилжилт: гадна конус - дотоод конус (таслагдсан конусын эзэлхүүн)
    od2, id2 = t.od(80), t.id_(80)
    ln = max(3.0 * (od - od2), od)

    def frustum(r1: float, r2: float, h: float) -> float:
        return math.pi * h / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)

    red_exact = frustum(od / 2, od2 / 2, ln) - frustum(idd / 2, id2 / 2, ln)

    # Бүтэн (нүхгүй) хувилбарын эзэлхүүн — үүнээс бага байх ёстой
    pipe_solid = math.pi * ro**2 * 500.0

    checks: list[tuple[str, float | None, float | None]] = [
        ("Pipe-DN100-L500", pipe_exact, pipe_solid),
        ("Elbow-DN100-90deg", elbow90, None),
        ("Elbow-DN100-45deg", elbow45, None),
        ("Tee-DN100x100", None, None),
        ("Reducer-DN100x80", red_exact, None),
        ("Flange-DN100", None, None),
    ]

    print(f"{'эд анги':24s} {'бие':>4} {'хэмссэн (л)':>12} {'тооцсон (л)':>12} {'зөрүү':>8}")
    print("-" * 68)
    bad = 0
    for name, exact, solid_bound in checks:
        f = OUTDIR / f"{name}.dwg"
        got = measure(f)
        if got is None:
            print(f"{name:24s}  MASSPROP уншигдсангүй")
            bad += 1
            continue
        count, vol = got
        line = f"{name:24s} {count:>4} {vol / 1e6:>12.4f}"
        if exact is not None:
            d = (vol - exact) / exact * 100.0
            line += f" {exact / 1e6:>12.4f} {d:>7.2f}%"
            if abs(d) > 0.5:
                line += "  <-- ЗӨРӨВ"
                bad += 1
        else:
            line += f" {'—':>12} {'—':>8}"
        if solid_bound is not None and vol >= solid_bound * 0.99:
            line += "  <-- НҮХ АЛГА!"
            bad += 1
        if count != 1:
            line += f"  <-- {count} бие"
            bad += 1
        print(line)

    print()
    print(f"Лавлах: DN100 бүтэн цилиндр L500 = {pipe_solid / 1e6:.4f} л")
    print(f"        хөндий хоолой            = {pipe_exact / 1e6:.4f} л  (5 дахин бага)")
    print(f"\n{len(checks) - bad}/{len(checks)} шалгалт давлаа")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
