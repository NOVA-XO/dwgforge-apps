r"""tulguur2d — ЭСП-ийн каталогийн тулгуурыг 2D DWG зураг болгох команд мөр.

Жишээ:
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguur.py --jagsaalt
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguur.py П110-1 У220-2
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguur.py --hutsel 110 --angilal завсрын
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguur.py --toim --hutsel 35
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguur.py --buh

`--jagsaalt` нь AutoCAD-гүйгээр ажиллана — зөвхөн хүснэгтийг хэвлэнэ.
Бусад тохиолдолд accoreconsole.exe хэрэгтэй (AutoCAD / Civil 3D).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge.backends import find_accoreconsole
from husnegt import neg_huudas
from tulguurdata import katalog
from tulguursan import (
    ANKER,
    CONFIG,
    GAN,
    JB,
    SALAA,
    SHILJILT,
    TOGSGOL,
    ZAVSAR,
    ZAVSAR_ONTSOG,
    Tulguur,
)
from zurag import OUTDIR, bicheh, toim

ANGILAL = (ZAVSAR, ZAVSAR_ONTSOG, ANKER, TOGSGOL, SALAA, SHILJILT)


def jagsaalt(bag: tuple, *, delgerengui: bool = False) -> None:
    """Тулгуурын жагсаалтыг хүснэгтээр хэвлэнэ (AutoCAD хэрэггүй)."""
    print(f"{'шифр':<24}{'кВ':>5}{'цеп':>4}  {'ангилал':<16}{'өндөр':>7}{'траверс':>8}"
          f"{'масс, кг':>10}  лист")
    print("-" * 90)
    for t in bag:
        jin = f"{t.jin:,.0f}".replace(",", " ") if t.jin is not None else "-"
        oir = "" if t.batalgaa else " ≈"
        print(f"{t.shifr:<24}{t.hutsel:>5}{t.tsep:>4}  {t.angilal:<16}"
              f"{t.undur:>7.1f}{t.dood:>8.1f}{jin:>10}  {t.huudas}{oir}")
        if delgerengui and t.temdeglel:
            print(f"    {t.temdeglel}")
    print(f"\n{len(bag)} тулгуур")


def main(argv: list[str] | None = None) -> int:
    """Командын мөрийг задлаад зураг үүсгэнэ."""
    p = argparse.ArgumentParser(
        prog="tulguur",
        description="ЭСП каталог (5713тм-т2) — тулгуурын 2D эскиз DWG болгох",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("shifr", nargs="*", help="зурах тулгуурын шифр (жишээ: П110-1)")
    p.add_argument("--hutsel", type=int, help="хүчдэлээр шүүх: 35 110 150 220 330 500")
    p.add_argument("--angilal", choices=ANGILAL, help="ангилалаар шүүх")
    p.add_argument("--material", choices=(GAN, JB), help="материалаар шүүх")
    p.add_argument("--tsep", type=int, choices=(1, 2), help="цепийн тоогоор шүүх")
    p.add_argument("--hai", default="", help="шифрээс хэсэгчлэн хайх")
    p.add_argument("--buh", action="store_true", help="каталогийн БҮХ тулгуур")
    p.add_argument("--toim", action="store_true", help="сонгосон бүгдийг НЭГ хуудсанд")
    p.add_argument("--bagana", type=int, default=6, help="тойм хуудасны багана (өгөгдмөл 6)")
    p.add_argument("--jagsaalt", action="store_true", help="зөвхөн жагсаалт (AutoCAD хэрэггүй)")
    p.add_argument("--delgerengui", action="store_true", help="жагсаалтад тэмдэглэл нэмнэ")
    p.add_argument("--hemjeesgui", action="store_true", help="хэмжээсгүй зурна")
    p.add_argument("--a3", action="store_true",
                   help="танай АЗ хуудасны блок дотор, тайлбар ба булангийн хүснэгттэй")
    p.add_argument("--tosol", default="", help="A3: төслийн нэр (булангийн хүснэгтэд)")
    p.add_argument("--ognoo", default="", help="A3: огноо")
    p.add_argument("--zurag-shifr", default="", help="A3: зургийн шифр (булангийн хүснэгтэд)")
    p.add_argument("--tugjee-arilgah", action="store_true",
                   help="үлдэгдэл .dwl түгжээг устгана (AutoCAD-д нээлттэй зураг байх ёсгүй)")
    p.add_argument("--out", type=Path, default=OUTDIR, help=f"гаралтын хавтас ({OUTDIR.name})")
    a = p.parse_args(argv)

    k = katalog()
    if CONFIG.is_file():
        # Чимээгүй дарж бичихгүй: хэмжээс кодод байгаагаас өөр байвал хаанаас
        # ирснийг нь хэлнэ — эс тэгвээс "яагаад өөр гарав?" гэсэн асуулт үлдэнэ.
        print(f"Хэмжээсийг {CONFIG.name}-оос авч байна (устгавал кодын утга сэргэнэ).")

    if a.shifr:
        try:
            bag = tuple(k.ol(s) for s in a.shifr)
        except KeyError as exc:
            print(exc)
            return 1
    elif a.buh:
        bag = k.buh
    elif any((a.hutsel, a.angilal, a.material, a.tsep, a.hai)):
        bag = k.shuult(
            hutsel=a.hutsel, angilal=a.angilal, material=a.material,
            tsep=a.tsep, hai=a.hai,
        )
    else:
        p.print_help()
        print(f"\nКаталогт {len(k)} тулгуур байна. Жагсаалт: --jagsaalt")
        return 0

    if not bag:
        print("Шүүлтүүрт таарсан тулгуур алга.")
        return 1

    if a.jagsaalt:
        jagsaalt(bag, delgerengui=a.delgerengui)
        return 0

    if find_accoreconsole() is None:
        print("accoreconsole олдсонгүй. AutoCAD/Civil 3D суулгах эсвэл "
              "DWGFORGE_ACCORECONSOLE-ыг тохируулна уу.")
        return 1

    a.out.mkdir(parents=True, exist_ok=True)
    # Тойм нь ГАНЦ файл бичдэг тул зөвхөн түүний түгжээ хамаатай; тус тусдаа
    # бичих үед бүлгийн файл бүрийг шалгана.
    ner = _toim_ner(a) if a.toim else ""
    if a.toim:
        hyanah: Sequence = (_Ner(ner),)
    else:
        hyanah = [_Ner(_fayl_ner(t, a3=a.a3)) for t in bag]
    if _tugjee(hyanah, a.out, arilgah=a.tugjee_arilgah):
        return 1
    ehleh = time.monotonic()

    if a.toim:
        ok = toim(bag, a.out / f"{ner}.dwg", bagana=a.bagana, hemjees=not a.hemjeesgui)
        print(f"\n{time.monotonic() - ehleh:.0f} секунд -> {a.out / f'{ner}.dwg'}")
        return 0 if ok else 1

    print(f"{len(bag)} тулгуур -> {a.out}")
    if a.a3:
        amjilt = sum(
            neg_huudas(
                t, a.out / f"{_fayl_ner(t, a3=True)}.dwg", tosol=a.tosol, ognoo=a.ognoo,
                shifr_zurag=a.zurag_shifr,
            )
            for t in bag
        )
    else:
        amjilt = sum(
            bicheh(t, a.out / f"{_fayl_ner(t, a3=False)}.dwg", hemjees=not a.hemjeesgui)
            for t in bag
        )
    hugatsaa = time.monotonic() - ehleh
    print(f"\n{amjilt}/{len(bag)} амжилттай, {hugatsaa:.0f} секунд -> {a.out}")
    return 0 if amjilt == len(bag) else 1


@dataclass(frozen=True, slots=True)
class _Ner:
    """`_tugjee`-д зөвхөн файлын нэр өгөх жижиг боодол."""

    ner: str


def _fayl_ner(t: Tulguur, *, a3: bool) -> str:
    """Гаралтын файлын нэр. АЗ хуудас нь эскизийг ДАРАХГҮЙ — өөр нэртэй.

    Веб дээрх нэршилтэй нэг байх ёстой: тэнд `<нэр>-A3.dwg` гэж хадгалдаг.
    Зөрвөл нэг тулгуурын хоёр хувилбар нэг файл руу бичигдэнэ.
    """
    return f"{t.ner}-A3" if a3 else t.ner


def _tugjee(bag: Sequence, out: Path, *, arilgah: bool) -> bool:
    """ЗУРАХ ГЭЖ БУЙ зургуудын `.dwl` түгжээг шалгана. Зогсоох ёстой бол True.

    accoreconsole нь `.dwl` байвал зургийг зөвхөн уншихаар нээдэг тул SAVEAS
    бүтэлгүйтэнэ. Түгжээ нь ХОЁР шалтгаанаар үүснэ: зураг AutoCAD-д ҮНЭХЭЭР
    нээлттэй байна, эсвэл өмнөх ажиллагаа таслагдаад үлдэгдэл үлдсэн. Эхнийх
    нь хэрэглэгчийн нээлттэй зураг тул чимээгүй устгаж болохгүй — асууна.

    Зөвхөн энэ удаагийн бүлгийг шалгана: хажууд нь өөр нэг зураг нээлттэй
    байгаа нь холбоогүй ажлыг зогсоох шалтгаан биш.
    """
    tugjee = [
        f for t in bag for f in (out / f"{t.ner}.dwl", out / f"{t.ner}.dwl2") if f.is_file()
    ]
    if not tugjee:
        return False
    if not arilgah:
        print(f"{len(tugjee)} түгжээний файл байна — эдгээр зураг дахин бичигдэхгүй:")
        for f in tugjee[:8]:
            print(f"  {f.name}")
        if len(tugjee) > 8:
            print(f"  ... нийт {len(tugjee)}")
        print("AutoCAD-д нээлттэй зураг байхгүй бол --tugjee-arilgah гэж дахин ажиллуулна уу.")
        return True
    ustsan, uldsen = 0, []
    for f in tugjee:
        try:
            f.unlink(missing_ok=True)
            ustsan += 1
        except OSError:
            # Файлыг өөр процесс барьж байна — энэ бол ҮНЭХЭЭР нээлттэй зураг,
            # үлдэгдэл биш. Хүчлэхгүй: хэрэглэгчийн ажлыг эвдэж болзошгүй.
            uldsen.append(f.name)
    if ustsan:
        print(f"{ustsan} үлдэгдэл түгжээ устлаа.")
    if uldsen:
        print("Дараах зураг AutoCAD-д ҮНЭХЭЭР нээлттэй байна — хааж байж дахин ажиллуулна уу:")
        for ner in uldsen:
            print(f"  {ner}")
        return True
    return False


def _toim_ner(a: argparse.Namespace) -> str:
    """Тойм хуудасны файлын нэрийг шүүлтүүрээс гаргана."""
    hesg = ["toim"]
    if a.hutsel:
        hesg.append(f"{a.hutsel}kV")
    if a.tsep:
        hesg.append(f"{a.tsep}tsep")
    if a.material == JB:
        hesg.append("jb")
    elif a.material == GAN:
        hesg.append("gan")
    if a.angilal:
        hesg.append({ZAVSAR: "zavsar", ZAVSAR_ONTSOG: "zavsar-ontsog", ANKER: "anker",
                     TOGSGOL: "togsgol", SALAA: "salaa", SHILJILT: "shiljilt"}[a.angilal])
    if a.buh:
        hesg.append("buh")
    return "-".join(hesg)


if __name__ == "__main__":
    raise SystemExit(main())
