r"""Тулгуурын 2 хэмжээст эскиз — каталогийн мөрийг DWG зураг болгоно.

Зургийн НЭГЖ нь МЕТР (1 нэгж = 1 м). Тулгуур нь урдаас харсан харагдац:
бие, траверс, тросостойк, оттяжка, газрын шугам, хэмжээс, паспортын бичээс.

Силуэтийн хэв бүрт нэг зурагч:

    сүлжээ        свободностоящая решётчатая (ихэнх ган тулгуур)
    оттяжкатай    нэг нарийн бие + хоёр оттяжка
    портал        хоёр босоо хөл + дээд хөндлөвч (ЖБ портал, ПВС)
    портал-татлага ВЛ 500 кВ-ын ПБ, ПУБ — налуу хөл + оттяжка
    шон           ганц төмөр бетон шон
    хос шон       хоёр шон + хөндлөвч, X холбоос
    гурван шон    гурван бие даасан шон (К, У 500 кВ, УБМ)

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe tulguur2d\\zurag.py П110-1
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge import Drawing, DrawingOptions, write_dwg
from dwgforge.backends.accore import AccoreConsoleBackend
from dwgforge.errors import DwgForgeError
from tulguursan import (
    GURAV_SHON,
    HOS_SHON,
    JB,
    PORTAL,
    PORTAL_T,
    POSTAVKA,
    SHON,
    TATLAGA,
    Tulguur,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

OUTDIR = Path(__file__).parent / "zurag"
ZAGVAR_JSON = Path(__file__).parent / "zagvar.json"


def _zagvar() -> dict:
    """Компанийн стандартыг ачаална (`zagvar.py holboh`-оор үүсдэг).

    Файл байхгүй бол хоосон буцаана — тэр үед бидний өөрсдийн давхаргын нэр,
    "Standard" бичгийн хэв ажиллана. Ингэснээр апп нь стандартгүй ч ажилладаг,
    стандарттай бол түүн рүү бүрэн шилждэг.
    """
    if not ZAGVAR_JSON.is_file():
        return {}
    try:
        return json.loads(ZAGVAR_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


ZAGVAR = _zagvar()
HOLBOLT: dict[str, str] = {k: v for k, v in (ZAGVAR.get("holbolt") or {}).items() if v}
BICHGIIN_HEV: str = ZAGVAR.get("bichgiin_hev") or "Standard"


def lay(uureg: str) -> str:
    """Дотоод үүргийн нэрийг компанийн давхаргын нэр рүү хөрвүүлнэ."""
    return HOLBOLT.get(uureg, uureg)


def uram() -> Path | None:
    """Үрлэг (загвар) DWG — байвал accoreconsole үүн дээр зургаа барина."""
    zam = ZAGVAR.get("uram") or ""
    if zam:
        p = Path(zam)
        return p if p.is_file() else None
    p = Path(__file__).parent / "uram" / "zagvar-uram.dwg"
    return p if p.is_file() else None

# -- давхаргууд (нэр, өнгө) -------------------------------------------------

L_BIE = "ТУЛГУУР-БИЕ"
L_SUL = "ТУЛГУУР-СҮЛЖЭЭ"
L_TOR = "ТУЛГУУР-ТРАВЕРС"
L_TROS = "ТУЛГУУР-ТРОСОСТОЙК"
L_TAT = "ТУЛГУУР-ОТТЯЖКА"
L_GAZAR = "ГАЗАР"
L_TENH = "ТЭНХЛЭГ"
L_HEM = "ХЭМЖЭЭС"
L_BICHIG = "БИЧИГ"
L_HUREE = "ХҮРЭЭ"

DAVHARGA: tuple[tuple[str, int], ...] = (
    (L_BIE, 7),
    (L_SUL, 8),
    (L_TOR, 3),
    (L_TROS, 4),
    (L_TAT, 6),
    (L_GAZAR, 2),
    (L_TENH, 8),
    (L_HEM, 1),
    (L_BICHIG, 7),
    (L_HUREE, 8),
)

# Бие нь суурийн өргөнөөс доод траверс хүртэл нарийсаад, дээшээ тогтмол болно —
# каталогийн эскизүүд яг ийм хэлбэртэй.
BAGA_ORGON = 0.30  # м, биеийн хамгийн нарийн өргөн
SHON_ORGON = 0.56  # м, төмөр бетон стойкийн диаметр (СК цуврал)

# --------------------------------------------------------------------------
# Хийцийн пропорц — серия 3.407.2-170.2 06КМ «Геометрическая схема» (1П110-2)
# ба ЭСП каталогийн эскизээс (лист 18, 23) хэмжсэн.
#
# ЭСП каталог нь СИЛУЭТ л өгдөг: раскос, ферм зурдаггүй. Тиймээс сүлжээний
# пропорцыг ажлын зургийн цомгоос авав. Гишүүн бүрийг хуулаагүй — зөвхөн
# хэмжээ тогтоох дүрмүүдийг авсан:
#
#   * Панелийн өндөр нь өргөнөөс хамаардаггүй, ТОГТМОЛ модультай. 06КМ дээр
#     бие нь 2200 мм-ийн панелиар дээшилж, хугарлын дээр 1800 болдог.
#   * Бие нь нэг шулуун нарийсалт БИШ — «линия гиба» дээр хугарч, дээшээ
#     бараг зэрэгцээ нарийн иш болно (огтлол 1-1: 3060, 2-2: 2197, 11-11: 350).
#   * Тросостойк нь ишний өргөнөөсөө оройд нийлдэг нарийн жад.
# --------------------------------------------------------------------------

PANEL_BIE = 2.2  # м, хугарлаас доош биеийн панелийн модуль (06КМ: 2200)
PANEL_ISH = 1.8  # м, хугарлаас дээш ишний панель (06КМ: 1800)
ISH_HARTSAA = 0.30  # ишний өргөн = суурийн өргөний хувь
TOR_UNDUR = 0.55  # м, траверсын үндэсний өндөр
TOR_UZUUR = 0.14  # м, траверсын үзүүрийн өндөр
TOR_ULGUUR = 0.35  # м, утас өлгөх цэгийн урт
UZUUR_MUR = 0.80  # тросостойкийн суурь = ишний өргөний хувь (мөр үүсгэнэ)
UZUUR_HESEG = 0.72  # өндрийнх нь энэ хувь нь сүлжээтэй, дээр нь нимгэн үзүүр
UZUUR_NARIIN = 0.30  # сүлжээн хэсгийн оройд үлдэх өргөн (суурийн хувь)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


class Zurag:
    """Нэг Drawing дотор олон тулгуур зурах туслах — бүх шугам офсеттой орно."""

    def __init__(self, dwg: Drawing) -> None:
        """Давхаргуудыг бүртгээд эхэлнэ."""
        self.dwg = dwg
        # Компанийн давхарга үрлэг зурагт аль хэдийн байвал dwgforge түүнийг
        # дахин тодорхойлохгүй (tblsearch шалгалт) — өнгө, шугамын төрөл нь
        # танайхаар үлдэнэ. Байхгүй бол бидний өгөгдмөл өнгөөр үүснэ.
        for ner, ongo in DAVHARGA:
            dwg.ensure_layer(lay(ner), color=ongo)
        self.ox = 0.0
        self.oz = 0.0

    def shiljuuleh(self, ox: float, oz: float) -> None:
        """Дараагийн элементүүдийн офсетыг тавина."""
        self.ox, self.oz = ox, oz

    # -- анхдагч элементүүд ------------------------------------------------

    def shugam(self, x0: float, z0: float, x1: float, z1: float, layer: str) -> None:
        """Нэг шулуун."""
        self.dwg.line(
            (self.ox + x0, self.oz + z0), (self.ox + x1, self.oz + z1), layer=lay(layer)
        )

    def zam(self, tsegs: Sequence[tuple[float, float]], layer: str, *, hulhii: bool = False) -> None:
        """Олон цэгийн полилиниа."""
        self.dwg.polyline(
            [(self.ox + x, self.oz + z) for x, z in tsegs], closed=hulhii, layer=lay(layer)
        )

    def toirog(self, x: float, z: float, r: float, layer: str = L_BICHIG) -> None:
        """Тойрог. Офсеттой — `zam`, `shugam`-тай нэг координатын системд байна."""
        self.dwg.circle((self.ox + x, self.oz + z), r, layer=lay(layer))

    def bichig(
        self,
        x: float,
        z: float,
        text: str,
        h: float,
        *,
        layer: str = L_BICHIG,
        tov: bool = False,
    ) -> None:
        """Нэг мөр текст. `tov=True` бол хэвтээ голлоно."""
        self.dwg.text(
            (self.ox + x, self.oz + z),
            text,
            height=h,
            style=BICHGIIN_HEV,
            halign=1 if tov else 0,
            align_point=(self.ox + x, self.oz + z) if tov else None,
            layer=lay(layer),
        )

    # -- хэмжээс -----------------------------------------------------------

    def hem_bosoo(self, x: float, z0: float, z1: float, text: str, h: float) -> None:
        """Босоо хэмжээсийн шугам, хоёр үзүүрт зураас, дундуур нь бичээс."""
        self.shugam(x, z0, x, z1, L_HEM)
        for z in (z0, z1):
            self.shugam(x - h * 0.5, z - h * 0.5, x + h * 0.5, z + h * 0.5, L_HEM)
        self.dwg.text(
            (self.ox + x - h * 0.4, self.oz + (z0 + z1) / 2.0),
            text,
            height=h,
            style=BICHGIIN_HEV,
            rotation=math.pi / 2.0,
            halign=1,
            align_point=(self.ox + x - h * 0.4, self.oz + (z0 + z1) / 2.0),
            layer=lay(L_HEM),
        )

    def hem_hevtee(self, z: float, x0: float, x1: float, text: str, h: float) -> None:
        """Хэвтээ хэмжээс."""
        self.shugam(x0, z, x1, z, L_HEM)
        for x in (x0, x1):
            self.shugam(x - h * 0.5, z - h * 0.5, x + h * 0.5, z + h * 0.5, L_HEM)
        self.bichig((x0 + x1) / 2.0, z + h * 0.35, text, h, layer=L_HEM, tov=True)


def _too(v: float) -> str:
    """Хэмжээсийн тоог метрээр цэвэрхэн бичнэ: 19.0 -> '19,0'."""
    return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",") or "0"


# --------------------------------------------------------------------------
# Биеийн хэлбэрүүд
# --------------------------------------------------------------------------


def _gib(t: Tulguur) -> float:
    """«Линия гиба» — биеийн налалт хугарах өндөр (м).

    Доод траверсын түвшин. ЭСП эскиз ба 06КМ хоёулаа энд хугарлыг харуулдаг:
    доор нь салаавчилсан бие, дээр нь нарийн иш.
    """
    return max(min(t.dood, t.undur), 0.1)


def _ish_hagas(t: Tulguur) -> float:
    """Хугарлаас дээших ишний ХАГАС өргөн (м)."""
    return max(t.suuri * ISH_HARTSAA, t.orgil, BAGA_ORGON) / 2.0


def _orgon(t: Tulguur, z: float) -> float:
    """Биеийн ХАГАС өргөн `z` өндөрт (м) — хугарлын шугамаар хоёр хэсэг."""
    gib = _gib(t)
    ish = _ish_hagas(t)
    doorh = max(t.suuri / 2.0, ish)
    orgil = min(max(t.orgil / 2.0, BAGA_ORGON / 2.0), ish)
    if z <= gib:
        return _lerp(doorh, ish, z / gib)
    return _lerp(ish, orgil, (z - gib) / max(t.undur - gib, 1e-6))


def _tuvshin(z0: float, z1: float, modul: float) -> list[float]:
    """`z0`..`z1`-ийг `modul`-д хамгийн ойр тэнцүү панель болгон хуваана.

    Жинхэнэ тулгуурын панель нь тогтмол модультай (06КМ: 2200 / 1800), тэр
    модуль нь хэрчмийн урттай яг таардаггүй тул хамгийн ойр бүхэл тоонд
    хуваана — панелиуд тэнцүү, зангилаанууд нь хэрчмийн үзүүрт яг тохирно.
    """
    urt = z1 - z0
    if urt <= 1e-6:
        return [z0]
    n = max(1, round(urt / modul))
    return [z0 + urt * i / n for i in range(n + 1)]


def _suljee_zurah(z: Zurag, t: Tulguur, tuvshin: list[float]) -> None:
    """Өгсөн түвшингүүдийн хооронд X раскос ба хөндлөвч татна."""
    for i in range(len(tuvshin) - 1):
        za, zb = tuvshin[i], tuvshin[i + 1]
        a0, a1 = _orgon(t, za), _orgon(t, zb)
        z.shugam(-a1, zb, a1, zb, L_SUL)
        z.shugam(-a0, za, a1, zb, L_SUL)
        z.shugam(a0, za, -a1, zb, L_SUL)


def _bie_suljee(z: Zurag, t: Tulguur, deed: float) -> None:
    """Сүлжээн бие: хугарлын шугамтай хоёр тавцан, тогтмол модультай раскос."""
    gib = min(_gib(t), deed)
    # Хөл нь хугарлаар дамжина — ганц шулуун биш, хугарсан шугам.
    for tal in (-1.0, 1.0):
        z.zam(
            [
                (tal * _orgon(t, 0.0), 0.0),
                (tal * _orgon(t, gib), gib),
                (tal * _orgon(t, deed), deed),
            ],
            L_BIE,
        )
    # Хугарлаас доош бүдүүн модуль, дээш нарийн — 06КМ-ийн 2200/1800.
    _suljee_zurah(z, t, _tuvshin(0.0, gib, PANEL_BIE))
    if deed > gib + 1e-6:
        _suljee_zurah(z, t, _tuvshin(gib, deed, PANEL_ISH))
        # Хугарлын диафрагм
        z.shugam(-_orgon(t, gib), gib, _orgon(t, gib), gib, L_SUL)


def _bie_shon(z: Zurag, t: Tulguur, deed: float) -> None:
    """Тогтмол огтлолтой бие: төмөр бетон шон, эсвэл ган сүлжээн мачт.

    Хоёулаа зэрэгцээ хажуутай ч ДОТООД нь өөр: шон бол цул, зөвхөн угсралтын
    үений зураастай; оттяжкатай ган мачт бол сүлжээн ферм тул раскостой.
    Өмнө нь хоёуланг нь цулаар зурдаг байсан — П110-7 мэт ган мачт бетон
    шон шиг харагддаг байв.
    """
    if t.material == JB:
        a = SHON_ORGON / 2.0
        z.zam([(-a, 0.0), (-a, deed), (a, deed), (a, 0.0)], L_BIE)
        n = max(1, int(deed // 6.0))
        for i in range(1, n + 1):
            zz = deed * i / (n + 1)
            z.shugam(-a, zz, a, zz, L_SUL)
        return
    a = max(t.orgil / 2.0, BAGA_ORGON / 2.0)
    z.zam([(-a, 0.0), (-a, deed), (a, deed), (a, 0.0)], L_BIE)
    tuvshin = _tuvshin(0.0, deed, PANEL_ISH)
    for i in range(len(tuvshin) - 1):
        za, zb = tuvshin[i], tuvshin[i + 1]
        z.shugam(-a, zb, a, zb, L_SUL)
        z.shugam(-a, za, a, zb, L_SUL)
        z.shugam(a, za, -a, zb, L_SUL)


def _tor_zurah(z: Zurag, t: Tulguur, x_tov: float = 0.0, bie_hagas: float | None = None) -> None:
    """Траверсуудыг зурна: хэвтээ гишүүн + налуу тулгуур + утасны цэг.

    `bie_hagas` нь траверс эхлэх байрлал (биеийн хагас өргөн); өгөөгүй бол
    тухайн өндөр дэх биеийн өргөнөөс тооцно.
    """
    for tor in t.tor:
        a = _orgon(t, tor.z) if bie_hagas is None else bie_hagas
        for tal, urt in ((-1.0, tor.zuun), (1.0, tor.baruun)):
            if urt <= 0.0:
                continue
            uzuur = x_tov + tal * urt
            ex = x_tov + tal * a
            # Траверс нь нимгэн шугам биш ТРАПЕЦ: доод татуурга хэвтээ, дээд
            # татуурга үндэснээсээ үзүүр рүү налж бууна (ЭСП эскиз, 06КМ).
            h_ug = min(TOR_UNDUR, urt * 0.40)
            h_uz = min(TOR_UZUUR, h_ug * 0.45)
            z.shugam(ex, tor.z, uzuur, tor.z, L_TOR)
            z.shugam(ex, tor.z + h_ug, uzuur, tor.z + h_uz, L_TOR)
            z.shugam(ex, tor.z, ex, tor.z + h_ug, L_TOR)
            z.shugam(uzuur, tor.z, uzuur, tor.z + h_uz, L_TOR)
            # Доторх зигзаг раскос
            n = max(2, round((urt - a) / 1.1))
            for i in range(n):
                xa = _lerp(ex, uzuur, i / n)
                xb = _lerp(ex, uzuur, (i + 1) / n)
                za = _lerp(tor.z + h_ug, tor.z + h_uz, i / n)
                zb = _lerp(tor.z + h_ug, tor.z + h_uz, (i + 1) / n)
                z.shugam(xa if i % 2 else xb, tor.z, xb if i % 2 else xa, zb if i % 2 else za,
                         L_TOR)
            # Утас өлгөх цэг — доод татуургаас доош
            z.shugam(uzuur, tor.z, uzuur, tor.z - TOR_ULGUUR, L_TOR)


def _uzuur_zurah(z: Zurag, t: Tulguur, z_deed: float) -> None:
    """Тросостойк(ууд) — сүлжээн хэсэг + түүн дээрх нимгэн үзүүр.

    ХЭЛБЭР НЬ ЦЭВЭР КОНУС БИШ. Каталогийн эскиз (лист 18, 23) хоёуланд нь
    тросостойк нь ишнээсээ мөр үүсгэн эхэлж, өндрийнхөө ихэнхийг бага зэрэг
    нарийсан явж байгаад дээд хэсэгтээ л нимгэн үзүүр болдог. Өмнө нь
    суурианаас шууд орой хүртэл шулуун татдаг байсан тул хэт шовх конус
    гарч, оройн сүүлчийн панелийн хөндлөвч жижиг хайрцаг үүсгэдэг байв.
    """
    if t.uzuur <= 0 or t.undur <= z_deed + 0.05:
        return
    a = _orgon(t, z_deed)
    # Суурь нь ишнээсээ БАГА — ингэснээр мөр харагдана.
    ug = a * UZUUR_MUR if t.uzuur == 1 else max(a * 0.40, 0.15)
    undur = t.undur - z_deed
    z_hus = z_deed + undur * UZUUR_HESEG  # сүлжээн хэсгийн орой
    hus = max(ug * UZUUR_NARIIN, 0.04)  # тэнд үлдэх ХАГАС өргөн

    def hagas(zz: float) -> float:
        """`zz` өндөр дэх хагас өргөн — сүлжээн хэсэг дотор шугаман."""
        return _lerp(ug, hus, (zz - z_deed) / max(z_hus - z_deed, 1e-6))

    for tov in (0.0,) if t.uzuur == 1 else (-a * 0.75, a * 0.75):
        z.shugam(tov - ug, z_deed, tov + ug, z_deed, L_TROS)  # мөр
        z.zam([(tov - ug, z_deed), (tov - hus, z_hus), (tov, t.undur)], L_TROS)
        z.zam([(tov + ug, z_deed), (tov + hus, z_hus), (tov, t.undur)], L_TROS)
        # Раскос зөвхөн сүлжээн хэсэгт. Хамгийн дээд хөндлөвчийг ТАВИХГҮЙ:
        # үзүүрийн ёроолд хайрцаг үүсгэдэг.
        tuvshin = _tuvshin(z_deed, z_hus, PANEL_ISH)
        for i in range(len(tuvshin) - 1):
            za, zb = tuvshin[i], tuvshin[i + 1]
            wa, wb = hagas(za), hagas(zb)
            if i < len(tuvshin) - 2:
                z.shugam(tov - wb, zb, tov + wb, zb, L_TROS)
            z.shugam(tov - wa, za, tov + wb, zb, L_TROS)
            z.shugam(tov + wa, za, tov - wb, zb, L_TROS)


def _tatlaga_zurah(z: Zurag, t: Tulguur, z_baril: float) -> None:
    """Оттяжка: барих цэгээс газрын анкер хүртэл."""
    if t.tatlaga <= 0.0:
        return
    for tal in (-1.0, 1.0):
        z.shugam(0.0, z_baril, tal * t.tatlaga, 0.0, L_TAT)
        z.shugam(tal * t.tatlaga, 0.0, tal * t.tatlaga, -0.6, L_TAT)


def _hos_bie(z: Zurag, t: Tulguur, deed: float, *, shon_hev: bool) -> None:
    """Хоёр хөлтэй портал: хос босоо гишүүн, дээд хөндлөвч, X холбоос."""
    hol = max(t.hol, t.suuri) / 2.0
    a = SHON_ORGON / 2.0 if shon_hev else max(t.orgil / 2.0, 0.25)
    for tal in (-1.0, 1.0):
        x = tal * hol
        z.zam([(x - a, 0.0), (x - a, deed), (x + a, deed), (x + a, 0.0)], L_BIE)
    z.shugam(-hol, deed, hol, deed, L_BIE)
    # дотоод холбоос
    n = max(2, int(deed // 5.0))
    z_ehleh = deed * 0.25
    for i in range(n):
        z0 = _lerp(z_ehleh, deed, i / n)
        z1 = _lerp(z_ehleh, deed, (i + 1) / n)
        z.shugam(-hol + a, z0, hol - a, z1, L_SUL)
        z.shugam(hol - a, z0, -hol + a, z1, L_SUL)


def _portal_tatlaga(z: Zurag, t: Tulguur, deed: float) -> None:
    """ВЛ 500 кВ-ын ПБ: налуу хос хөл, дээд хөндлөвч, дөрвөн оттяжка."""
    hol = max(t.hol, 1.0) / 2.0
    hurdun = hol * 0.62  # хөлүүд дээшлэхдээ нийлнэ
    for tal in (-1.0, 1.0):
        z.shugam(tal * hol, 0.0, tal * hurdun, deed, L_BIE)
        z.shugam(tal * (hol - 1.2), 0.0, tal * (hurdun - 0.35), deed, L_BIE)
        n = max(4, int(deed // 3.0))
        for i in range(n):
            z0, z1 = deed * i / n, deed * (i + 1) / n
            xa = tal * _lerp(hol, hurdun, i / n)
            xb = tal * _lerp(hol - 1.2, hurdun - 0.35, (i + 1) / n)
            z.shugam(xa, z0, xb, z1, L_SUL)
    z.shugam(-hurdun, deed, hurdun, deed, L_BIE)
    if t.tatlaga > 0.0:
        for tal in (-1.0, 1.0):
            z.shugam(tal * hurdun, deed, tal * t.tatlaga, 0.0, L_TAT)
            z.shugam(tal * t.tatlaga, 0.0, tal * t.tatlaga, -0.6, L_TAT)


def _gurav_shon(z: Zurag, t: Tulguur, deed: float) -> None:
    """Гурван бие даасан стойк: -hol, 0, +hol дээр, тус бүр өөрийн траверстай."""
    hol = max(t.hol, 4.0)
    # Стойк бүрийн суурийн ХАГАС өргөн: `suuri` нь гурвуулангийн нийт зайг
    # заадаг тул түүнийг шууд авбал стойкууд бие бие рүүгээ орно.
    a = max(min(t.suuri / 2.0, hol * 0.16), 0.4)
    for x in (-hol, 0.0, hol):
        z.zam([(x - a, 0.0), (x - a * 0.45, deed), (x + a * 0.45, deed), (x + a, 0.0)], L_BIE)
        n = max(2, int(deed // 3.0))
        for i in range(n):
            z0, z1 = deed * i / n, deed * (i + 1) / n
            w0 = _lerp(a, a * 0.45, i / n)
            w1 = _lerp(a, a * 0.45, (i + 1) / n)
            z.shugam(x - w0, z0, x + w1, z1, L_SUL)
            z.shugam(x + w0, z0, x - w1, z1, L_SUL)
        if t.tatlaga > 0.0:
            for tal in (-1.0, 1.0):
                z.shugam(x, deed, x + tal * t.tatlaga, 0.0, L_TAT)
        _tor_zurah(z, t, x_tov=x, bie_hagas=a * 0.45)


# --------------------------------------------------------------------------
# Нэг тулгуурын эскиз
# --------------------------------------------------------------------------


def _hagas_urgun(t: Tulguur) -> float:
    """Зурагдах хэсгийн ХАГАС өргөн (м) — газрын шугам, хэмжээс, хүрээнд хэрэгтэй."""
    hagas = max(t.torzai, t.suuri / 2.0, t.tatlaga, t.hol / 2.0)
    if t.hev == GURAV_SHON:
        hagas = max(t.hol + t.torzai, t.hol + t.tatlaga)
    return max(hagas, 2.0)


def _tulguur_zurah(
    z: Zurag, t: Tulguur, *, hemjees: bool = True, h_bichig: float | None = None
) -> tuple[float, float]:
    """Тулгуурыг (0,0) газрын түвшинд зурна. Буцаах нь (өргөн, өндөр)."""
    z_deed = max((tor.z for tor in t.tor), default=t.undur)
    z_deed = max(z_deed, min(t.dood, t.undur)) if t.tor else t.undur
    bie_deed = max(z_deed, t.undur if t.uzuur == 0 else z_deed)

    if t.hev == TATLAGA:
        _bie_shon(z, t, bie_deed)
        _tatlaga_zurah(z, t, t.dood)
        _tor_zurah(z, t)
        _uzuur_zurah(z, t, bie_deed)
    elif t.hev == PORTAL_T:
        _portal_tatlaga(z, t, bie_deed)
        _tor_zurah(z, t)
        _uzuur_zurah(z, t, bie_deed)
    elif t.hev in (PORTAL, HOS_SHON):
        _hos_bie(z, t, bie_deed, shon_hev=t.material == JB)
        _tor_zurah(z, t)
        _uzuur_zurah(z, t, bie_deed)
    elif t.hev == GURAV_SHON:
        _gurav_shon(z, t, bie_deed)  # траверсуудыг стойк бүр дээр өөрөө зурна
    elif t.hev == SHON:
        _bie_shon(z, t, bie_deed)
        _tor_zurah(z, t)
        _uzuur_zurah(z, t, bie_deed)
        _tatlaga_zurah(z, t, t.dood)
    else:
        _bie_suljee(z, t, bie_deed)
        _tor_zurah(z, t)
        _uzuur_zurah(z, t, bie_deed)

    urgun = max(2.0 * _hagas_urgun(t), 4.0)
    # Ганц тулгуурын зурагт текст нь тулгуурын өндрөөс хамаарна; хуудсанд
    # оруулахад цаасны мм-ээр тогтсон өндөр өгөгддөг (бүх багана ижил болно).
    h = h_bichig if h_bichig is not None else max(t.undur / 55.0, 0.22)

    # газрын шугам + фундаментын тэмдэглэгээ
    gazar = urgun / 2.0 + 1.0
    z.shugam(-gazar, 0.0, gazar, 0.0, L_GAZAR)
    n = max(6, int(gazar))
    for i in range(2 * n):
        x = -gazar + (2.0 * gazar) * i / (2 * n - 1)
        z.shugam(x, 0.0, x - 0.35, -0.35, L_GAZAR)

    if hemjees:
        _hemjees_zurah(z, t, urgun, h)
    return urgun, t.undur


def _hemjees_zurah(z: Zurag, t: Tulguur, urgun: float, h: float) -> None:
    """Нийт өндөр, доод траверсын өндөр, суурийн өргөн, траверсын гар."""
    x_hem = urgun / 2.0 + max(1.5, urgun * 0.08)
    z.hem_bosoo(x_hem, 0.0, t.undur, _too(t.undur), h)
    if 0.0 < t.dood < t.undur:
        z.hem_bosoo(x_hem + h * 3.0, 0.0, t.dood, _too(t.dood), h)
    if t.suuri > 0.05:
        z.hem_hevtee(-1.4, -t.suuri / 2.0, t.suuri / 2.0, _too(t.suuri), h)
    if t.tatlaga > 0.0:
        z.hem_hevtee(-2.4, -t.tatlaga, t.tatlaga, _too(2 * t.tatlaga), h)
    for tor in t.tor:
        for tal, urt in ((-1.0, tor.zuun), (1.0, tor.baruun)):
            if urt > 0.4:
                z.bichig(tal * urt * 0.55, tor.z + h * 0.5, _too(urt), h, layer=L_HEM, tov=True)


def hemjees_delgerengui(z: Zurag, t: Tulguur, urgun: float, h: float) -> None:
    """БҮХ хэмжээсийг гаргана — дэлгэрэнгүй хуудсанд зориулав.

    `_hemjees_zurah` нь бүдүүвчид хангалттай дөрвөн хэмжээс тавьдаг. Энд
    траверс бүрийн түвшин, гар тус бүрийн урт, хугарлын шугам, ишний өргөн,
    тросостойкийн өндөр — гаргаж болох бүхнийг тавина.

    Босоо хэмжээс нь ХОЁР баганад ордог: дотор талд шат дараалсан гинж
    (газар → хугарал → траверс бүр → орой), гадна талд нийт өндөр. Ингэснээр
    гинжний нийлбэр нийт өндөртэй тэнцэж байгааг зурагнаас шалгаж болно.
    """
    hagas = urgun / 2.0
    x_gin = hagas + max(1.2, urgun * 0.06)  # гинжин хэмжээс
    x_niit = x_gin + h * 4.5  # нийт өндөр

    z.hem_bosoo(x_niit, 0.0, t.undur, _too(t.undur), h)

    tuvshin = [0.0]
    gib = _gib(t)
    if 0.05 < gib < t.undur - 0.05:
        tuvshin.append(gib)
    tuvshin += [tor.z for tor in t.tor if 0.05 < tor.z < t.undur - 0.05]
    tuvshin.append(t.undur)
    tuvshin = sorted({round(v, 3) for v in tuvshin})
    for za, zb in itertools.pairwise(tuvshin):
        if zb - za > 0.05:
            z.hem_bosoo(x_gin, za, zb, _too(zb - za), h)

    # Хэвтээ: суурь, ишний өргөн, траверсын гар бүр
    if t.suuri > 0.05:
        z.hem_hevtee(-1.6, -t.suuri / 2.0, t.suuri / 2.0, _too(t.suuri), h)
    if t.tatlaga > 0.0:
        z.hem_hevtee(-2.8, -t.tatlaga, t.tatlaga, _too(2 * t.tatlaga), h)
    ish = _orgon(t, gib)
    if ish > 0.05:
        z.hem_hevtee(gib - h * 2.2, -ish, ish, _too(2 * ish), h)
    for tor in t.tor:
        for tal, urt in ((-1.0, tor.zuun), (1.0, tor.baruun)):
            if urt <= 0.4:
                continue
            # Гарын урт нь ТЭНХЛЭГЭЭС хэмжигдэнэ (каталог ч мөн адил), тиймээс
            # хэмжээсийн шугам голоос үзүүр хүртэл.
            x0, x1 = sorted((0.0, tal * urt))
            z.hem_hevtee(tor.z + h * 2.4, x0, x1, _too(urt), h)


def _pasport(z: Zurag, t: Tulguur, urgun: float, h: float) -> float:
    """Зургийн доор паспортын бичээс. Буцаах нь эзэлсэн өндөр (сөрөг тал руу)."""
    mor: list[str] = [t.shifr]
    tsep = "нэг цепийн" if t.tsep == 1 else "хоёр цепийн"
    mor.append(f"ВЛ {t.hutsel} кВ, {tsep}, {t.angilal}, {t.material}")
    jin = []
    if t.jin is not None:
        jin.append(f"масс {t.jin:,.0f} кг".replace(",", " "))
    if t.jin_ts is not None:
        jin.append(f"цинктэй {t.jin_ts:,.0f} кг".replace(",", " "))
    if t.angilal == POSTAVKA:
        jin.append("(подставка)")
    if jin:
        mor.append(", ".join(jin))
    mor.append(f"өндөр {_too(t.undur)} м, доод траверс {_too(t.dood)} м")
    if t.utas:
        mor.append(f"утас {t.utas}" + (f", трос {t.tros}" if t.tros else ""))
    if t.mus:
        mor.append(f"гололёдын район {t.mus}")
    if t.shem:
        mor.append(f"монтажийн схем {t.shem}")
    mor.append(f"каталог 5713тм-т2, лист {t.huudas}")
    if t.temdeglel:
        mor.extend(_taslah(t.temdeglel, max(38, int(urgun / h * 0.9))))
    if not t.batalgaa:
        mor.append("≈ хэмжээс ойролцоо (эскизээс уншаагүй)")

    zz = -3.2 - h * 2.5  # хамгийн доод хэмжээсийн (оттяжкын) шугамаас доогуур
    z.bichig(-urgun / 2.0, zz, mor[0], h * 1.8)
    zz -= h * 2.4
    for s in mor[1:]:
        z.bichig(-urgun / 2.0, zz, s, h)
        zz -= h * 1.55
    return -zz


def _taslah(text: str, urt: int) -> list[str]:
    """Урт бичвэрийг `urt` тэмдэгтээр таслаж мөр болгоно."""
    mor: list[str] = []
    idev = ""
    for ug in text.split():
        if idev and len(idev) + 1 + len(ug) > urt:
            mor.append(idev)
            idev = ug
        else:
            idev = f"{idev} {ug}".strip()
    if idev:
        mor.append(idev)
    return mor


def barih(t: Tulguur, *, hemjees: bool = True, huree: bool = True) -> Drawing:
    """Нэг тулгуурын бүрэн зураг (хэмжээс, паспорт, хүрээтэй)."""
    dwg = Drawing(options=DrawingOptions(dwg_format="2018"))
    z = Zurag(dwg)
    urgun, undur = _tulguur_zurah(z, t, hemjees=hemjees)
    h = max(t.undur / 55.0, 0.22)
    doosh = _pasport(z, t, urgun, h)
    if huree:
        zai = max(1.5, urgun * 0.12)
        x0 = -urgun / 2.0 - zai - h * 6.0
        x1 = urgun / 2.0 + zai + h * 6.0
        z.zam([(x0, -doosh - zai), (x1, -doosh - zai), (x1, undur + zai), (x0, undur + zai)],
              L_HUREE, hulhii=True)
    return dwg


def toim(tulguur: Sequence[Tulguur], out: Path, *, bagana: int = 6, hemjees: bool = True) -> bool:
    """Олон тулгуурыг НЭГ хуудсанд тор болгон байрлуулж бичнэ (жинхэнэ масштаб)."""
    if not tulguur:
        print("  тулгуур алга")
        return False
    dwg = Drawing(options=DrawingOptions(dwg_format="2018"))
    z = Zurag(dwg)
    urgun_max = max(max(2.0 * _hagas_urgun(t), 4.0) for t in tulguur) * 1.45
    undur_max = max(t.undur for t in tulguur) * 1.55

    for i, t in enumerate(tulguur):
        mor, bag = divmod(i, bagana)
        z.shiljuuleh(bag * urgun_max, -mor * undur_max)
        u, _ = _tulguur_zurah(z, t, hemjees=hemjees)
        _pasport(z, t, u, max(t.undur / 55.0, 0.22))
    z.shiljuuleh(0.0, 0.0)
    return _bicheh(dwg, out, f"тойм ({len(tulguur)} тулгуур)")


def bicheh(t: Tulguur, out: Path, *, hemjees: bool = True) -> bool:
    """Нэг тулгуурыг DWG болгож бичнэ."""
    return _bicheh(barih(t, hemjees=hemjees), out, t.shifr)


def _bicheh(dwg: Drawing, out: Path, ner: str) -> bool:
    """Drawing-ыг AutoCAD-аар гүйцэтгэж DWG болгоно."""
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        backend = AccoreConsoleBackend(template=uram())
        res = write_dwg(dwg, out, backend=backend, timeout=900.0, check=False)
    except DwgForgeError as exc:
        print(f"  FAIL {ner:22s} {exc}")
        return False
    hemjee = out.stat().st_size if out.is_file() else 0
    tem = "OK  " if res.ok else "FAIL"
    print(f"  {tem} {ner:22s} {hemjee:>9,}  {res.entities_ok}/{len(dwg)}  {res.duration_s:.1f}s")
    if not res.ok:
        for tag, message in res.failures[:3]:
            print(f"       ! {tag}: {message[:90]}")
    return res.ok


def main() -> int:
    """`python tulguur2d/zurag.py <шифр>` — нэг тулгуурын зураг."""
    from tulguurdata import katalog

    k = katalog()
    shifr = sys.argv[1] if len(sys.argv) > 1 else "П110-1"
    try:
        t = k.ol(shifr)
    except KeyError as exc:
        print(exc)
        return 1
    return 0 if bicheh(t, OUTDIR / f"{t.ner}.dwg") else 1


if __name__ == "__main__":
    raise SystemExit(main())
