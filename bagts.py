r"""Багц үүсгэгч — эд ангийн бүтэн сан нэг дор гаргана.

Ажиллуулах:
    .\.venv\Scripts\python.exe parts3d\bagts.py                 # өгөгдмөл багц
    .\.venv\Scripts\python.exe parts3d\bagts.py --dn 50 80 100  # тодорхой DN
    .\.venv\Scripts\python.exe parts3d\bagts.py --buh           # хүснэгтийн БҮХ DN
    .\.venv\Scripts\python.exe parts3d\bagts.py --dn 100 --zovhon Pipe Elbow

Эд анги бүр ~4-8 секунд авна. `--buh` нь 14 DN x 7 хувилбар = ~10 минут.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parts import Elbow, Flange, Pipe, Reducer, Tee, emit, run
from partsan import Table, load_table

from dwgforge.backends import find_accoreconsole

OUTDIR = Path(__file__).parent / "parts"

# Өгөгдмөл DN багц — хамгийн түгээмэл хэмжээнүүд.
DEFAULT_DN = (50, 80, 100, 150)

# Тухайн DN-д ямар эд ангиуд үүсгэх вэ. Шинэ хувилбар нэмэхэд энд нэмнэ.
BUILDERS: dict[str, object] = {
    "Pipe": lambda dn, t: [Pipe(dn=dn, length=500.0)],
    "Elbow": lambda dn, t: [Elbow(dn=dn, angle=90.0), Elbow(dn=dn, angle=45.0)],
    "Tee": lambda dn, t: [Tee(dn=dn)],
    "Reducer": lambda dn, t: _reducer(dn, t),
    "Flange": lambda dn, t: [Flange(dn=dn)],
}


def _reducer(dn: int, t: Table) -> list[object]:
    """Тухайн DN-ээс нэг доод хэмжээ рүү шилжих хэсэг. Хамгийн жижигт нь алга."""
    sizes = sorted((int(k) for k in t.dn), key=int)
    if dn not in sizes or sizes.index(dn) == 0:
        return []
    return [Reducer(dn=dn, dn_small=sizes[sizes.index(dn) - 1])]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bagts", description="Эд ангийн багц үүсгэгч")
    ap.add_argument("--dn", type=int, nargs="+", help="ямар DN хэмжээнүүд")
    ap.add_argument("--buh", action="store_true", help="хүснэгтийн бүх DN")
    ap.add_argument(
        "--zovhon",
        nargs="+",
        choices=sorted(BUILDERS),
        help="зөвхөн эдгээр эд ангийг",
    )
    ap.add_argument("--hool", action="store_true", help="жагсаалтыг харуулаад зогсох")
    args = ap.parse_args(argv)

    exe = find_accoreconsole()
    if exe is None:
        print("accoreconsole олдсонгүй — AutoCAD 2026 суусан эсэхийг шалгана уу.")
        return 1

    table = load_table()
    all_dn = sorted((int(k) for k in table.dn), key=int)
    if args.buh:
        dns = all_dn
    elif args.dn:
        dns = args.dn
    else:
        dns = list(DEFAULT_DN)

    bad = [d for d in dns if d not in all_dn]
    if bad:
        print(f"хүснэгтэд байхгүй DN: {bad}. Байгаа: {all_dn}")
        return 1

    kinds = args.zovhon or sorted(BUILDERS)

    jobs = []
    for dn in dns:
        for kind in kinds:
            jobs.extend(BUILDERS[kind](dn, table))  # type: ignore[operator]

    print(f"DN: {dns}")
    print(f"Эд анги: {', '.join(kinds)}")
    print(
        f"Нийт {len(jobs)} файл, ойролцоогоор {len(jobs) * 6 // 60}-{len(jobs) * 9 // 60} минут\n"
    )

    if args.hool:
        for j in jobs:
            print("   ", j.name())  # type: ignore[attr-defined]
        return 0

    OUTDIR.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    ok = 0
    for i, part in enumerate(jobs, 1):
        print(f"[{i:>3}/{len(jobs)}] ", end="")
        ok += run(emit([part], table), OUTDIR / f"{part.name()}.dwg")  # type: ignore[attr-defined]

    mins = (time.monotonic() - started) / 60.0
    total_kb = sum(f.stat().st_size for f in OUTDIR.glob("*.dwg")) / 1024
    print(f"\n{ok}/{len(jobs)} амжилттай · {mins:.1f} минут")
    print(f"Сан: {OUTDIR}  ({len(list(OUTDIR.glob('*.dwg')))} файл, {total_kb:,.0f} KB)")
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
