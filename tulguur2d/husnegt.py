r"""АЗ хуудас угсрах — танай "ТОНОГЛОЛЫН ТЕХНИКИЙН ҮЗҮҮЛЭЛТ" зургийн бүтцээр.

Багана бүр нэг тулгуур, дөрвөн мөртэй:

    ПЛАН      маршрутын шугам + тэмдэг (анкер ▽ / дундын ○) + ПК00+00
    ШИФР      тулгуурын шифр
    ӨНДӨРЛӨГ  урдаас харсан эскиз, хэмжээстэй
    СУУРЬ     фундаментын план (тэнхлэг, хөлийн байрлал, суурийн өргөн)

Баганууд нь АНКЕР / ДУНДЫН гэж бүлэглэгдэж, дээр нь бүлгийн гарчиг гарна.

МАСШТАБ. Зураг нь МОДЕЛЬ орчинд МЕТРЭЭР 1:1 зурагдана — хэмжээсийн тоо
каталогийн утгатай яг таарна. Харин хүрээ, бичээс нь цаасны мм-ээр өгөгдөж,
масштабаар үржиж модель рүү ордог (`mm()`). Тиймээс хуудсыг 1:M-ээр хэвлэхэд
бичээс нь яг 2.5 мм гарна. M-ийг хамгийн өндөр тулгуураас автоматаар сонгоно.

Ажиллуулах:
    python tulguur2d/husnegt.py --hutsel 110 --angilal анкер-өнцгийн
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge import Drawing, DrawingOptions
from oruulga import Attrib, Insert, SeqEnd
from tulguursan import (
    ANKER,
    GURAV_SHON,
    HOS_SHON,
    PORTAL,
    PORTAL_T,
    SALAA,
    SHON,
    TATLAGA,
    TOGSGOL,
    Tulguur,
)
from zurag import (
    BICHGIIN_HEV,
    L_BICHIG,
    L_GAZAR,
    L_HUREE,
    L_TENH,
    OUTDIR,
    ZAGVAR,
    Zurag,
    _bicheh,
    _hagas_urgun,
    _too,
    _tulguur_zurah,
    lay,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# -- цаасны хэмжээ, мм -------------------------------------------------------

TSAAS: dict[str, tuple[float, float]] = {
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}

ZAH_ZUUN = 20.0  # мм, зүүн зах (үдэлт)
ZAH = 5.0  # мм, бусад зах

# Хуудасны мөрүүдийн өндөр, мм. Нийлбэр нь хүрээний өндрөөс бага байна.
MOR_GARCHIG = 8.0
MOR_PLAN = 52.0
MOR_NER = 8.0
MOR_SUURI = 34.0
# Өндөрлөгийн мөр нь үлдсэн зайг бүхэлд нь эзэлнэ.

# Булангийн хүснэгтийн нүдэнд үлдээх зай, мм. Ихэнх штампын эх цэг нь
# баруун доод буланд байдаг тул хүрээний булан руу шууд тавина;
# бодит хэмжээг `zagvar.json`-оос уншина.
SHTAMP_URGUN = 170.44  # мм
SHTAMP_UNDUR = 36.0  # мм

# Стандарт масштабууд — автоматаар эдгээрээс сонгоно.
MASSHTAB = (50, 100, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1250, 1500, 2000)

# Бичээсийн өндөр, цаасны мм.
H_GARCHIG = 3.5
H_NER = 3.5
H_HEM = 2.0
H_PK = 2.0
H_TAILBAR = 2.5


def masshtab_songoh(bag: Sequence[Tulguur], urgun_mm: float, undur_mm: float) -> int:
    """Бүх тулгуур нүдэнд багтах хамгийн НАРИЙН стандарт масштабыг сонгоно."""
    if not bag:
        return 200
    undur_m = max(t.undur for t in bag)
    urgun_m = max(2.0 * _hagas_urgun(t) for t in bag)
    heregtei = max(undur_m * 1000.0 / undur_mm, urgun_m * 1000.0 / urgun_mm)
    for m in MASSHTAB:
        if m >= heregtei:
            return m
    return MASSHTAB[-1]


class Husnegt:
    """Нэг хуудсыг угсарна. Бүх координат МОДЕЛЬ метрээр."""

    def __init__(
        self,
        bag: Sequence[Tulguur],
        *,
        tsaas: str = "A3",
        masshtab: int | None = None,
        garchig: str = "ТОНОГЛОЛЫН ТЕХНИКИЙН ҮЗҮҮЛЭЛТ",
        shtamp: str = "",
    ) -> None:
        """Хуудасны хэмжээ, масштаб, баганын өргөнийг тооцно."""
        self.bag = list(bag)
        self.garchig = garchig
        self.shtamp = shtamp
        self.tsaas_urgun, self.tsaas_undur = TSAAS.get(tsaas, TSAAS["A3"])

        # Хүрээний дотор талын хэмжээ, мм
        self.x0 = ZAH_ZUUN
        self.x1 = self.tsaas_urgun - ZAH
        self.y0 = ZAH
        self.y1 = self.tsaas_undur - ZAH

        # Хүснэгтийн талбай — штампын дээр
        self.t_y0 = self.y0 + SHTAMP_UNDUR
        self.t_y1 = self.y1
        self.bagana_too = max(1, len(self.bag))
        self.bagana_urgun = (self.x1 - self.x0) / self.bagana_too

        mor_urd = (self.t_y1 - self.t_y0) - MOR_GARCHIG - MOR_PLAN - MOR_NER - MOR_SUURI
        self.mor_urd = max(mor_urd, 40.0)
        self.masshtab = masshtab or masshtab_songoh(
            self.bag, self.bagana_urgun * 0.92, self.mor_urd * 0.88
        )

        self.dwg = Drawing(options=DrawingOptions(dwg_format="2018"))
        self.z = Zurag(self.dwg)

    # -- нэгж хөрвүүлэлт ---------------------------------------------------

    def mm(self, v: float) -> float:
        """Цаасны миллиметрийг модель метр болгоно (масштабаар)."""
        return v / 1000.0 * self.masshtab

    # -- мөрийн хил, мм ----------------------------------------------------

    @property
    def y_garchig(self) -> tuple[float, float]:
        """Бүлгийн гарчгийн мөр."""
        return self.t_y1 - MOR_GARCHIG, self.t_y1

    @property
    def y_plan(self) -> tuple[float, float]:
        """Планы тэмдгийн мөр."""
        deed = self.y_garchig[0]
        return deed - MOR_PLAN, deed

    @property
    def y_ner(self) -> tuple[float, float]:
        """Шифрийн мөр."""
        deed = self.y_plan[0]
        return deed - MOR_NER, deed

    @property
    def y_urd(self) -> tuple[float, float]:
        """Өндөрлөгийн мөр."""
        deed = self.y_ner[0]
        return deed - self.mor_urd, deed

    @property
    def y_suuri(self) -> tuple[float, float]:
        """Фундаментын планы мөр."""
        deed = self.y_urd[0]
        return self.t_y0, deed

    def x_bagana(self, i: int) -> tuple[float, float]:
        """`i` дугаар баганын зүүн, баруун хил (мм)."""
        return self.x0 + i * self.bagana_urgun, self.x0 + (i + 1) * self.bagana_urgun

    # -- зурах туслахууд ---------------------------------------------------

    def shugam(self, x0: float, y0: float, x1: float, y1: float, layer: str) -> None:
        """Цаасны мм координатаар шулуун татна."""
        self.z.shugam(self.mm(x0), self.mm(y0), self.mm(x1), self.mm(y1), layer)

    def tegsheg(self, x0: float, y0: float, x1: float, y1: float, layer: str) -> None:
        """Тэгш өнцөгт."""
        self.z.zam(
            [
                (self.mm(x0), self.mm(y0)),
                (self.mm(x1), self.mm(y0)),
                (self.mm(x1), self.mm(y1)),
                (self.mm(x0), self.mm(y1)),
            ],
            layer,
            hulhii=True,
        )

    def bichig(
        self, x: float, y: float, text: str, h_mm: float, *, tov: bool = True,
        layer: str = L_BICHIG, ergelt: float = 0.0,
    ) -> None:
        """Цаасны мм-ээр текст (өндөр нь мм-ээр өгөгдөнө)."""
        px, py = self.mm(x), self.mm(y)
        self.dwg.text(
            (px, py),
            text,
            height=self.mm(h_mm),
            rotation=ergelt,
            style=BICHGIIN_HEV,
            halign=1 if tov else 0,
            align_point=(px, py) if tov else None,
            layer=lay(layer),
        )

    # -- бүрэлдэхүүн хэсгүүд ------------------------------------------------

    def huree(self) -> None:
        """Цаасны хүрээ, дотор рамк, булангийн хүснэгт."""
        self.tegsheg(0.0, 0.0, self.tsaas_urgun, self.tsaas_undur, L_HUREE)
        self.tegsheg(self.x0, self.y0, self.x1, self.y1, L_HUREE)
        if self.shtamp:
            # Блокийн эх цэг нь баруун доод булан — хүрээний булантай нийлүүлнэ.
            self.dwg.add(
                Insert(
                    self.shtamp,
                    (self.mm(self.x1), self.mm(self.y0)),
                    scale=self.masshtab / 1000.0,
                    layer=lay(L_HUREE),
                )
            )

    def tor(self) -> None:
        """Хүснэгтийн шугамууд: мөр хоорондын зураас, баганын тусгаарлагч."""
        for y in (self.t_y0, self.y_urd[1], self.y_ner[1], self.y_plan[1], self.t_y1):
            self.shugam(self.x0, y, self.x1, y, L_HUREE)
        for i in range(self.bagana_too + 1):
            x = self.x0 + i * self.bagana_urgun
            self.shugam(x, self.t_y0, x, self.t_y1, L_HUREE)

    def buleg_garchig(self) -> None:
        """АНКЕР / ДУНДЫН гэсэн бүлгийн гарчиг — зэргэлдээ баганууд нэгдэнэ."""
        yl, yu = self.y_garchig
        ehleh = 0
        for i in range(self.bagana_too + 1):
            odoo = _buleg(self.bag[i]) if i < self.bagana_too else None
            umnuh = _buleg(self.bag[ehleh])
            if odoo == umnuh:
                continue
            xa = self.x_bagana(ehleh)[0]
            xb = self.x_bagana(i - 1)[1]
            self.bichig((xa + xb) / 2.0, (yl + yu) / 2.0 - H_GARCHIG * 0.35, umnuh, H_GARCHIG)
            if i < self.bagana_too:
                self.shugam(xb, yl, xb, yu, L_HUREE)
            ehleh = i

    def plan_temdeg(self, i: int, t: Tulguur) -> None:
        """Маршрутын шугам + тулгуурын тэмдэг + ПК бичиг."""
        xa, xb = self.x_bagana(i)
        yl, yu = self.y_plan
        x = (xa + xb) / 2.0
        # шифр — тэмдгийн дээр, доогуур зураастай
        self.bichig(x, yu - 6.0, t.shifr, H_NER)
        self.shugam(x - 12.0, yu - 7.5, x + 12.0, yu - 7.5, L_BICHIG)
        # маршрутын шугам
        self.shugam(x, yl + 4.0, x, yu - 12.0, L_TENH)
        for k in range(1, 5):
            yy = yl + 4.0 + (yu - 12.0 - yl - 4.0) * k / 5.0
            self.shugam(x - 0.7, yy, x + 0.7, yy, L_TENH)
        # тулгуурын тэмдэг
        ys = yu - 14.5
        if t.angilal in (ANKER, TOGSGOL, SALAA):
            r = 2.2
            self.z.zam(
                [
                    (self.mm(x - r), self.mm(ys + r)),
                    (self.mm(x + r), self.mm(ys + r)),
                    (self.mm(x), self.mm(ys - r)),
                ],
                L_BICHIG,
                hulhii=True,
            )
        else:
            self.dwg.circle((self.mm(x), self.mm(ys)), self.mm(2.0), layer=lay(L_BICHIG))
        # ПК бичиг — босоо
        self.bichig(x - 2.5, yl + 6.0, "ПК00+00", H_PK, tov=False, ergelt=math.pi / 2.0)

    def ner_nuh(self, i: int, t: Tulguur) -> None:
        """Шифрийн мөр."""
        xa, xb = self.x_bagana(i)
        yl, yu = self.y_ner
        self.bichig((xa + xb) / 2.0, (yl + yu) / 2.0 - H_NER * 0.35, t.shifr, H_NER)

    def urd_haragdats(self, i: int, t: Tulguur) -> None:
        """Урдаас харсан эскиз — модель метрээр 1:1, нүдний доод шугам дээр."""
        xa, xb = self.x_bagana(i)
        yl, _ = self.y_urd
        self.z.shiljuuleh(self.mm((xa + xb) / 2.0), self.mm(yl + 4.0))
        _tulguur_zurah(self.z, t, hemjees=True, h_bichig=self.mm(H_HEM))
        self.z.shiljuuleh(0.0, 0.0)

    def suuri_plan(self, i: int, t: Tulguur) -> None:
        """Фундаментын план: хөлийн байрлал, тэнхлэг, суурийн хэмжээс."""
        xa, xb = self.x_bagana(i)
        yl, yu = self.y_suuri
        cx = (xa + xb) / 2.0
        cy = (yl + yu) / 2.0 + 2.0
        self.z.shiljuuleh(self.mm(cx), self.mm(cy))

        hol = _hol_bairlal(t)
        fund = max(t.suuri * 0.16, 0.5)  # фундаментын нүдний хэмжээ, м
        for px, py in hol:
            self.z.zam(
                [
                    (px - fund / 2, py - fund / 2),
                    (px + fund / 2, py - fund / 2),
                    (px + fund / 2, py + fund / 2),
                    (px - fund / 2, py + fund / 2),
                ],
                L_GAZAR,
                hulhii=True,
            )
        # тэнхлэгүүд
        rx = max((abs(p[0]) for p in hol), default=1.0) + fund
        ry = max((abs(p[1]) for p in hol), default=1.0) + fund
        self.z.shugam(-rx, 0.0, rx, 0.0, L_TENH)
        self.z.shugam(0.0, -ry, 0.0, ry, L_TENH)
        self.z.shiljuuleh(0.0, 0.0)
        if t.suuri > 0.05 and len(hol) > 1:
            # Нүднээс гарахгүйн тулд нүдний доод шугамын дээр тавина.
            self.bichig(cx, yl + 2.5, _too(t.suuri), H_HEM)

    def tailbar(self) -> None:
        """Зүүн доод буланд тэмдэглэгээний тайлбар."""
        x = self.x0 + 4.0
        y = self.y0 + SHTAMP_UNDUR - 7.0
        self.dwg.circle((self.mm(x), self.mm(y)), self.mm(2.0), layer=lay(L_BICHIG))
        self.bichig(x + 6.0, y - 1.0, "Дундын тулгуур / Suspension tower", H_TAILBAR, tov=False)
        y -= 8.0
        r = 2.2
        self.z.zam(
            [
                (self.mm(x - r), self.mm(y + r)),
                (self.mm(x + r), self.mm(y + r)),
                (self.mm(x), self.mm(y - r)),
            ],
            L_BICHIG,
            hulhii=True,
        )
        self.bichig(x + 6.0, y - 1.0, "Анкер тулгуур / Tention tower", H_TAILBAR, tov=False)
        y -= 8.0
        self.bichig(
            x, y, f"Масштаб 1:{self.masshtab}   ({len(self.bag)} тулгуур)",
            H_TAILBAR, tov=False,
        )
        y -= 5.5
        self.bichig(
            x, y, "ЭСП каталог 5713тм-т2 (1976). Хэмжээс метрээр.",
            H_TAILBAR, tov=False,
        )

    def barih(self) -> Drawing:
        """Бүх хэсгийг угсарч Drawing буцаана."""
        self.huree()
        self.tor()
        self.buleg_garchig()
        for i, t in enumerate(self.bag):
            self.plan_temdeg(i, t)
            self.ner_nuh(i, t)
            self.urd_haragdats(i, t)
            self.suuri_plan(i, t)
        self.tailbar()
        self.bichig(
            (self.x0 + self.x1) / 2.0, self.y1 + 1.5, self.garchig, H_GARCHIG, layer=L_BICHIG
        )
        return self.dwg


# --------------------------------------------------------------------------
# Нэг тулгуур = нэг АЗ хуудас (танай хүрээний блок дотор)
# --------------------------------------------------------------------------

# Хуудасны блок, булангийн хүснэгт, хүний нэр — БҮГД `zagvar.json`-оос ирнэ.
# Эх кодод бичихгүй: тэдгээр нь тодорхой нэг захиалагчийн зургийн блокийн нэр,
# ажилтны нэр бөгөөд энэ repo нээлттэй. Байхгүй бол хуудас өөрийн хүрээтэйгээр,
# штампгүй гарна.
_SHTAMP: dict = ZAGVAR.get("shtamp") or {}

#: Булангийн хүснэгтийн блокийн нэр (`zagvar.py holboh` атрибутаар нь таана).
SHTAMP_BLOCK: str = str(_SHTAMP.get("ner") or "")

#: Атрибутын байрлал (блокийн эх цэгээс, мм) ба өндөр: (tag, x, y, h).
SHTAMP_ATT: tuple[tuple[str, float, float, float], ...] = tuple(
    (str(a[0]), float(a[1]), float(a[2]), float(a[3]))
    for a in _SHTAMP.get("att", [])
    if len(a) >= 4
)

_HUN: dict = ZAGVAR.get("hunii_ner") or {}
INZHENER: str = str(_HUN.get("inzhener") or "")
ZURSAN: str = str(_HUN.get("zursan") or "") or INZHENER
SHALGASAN: str = str(_HUN.get("shalgasan") or "")

#: Цаасны хүрээний блок (хэмжээгээр нь танисан).
A3_BLOCK: str = str(ZAGVAR.get("huree_block") or "")


class Huudas:
    """Нэг тулгуурыг танай АЗ хуудасны блок дотор зурна.

    Зүүн талд өндөрлөгийн зураг + суурийн план, баруун талд ТАЙЛБАР,
    баруун доод буланд булангийн хүснэгт (атрибутууд нь бөглөгдсөн).
    """

    def __init__(
        self,
        t: Tulguur,
        *,
        masshtab: int | None = None,
        huree_block: str = A3_BLOCK,
        shtamp: str = SHTAMP_BLOCK,
        tosol: str = "",
        ognoo: str = "",
        shifr_zurag: str = "",
        inzhener: str = INZHENER,
        zursan: str = ZURSAN,
        shalgasan: str = SHALGASAN,
        zurag_ner: str = "Нэг маягийн зураг",
    ) -> None:
        """Хуудасны бүсүүдийг тооцоод масштабыг сонгоно."""
        self.t = t
        self.huree_block = huree_block
        self.shtamp = shtamp
        self.tosol = tosol
        self.ognoo = ognoo
        self.shifr_zurag = shifr_zurag
        self.inzhener = inzhener
        self.zursan = zursan or inzhener
        self.shalgasan = shalgasan
        self.zurag_ner = zurag_ner

        self.x0, self.y0 = ZAH_ZUUN, ZAH
        self.x1, self.y1 = TSAAS["A3"][0] - ZAH, TSAAS["A3"][1] - ZAH
        # Баруун талын тайлбарын багана
        self.tailbar_urgun = 118.0
        self.zurag_x1 = self.x1 - self.tailbar_urgun
        # Булангийн хүснэгтийн дээд ирмэг
        self.shtamp_deed = self.y0 + SHTAMP_UNDUR

        self.zurag_urgun = self.zurag_x1 - self.x0
        # Босоо чиглэлд өндөрлөг БА суурийн план хоёулаа багтах ёстой: хоёулаа
        # масштабаас хамаардаг тул нийлбэрээр нь масштабаа сонгоно, зайг мм-ээр
        # тусад нь хасна.
        self.suuri_undur_m = _suuri_undur(t)
        zai_mm = 28.0  # газрын шугам ба план хоорондын зай + доод захын зай
        bolomj = (self.y1 - self.y0 - zai_mm) * 0.97
        self.masshtab = masshtab or _masshtab_hos(
            t.undur + self.suuri_undur_m, 2.0 * _hagas_urgun(t), bolomj, self.zurag_urgun * 0.80
        )

        self.dwg = Drawing(options=DrawingOptions(dwg_format="2018"))
        self.z = Zurag(self.dwg)

    def mm(self, v: float) -> float:
        """Цаасны миллиметрийг модель метр болгоно."""
        return v / 1000.0 * self.masshtab

    def bichig(
        self, x: float, y: float, text: str, h_mm: float, *, tov: bool = False,
        layer: str = L_BICHIG,
    ) -> None:
        """Цаасны мм-ээр текст."""
        px, py = self.mm(x), self.mm(y)
        self.dwg.text(
            (px, py),
            text,
            height=self.mm(h_mm),
            style=BICHGIIN_HEV,
            halign=1 if tov else 0,
            align_point=(px, py) if tov else None,
            layer=lay(layer),
        )

    # -- хэсгүүд -----------------------------------------------------------

    def huree(self) -> None:
        """Танай АЗ хуудасны блокийг тавина (байхгүй бол өөрсдөө хүрээ зурна)."""
        if self.huree_block:
            self.dwg.add(
                Insert(self.huree_block, (0.0, 0.0), scale=self.masshtab / 1000.0,
                       layer=lay(L_HUREE))
            )
            return
        for a, b in (((0.0, 0.0), (TSAAS["A3"][0], TSAAS["A3"][1])),
                     ((self.x0, self.y0), (self.x1, self.y1))):
            self.z.zam(
                [
                    (self.mm(a[0]), self.mm(a[1])), (self.mm(b[0]), self.mm(a[1])),
                    (self.mm(b[0]), self.mm(b[1])), (self.mm(a[0]), self.mm(b[1])),
                ],
                L_HUREE,
                hulhii=True,
            )

    def bulangiin_husnegt(self) -> None:
        """Булангийн хүснэгт + атрибутуудыг бөглөнө."""
        if not self.shtamp or not SHTAMP_ATT:
            return
        s = self.masshtab / 1000.0
        bx, by = self.x1, self.y0  # блокийн эх цэг нь баруун доод булан
        utga = {
            "ТӨСЛИЙН-НЭР": self.tosol,
            "ЗУРАГ-НЭР": f"{self.zurag_ner}. {self.t.shifr}",
            "АЗ": "A3",
            "И_НЭР": self.inzhener,
            "МАСШ": f"1:{self.masshtab}",
            "ОГНОО": self.ognoo,
            "Г_НЭР": self.zursan,
            "Ш_НЭР": self.shalgasan,
            "ШИФР": self.shifr_zurag,
            "ХТ-1": "",
            "ТОО": "1",
        }
        self.dwg.add(
            Insert(self.shtamp, (self.mm(bx), self.mm(by)), scale=s,
                   layer=lay(L_HUREE), atributtai=True)
        )
        for tag, ax, ay, ah in SHTAMP_ATT:
            self.dwg.add(
                Attrib(
                    tag,
                    utga.get(tag, ""),
                    (self.mm(bx + ax), self.mm(by + ay)),
                    height=self.mm(ah),
                    style=BICHGIIN_HEV,
                    layer=lay(L_HUREE),
                )
            )
        self.dwg.add(SeqEnd(layer=lay(L_HUREE)))

    def zurag(self) -> None:
        """Өндөрлөгийн зураг — зүүн бүсийн голд, доор нь суурийн план."""
        cx = (self.x0 + self.zurag_x1) / 2.0
        # Суурийн планы хагас өндөр (цаасны мм) — доод захаас түүгээр эхэлнэ.
        hagas_mm = self.suuri_undur_m / 2.0 / self.masshtab * 1000.0
        cy = self.y0 + 12.0 + hagas_mm
        gazar = cy + hagas_mm + 10.0

        self.z.shiljuuleh(self.mm(cx), self.mm(gazar))
        _tulguur_zurah(self.z, self.t, hemjees=True, h_bichig=self.mm(H_HEM))
        self.z.shiljuuleh(0.0, 0.0)
        self.z.shiljuuleh(self.mm(cx), self.mm(cy))
        hol = _hol_bairlal(self.t)
        fund = max(self.t.suuri * 0.16, 0.5)
        for px, py in hol:
            self.z.zam(
                [
                    (px - fund / 2, py - fund / 2), (px + fund / 2, py - fund / 2),
                    (px + fund / 2, py + fund / 2), (px - fund / 2, py + fund / 2),
                ],
                L_GAZAR,
                hulhii=True,
            )
        rx = max((abs(p[0]) for p in hol), default=1.0) + fund
        ry = max((abs(p[1]) for p in hol), default=1.0) + fund
        self.z.shugam(-rx, 0.0, rx, 0.0, L_TENH)
        self.z.shugam(0.0, -ry, 0.0, ry, L_TENH)
        self.z.shiljuuleh(0.0, 0.0)
        self.bichig(cx, self.y0 + 5.0, f"Суурийн план  {_too(self.t.suuri)} м", H_HEM, tov=True)

    def tailbar(self) -> None:
        """Баруун талын ТАЙЛБАР багана."""
        x = self.zurag_x1 + 6.0
        y = self.y1 - 8.0
        self.z.shugam(
            self.mm(self.zurag_x1), self.mm(self.shtamp_deed),
            self.mm(self.zurag_x1), self.mm(self.y1),
            L_HUREE,
        )
        self.bichig(x, y, "ТАЙЛБАР", 3.5)
        y -= 8.0
        for gar, utga in _tailbar_mor(self.t):
            if not utga:
                continue
            for i, mor in enumerate(_taslah(utga, 34)):
                self.bichig(x, y, f"{gar}:" if i == 0 else "", 2.5)
                self.bichig(x + 34.0, y, mor, 2.5)
                y -= 4.6
            y -= 1.0
        if not self.t.batalgaa:
            y -= 3.0
            self.bichig(x, y, "≈ Хэмжээс ойролцоо — эскизээс уншаагүй.", 2.5)

    def barih(self) -> Drawing:
        """Бүх хэсгийг угсарна."""
        self.huree()
        self.zurag()
        self.tailbar()
        self.bulangiin_husnegt()
        return self.dwg


def _suuri_undur(t: Tulguur) -> float:
    """Суурийн планы нийт өндөр (м) — фундаментын нүд орсон."""
    hol = _hol_bairlal(t)
    fund = max(t.suuri * 0.16, 0.5)
    return 2.0 * (max((abs(p[1]) for p in hol), default=0.0) + fund)


def _masshtab_hos(undur_m: float, urgun_m: float, undur_mm: float, urgun_mm: float) -> int:
    """Өндөр, өргөн хоёуланг нь багтаах стандарт масштаб."""
    heregtei = max(undur_m * 1000.0 / max(undur_mm, 1.0), urgun_m * 1000.0 / max(urgun_mm, 1.0))
    for m in MASSHTAB:
        if m >= heregtei:
            return m
    return MASSHTAB[-1]


def _tailbar_mor(t: Tulguur) -> list[tuple[str, str]]:
    """Тайлбарын мөрүүд: (гарчиг, утга)."""
    jin = []
    if t.jin is not None:
        jin.append(f"{t.jin:,.0f} кг".replace(",", " "))
    if t.jin_ts is not None:
        jin.append(f"цинктэй {t.jin_ts:,.0f} кг".replace(",", " "))
    tsep = "нэг цепийн" if t.tsep == 1 else "хоёр цепийн"
    return [
        ("Шифр", t.shifr),
        ("Хүчдэл", f"ВЛ {t.hutsel} кВ, {tsep}"),
        ("Ангилал", t.angilal),
        ("Материал", t.material),
        ("Нийт өндөр", f"{_too(t.undur)} м"),
        ("Доод траверс", f"{_too(t.dood)} м"),
        ("Суурийн өргөн", f"{_too(t.suuri)} м"),
        ("Масс", ", ".join(jin)),
        ("Утас", t.utas),
        ("Трос", t.tros),
        ("Гололёдын район", t.mus),
        ("Монтажийн схем", t.shem),
        ("Эх сурвалж", f"ЭСП каталог 5713тм-т2, лист {t.huudas}"),
        ("Нэмэлт", t.temdeglel),
    ]


def _taslah(text: str, urt: int) -> list[str]:
    """Урт бичвэрийг мөр болгон таслана."""
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


def neg_huudas(t: Tulguur, out: Path, **tohirgoo: object) -> bool:
    """Нэг тулгуурыг АЗ хуудас болгож DWG-д бичнэ."""
    h = Huudas(t, **tohirgoo)  # type: ignore[arg-type]
    return _bicheh(h.barih(), out, f"{t.shifr} (A3, 1:{h.masshtab})")


def _buleg(t: Tulguur) -> str:
    """Тулгуурын бүлгийн гарчиг (танай зургийн нэршлээр)."""
    if t.angilal in (ANKER, TOGSGOL, SALAA):
        return "АНКЕР ТУЛГУУР / TENTION TOWER"
    return "ДУНДЫН ТУЛГУУР / SUSPENSION TOWER"


def erembe(t: Tulguur) -> tuple[str, float]:
    """Эрэмбэлэх түлхүүр: "+5", "+14" дагаварыг ТООГООР эрэмбэлнэ.

    Энгийн текст эрэмбэ нь "У110-2+14"-ийг "У110-2+5"-аас өмнө тавьдаг —
    зурагт хүснэгтийн дараалал буруу харагдана.
    """
    suuri, _, nemelt = t.shifr.partition("+")
    try:
        n = float(nemelt.replace(",", "."))
    except ValueError:
        n = 0.0
    return suuri, n


def _hol_bairlal(t: Tulguur) -> list[tuple[float, float]]:
    """Фундаментын байрлал (x, y) метрээр, планаас харснаар."""
    a = t.suuri / 2.0
    if t.hev == SHON:
        return [(0.0, 0.0)]
    if t.hev == TATLAGA:
        # Гол шон + гурван оттяжкын анкер
        return [(0.0, 0.0), (-t.tatlaga, 0.0), (t.tatlaga, 0.0)] if t.tatlaga else [(0.0, 0.0)]
    if t.hev in (PORTAL, PORTAL_T, HOS_SHON):
        b = max(t.hol, t.suuri) / 2.0
        return [(-b, 0.0), (b, 0.0)]
    if t.hev == GURAV_SHON:
        hol = max(t.hol, 4.0)
        return [(-hol, 0.0), (0.0, 0.0), (hol, 0.0)]
    return [(-a, -a), (a, -a), (a, a), (-a, a)]


def husnegt(
    bag: Sequence[Tulguur],
    out: Path,
    *,
    tsaas: str = "A3",
    masshtab: int | None = None,
    garchig: str = "ТОНОГЛОЛЫН ТЕХНИКИЙН ҮЗҮҮЛЭЛТ",
    shtamp: str = "",
) -> bool:
    """Нэг хуудсыг үүсгэж DWG болгож бичнэ."""
    h = Husnegt(bag, tsaas=tsaas, masshtab=masshtab, garchig=garchig, shtamp=shtamp)
    dwg = h.barih()
    return _bicheh(dwg, out, f"{out.stem} (1:{h.masshtab}, {len(bag)} багана)")


def main(argv: list[str] | None = None) -> int:
    """Командын мөр — шүүлтүүрээр сонгоод хуудас гаргана."""
    from tulguurdata import katalog

    p = argparse.ArgumentParser(prog="husnegt", description="Тулгуурын АЗ хуудас угсрах")
    p.add_argument("shifr", nargs="*", help="тулгуурын шифрүүд (өгөхгүй бол шүүлтүүр)")
    p.add_argument("--hutsel", type=int)
    p.add_argument("--angilal")
    p.add_argument("--material")
    p.add_argument("--tsep", type=int, choices=(1, 2))
    p.add_argument("--hai", default="")
    p.add_argument("--tsaas", default="A3", choices=tuple(TSAAS))
    p.add_argument("--masshtab", type=int, help="1:M (өгөхгүй бол автомат)")
    p.add_argument("--bagana", type=int, default=7, help="нэг хуудсанд хэдэн багана")
    p.add_argument("--shtamp", default=SHTAMP_BLOCK, help="штампын блокийн нэр")
    p.add_argument("--garchig", default="ТОНОГЛОЛЫН ТЕХНИКИЙН ҮЗҮҮЛЭЛТ")
    p.add_argument("--out", type=Path, default=OUTDIR)
    a = p.parse_args(argv)

    k = katalog()
    if a.shifr:
        bag = [k.ol(s) for s in a.shifr]
    else:
        bag = list(
            k.shuult(
                hutsel=a.hutsel, angilal=a.angilal, material=a.material,
                tsep=a.tsep, hai=a.hai,
            )
        )
    if not bag:
        print("тулгуур олдсонгүй")
        return 1

    # Анкерыг эхэнд, дундыг дараа нь — танай зургийн дараалал.
    bag.sort(key=lambda t: (_buleg(t) != "АНКЕР ТУЛГУУР / TENTION TOWER", *erembe(t)))

    a.out.mkdir(parents=True, exist_ok=True)
    ok = 0
    huudas = [bag[i : i + a.bagana] for i in range(0, len(bag), a.bagana)]
    for n, heseg in enumerate(huudas, start=1):
        ner = f"husnegt-{n:02d}" if len(huudas) > 1 else "husnegt"
        ok += husnegt(
            heseg, a.out / f"{ner}.dwg", tsaas=a.tsaas, masshtab=a.masshtab,
            garchig=a.garchig, shtamp=a.shtamp,
        )
    print(f"\n{ok}/{len(huudas)} хуудас -> {a.out}")
    return 0 if ok == len(huudas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
