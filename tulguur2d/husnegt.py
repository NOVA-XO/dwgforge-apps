r"""АЗ хуудас угсрах — танай "нэг маягийн зураг"-ийн бүтцээр.

Танай нэг маягийн зургийн багцад ХОЁР өөр хуудас байдаг. Энэ модуль хоёуланг
нь гаргана:

`Husnegt` — ТЭМДЭГЛЭГЭЭНИЙ хуудас. Зүүн талд шошгын багана, баруун тийш
тулгуур бүр нэг багана. Мөрүүд нь дээрээс доош:

    ТУЛГУУР БАЙГУУЛАЛТЫН ДЭЭРХ ТЭМДЭГЛЭГЭЭ   план: шугам + ▽/○ + ПК00+00
    ТУЛГУУРЫН МАРК                            шифр
    ТУЛГУУРЫН ЗАГВАР                          урдаас харсан эскиз, хэмжээстэй
    СУУРИЛУУЛАЛТЫН СХЕМ                       фундаментын план
    МАТЕРИАЛ · ТРАВЕРС · МАСС · ТОО ШИРХЭГ    богино мөрүүд

Баганууд ДУНДЫН / АНКЕР гэж бүлэглэгдэж, дээр нь бүлгийн гарчиг гарна.
Доод зүүн буланд тэмдэглэгээний тайлбар.

`Huudas` — НЭГ ТУЛГУУРЫН хуудас. Дээр нь гарчиг ("<шифр> МАЯГИЙН <ангилал>
ТУЛГУУР" + масштаб), зүүн талд өндөрлөг ба суурийн план, баруун талд тайлбар
ба МАТЕРИАЛЫН ТҮҮВЭР, доор нь булангийн хүснэгт.

ТАНАЙ СТАНДАРТААС ЮУГ ӨӨРЧИЛСӨН БЭ. Тэмдэглэгээний хуудасны "ШОНГИЙН МАРК",
"ХӨНДЛӨВЧ", "ХЭРЭГЛЭГДЭХ ХҮРЭЭ" гурван мөрийг ЭСП каталог бөглөж чадахгүй —
тэнд шонгийн марк ч, хийцийн жагсаалт ч байхгүй. Мөрийн байрыг хоосон
үлдээхийн оронд каталогийн МЭДДЭГ зүйлээр сольсон: МАТЕРИАЛ, ТРАВЕРС, МАСС.
"ТОО ШИРХЭГ" хэвээрээ, төслөөр бөглөгдөнө.

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
    from collections.abc import Callable, Sequence

# -- цаасны хэмжээ, мм -------------------------------------------------------

TSAAS: dict[str, tuple[float, float]] = {
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}

ZAH_ZUUN = 20.0  # мм, зүүн зах (үдэлт)
ZAH = 5.0  # мм, бусад зах

# Тэмдэглэгээний хуудасны мөрийн өндөр, мм. Нийлбэр нь хүрээнээс бага байна.
SHOSHGO_URGUN = 34.0  # зүүн талын шошгын багана
MOR_GARCHIG = 7.0
MOR_PLAN = 46.0
MOR_NER = 6.0
MOR_SUURI = 26.0
MOR_JIJIG = 5.5  # доод дөрвөн богино мөр тус бүр
# Өндөрлөгийн ("ТУЛГУУРЫН ЗАГВАР") мөр нь үлдсэн зайг бүхэлд нь эзэлнэ.

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
H_SHOSHGO = 2.5  # тэмдэглэгээний хуудасны зүүн шошгын багана

#: Доод богино мөрүүдийн шошго. Танай хуудасны ШОНГИЙН МАРК / ХӨНДЛӨВЧ /
#: ХЭРЭГЛЭГДЭХ ХҮРЭЭ гурвыг ЭСП каталог бөглөж чадахгүй тул каталогийн
#: мэддэг зүйлээр сольсон (модулийн толгойг үз).
JIJIG_MOR: tuple[str, ...] = ("МАТЕРИАЛ", "ТРАВЕРС", "МАСС, кг", "ТОО ШИРХЭГ")

#: Тэмдэглэгээний хуудасны өндөр мөрүүдийн шошго — босоо бичигдэнэ.
SHOSHGO_PLAN = "ТУЛГУУР БАЙГУУЛАЛТЫН ДЭЭРХ ТЭМДЭГЛЭГЭЭ"
SHOSHGO_NER = "ТУЛГУУРЫН МАРК"
SHOSHGO_ZAGVAR = "ТУЛГУУРЫН ЗАГВАР"
SHOSHGO_SUURI = "СУУРИЛУУЛАЛТЫН СХЕМ"

# --------------------------------------------------------------------------
# Хуудасны блок, булангийн хүснэгт, хүний нэр — БҮГД `zagvar.json`-оос ирнэ.
# Эх кодод бичихгүй: тэдгээр нь тодорхой нэг захиалагчийн зургийн блокийн нэр,
# ажилтны нэр бөгөөд энэ repo нээлттэй. Байхгүй бол хуудас өөрийн хүрээтэйгээр,
# штампгүй гарна.
# --------------------------------------------------------------------------

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
_HUREE: dict = ZAGVAR.get("huree") or {}
A3_BLOCK: str = str(_HUREE.get("ner") or ZAGVAR.get("huree_block") or "")

#: Танай хүрээний ЗУРАХ ТАЛБАЙ (x0, y0, x1, y1), цаасны мм.
#:
#: Үүнийг таамаглаж болохгүй. Жишээ нь нэг АЗ блок гурван үүрлэсэн тэгш өнцөгттэй —
#: 0..420 (цаасны ирмэг), 15..415 (бүсийн зурвас), 20..410 x 10..287 (зурах
#: талбай). "5 мм зах" гэж таамаглавал гарчиг дээд хүрээгээр давж, баруун
#: багана хүрээнээс гарна. Блок дотроос хэмжсэн утга байвал түүнийг ашиглана.
_DOTOR = _HUREE.get("dotor") or []
HUREE_DOTOR: tuple[float, float, float, float] | None = (
    (float(_DOTOR[0]), float(_DOTOR[1]), float(_DOTOR[2]), float(_DOTOR[3]))
    if len(_DOTOR) == 4
    else None
)


def dotor_huree(tsaas: str, huree_block: str) -> tuple[float, float, float, float]:
    """Зурах талбайн хил (x0, y0, x1, y1), цаасны мм.

    Танай блокийг хэрэглэж байгаа бол ТҮҮНЭЭС хэмжсэн талбай, эс бөгөөс
    өгөгдмөл захын зай.
    """
    if huree_block and HUREE_DOTOR is not None:
        return HUREE_DOTOR
    u, o = TSAAS.get(tsaas, TSAAS["A3"])
    return ZAH_ZUUN, ZAH, u - ZAH, o - ZAH


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
        garchig: str = "ТУЛГУУР БАЙГУУЛАЛТЫН ТЭМДЭГЛЭГЭЭ БА ТУЛГУУРЫН ХЭМЖЭЭС",
        shtamp: str = SHTAMP_BLOCK,
        huree_block: str = "",
        tosol: str = "",
        ognoo: str = "",
        shifr_zurag: str = "",
    ) -> None:
        """Хуудасны хэмжээ, масштаб, баганын өргөнийг тооцно."""
        self.bag = list(bag)
        self.garchig = garchig
        self.shtamp = shtamp
        self.tosol = tosol
        self.ognoo = ognoo
        self.shifr_zurag = shifr_zurag
        self.tsaas_urgun, self.tsaas_undur = TSAAS.get(tsaas, TSAAS["A3"])
        # Танай хүрээний блок нь АЗ-ынх. Том цаасанд түүнийг тавьбал хэмжээ
        # зөрөх тул зөвхөн АЗ дээр хэрэглэнэ.
        self.huree_block = huree_block if tsaas == "A3" else ""

        # Хүрээний дотор талын хэмжээ, мм — танай блокоос хэмжсэн
        self.x0, self.y0, self.x1, self.y1 = dotor_huree(tsaas, self.huree_block)

        # Хүснэгтийн талбай — штампын дээр. Зүүн талд шошгын багана үлдэнэ.
        self.t_x0 = self.x0 + SHOSHGO_URGUN
        self.t_y0 = self.y0 + SHTAMP_UNDUR
        self.t_y1 = self.y1
        self.bagana_too = max(1, len(self.bag))
        self.bagana_urgun = (self.x1 - self.t_x0) / self.bagana_too

        jijig = MOR_JIJIG * len(JIJIG_MOR)
        bolomj = (self.t_y1 - self.t_y0) - MOR_GARCHIG - MOR_PLAN - MOR_NER - MOR_SUURI - jijig
        bolomj = max(bolomj, 40.0)
        self.mor_urd = bolomj
        self.masshtab = masshtab or masshtab_songoh(
            self.bag, self.bagana_urgun * 0.92, bolomj * 0.88
        )
        # Хоёр дахь дамжлага. Өргөн нь масштабыг тогтоосон бол (өргөн тулгуур,
        # оттяжкатай, олон багана) хамгийн өндөр тулгуур мөрөндөө багтаад
        # дээрээ асар их хоосон зай үлдээдэг. Мөрийг хэрэгцээнд нь тааруулаад
        # ИЛҮҮДЛИЙГ АЛГА БОЛГОХГҮЙ — план ба суурийн мөрөнд хуваарилна. Эс
        # тэгвээс хүснэгт хүрээндээ хүрэхгүй, доор нь хоосон нүд үлдэнэ.
        heregtei = max((t.undur for t in self.bag), default=0.0) * 1000.0 / self.masshtab + 10.0
        self.mor_urd = max(min(bolomj, heregtei), 40.0)
        iluu = bolomj - self.mor_urd
        self.mor_plan = MOR_PLAN + iluu * 0.45
        self.mor_suuri = MOR_SUURI + iluu * 0.55

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
        return deed - self.mor_plan, deed

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
        return deed - self.mor_suuri, deed

    def y_jijig(self, k: int) -> tuple[float, float]:
        """`k` дугаар богино мөрийн доод, дээд хил (мм) — дээрээс доош."""
        deed = self.y_suuri[0] - k * MOR_JIJIG
        return deed - MOR_JIJIG, deed

    def x_bagana(self, i: int) -> tuple[float, float]:
        """`i` дугаар баганын зүүн, баруун хил (мм)."""
        return self.t_x0 + i * self.bagana_urgun, self.t_x0 + (i + 1) * self.bagana_urgun

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
        """Танай хуудасны блок (байхгүй бол өөрийн хүрээ) + булангийн хүснэгт."""
        if self.huree_block:
            self.dwg.add(
                Insert(self.huree_block, (0.0, 0.0), scale=self.masshtab / 1000.0,
                       layer=lay(L_HUREE))
            )
        else:
            self.tegsheg(0.0, 0.0, self.tsaas_urgun, self.tsaas_undur, L_HUREE)
            self.tegsheg(self.x0, self.y0, self.x1, self.y1, L_HUREE)
        if self.shtamp:
            # Блокийн эх цэг нь баруун доод булан — хүрээний булантай нийлүүлнэ.
            _shtamp_oruulah(
                self.dwg, self.mm, self.shtamp, self.x1, self.y0,
                self.masshtab / 1000.0,
                {
                    "ТӨСЛИЙН-НЭР": self.tosol,
                    "ЗУРАГ-НЭР": self.garchig,
                    "АЗ": "A3",
                    "И_НЭР": INZHENER,
                    "Г_НЭР": ZURSAN,
                    "Ш_НЭР": SHALGASAN,
                    "МАСШ": f"1:{self.masshtab}",
                    "ОГНОО": self.ognoo,
                    "ШИФР": self.shifr_zurag,
                    "ТОО": "1",
                },
            )

    def tor(self) -> None:
        """Хүснэгтийн шугамууд: мөр хоорондын зураас, баганын тусгаарлагч."""
        mor_y = [self.t_y0, self.y_suuri[1], self.y_urd[1], self.y_ner[1], self.y_plan[1]]
        mor_y += [self.y_jijig(k)[1] for k in range(len(JIJIG_MOR))]
        # Бүлгийн гарчгийн мөр нь шошгын багана дээгүүр гардаггүй.
        for y in sorted(set(mor_y)):
            self.shugam(self.x0, y, self.x1, y, L_HUREE)
        self.shugam(self.t_x0, self.t_y1, self.x1, self.t_y1, L_HUREE)
        self.shugam(self.x0, self.t_y0, self.x0, self.y_plan[1], L_HUREE)
        for i in range(self.bagana_too + 1):
            x = self.t_x0 + i * self.bagana_urgun
            self.shugam(x, self.t_y0, x, self.y_plan[1], L_HUREE)

    def shoshgo(self) -> None:
        """Зүүн талын шошгын багана — өндөр мөрүүдэд босоо, богинод хэвтээ."""
        x_tov = self.x0 + SHOSHGO_URGUN / 2.0
        for shoshgo, (yl, yu) in (
            (SHOSHGO_PLAN, self.y_plan),
            (SHOSHGO_ZAGVAR, self.y_urd),
        ):
            # Босоо: эргэлт π/2, голлуулах цэг нь мөрийн голд. Багтах зай нь
            # МӨРИЙН ӨНДӨР — "ТУЛГУУР БАЙГУУЛАЛТЫН ДЭЭРХ ТЭМДЭГЛЭГЭЭ" 46 мм-т
            # багтахгүй тул үсгийн өндрийг багасгана.
            h = _shoshgo_undur(shoshgo, yu - yl)
            self.bichig(x_tov + h * 0.35, (yl + yu) / 2.0, shoshgo, h, ergelt=math.pi / 2.0)
        mor = [(SHOSHGO_NER, self.y_ner), (SHOSHGO_SUURI, self.y_suuri)]
        mor += [(s, self.y_jijig(k)) for k, s in enumerate(JIJIG_MOR)]
        for shoshgo, (yl, yu) in mor:
            h = _shoshgo_undur(shoshgo, SHOSHGO_URGUN)
            self.bichig(x_tov, (yl + yu) / 2.0 - h * 0.35, shoshgo, h)

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
        # Маршрутын шугам — тэмдгээс доош. Тэмдэг нь шугамын ДЭЭД үзүүрт.
        ys = yu - 6.0
        self.shugam(x, yl + 3.0, x, ys - 2.5, L_TENH)
        _plan_temdeg_zurah(self.z, self.mm, x, ys, t)
        # ПК бичиг — босоо, шугамын хажууд
        self.bichig(x - 2.0, yl + 5.0, "ПК00+00", H_PK, tov=False, ergelt=math.pi / 2.0)

    def jijig_mor_zurah(self, i: int, t: Tulguur) -> None:
        """Доод богино мөрүүдийн утга."""
        xa, xb = self.x_bagana(i)
        for k, utga in enumerate(_jijig_utga(t)):
            if not utga:
                continue
            yl, yu = self.y_jijig(k)
            self.bichig((xa + xb) / 2.0, (yl + yu) / 2.0 - H_HEM * 0.35, utga, H_HEM)

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
            # Схемийн ЯГ ДООР — мөр өндөрссөн ч бичээс схемээсээ салахгүй.
            hagas_mm = ry / self.masshtab * 1000.0
            self.bichig(cx, max(cy - hagas_mm - 4.0, yl + 1.5), _too(t.suuri), H_HEM)

    def tailbar(self) -> None:
        """Зүүн доод буланд тэмдэглэгээний тайлбар — хуудасны түлхүүр.

        Хоёр багана: зүүнд тулгуурын тэмдэг, баруунд эргэлт ба цооног.
        Штамп нь баруун доод буланд суудаг тул энэ нь түүнээс зүүн тийш байна.
        """
        y_deed = self.t_y0 - 7.0
        for x, mor in (
            (self.x0 + 6.0, (("dund", "Дундын тулгуур"), ("anker", "Анкер тулгуур"))),
            (self.x0 + 78.0, (("ergelt", "Эргэлтийн чиглэл /зүүн/"), ("tsooneg", "Ц-1  Геологийн цооног"))),
        ):
            y = y_deed
            for temdeg, bichver in mor:
                # Тэмдгийг богино шугамын дунд байрлуулна — танай зурагт мөн адил.
                self.shugam(x - 5.0, y, x + 5.0, y, L_TENH)
                _temdeg_zurah(self.z, self.mm, x, y, temdeg)
                self.bichig(x + 9.0, y - 1.0, bichver, H_TAILBAR, tov=False)
                y -= 9.0

        self.bichig(
            self.x0 + 6.0, self.y0 + 2.5,
            f"ЭСП каталог 5713тм-т2 (1976).  Хэмжээс метрээр.  Масштаб 1:{self.masshtab}.",
            2.0, tov=False,
        )

    def barih(self) -> Drawing:
        """Бүх хэсгийг угсарч Drawing буцаана."""
        self.huree()
        self.tor()
        self.shoshgo()
        self.buleg_garchig()
        for i, t in enumerate(self.bag):
            self.plan_temdeg(i, t)
            self.ner_nuh(i, t)
            self.urd_haragdats(i, t)
            self.suuri_plan(i, t)
            self.jijig_mor_zurah(i, t)
        self.tailbar()
        if not self.huree_block:
            # Танай блок дотор гарчиг нь булангийн хүснэгтэд ордог тул давхардуулахгүй.
            self.bichig(
                (self.t_x0 + self.x1) / 2.0, self.y1 + 1.5, self.garchig, H_GARCHIG,
                layer=L_BICHIG,
            )
        return self.dwg


# --------------------------------------------------------------------------
# Нэг тулгуур = нэг АЗ хуудас (танай хүрээний блок дотор)
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Материалын түүврийн багана: (гарчиг, өргөн мм). Нийлбэр нь штампын өргөн —
# хүснэгт нь штампын яг дээр, ирмэг нь тэгшхэн таарна.
# --------------------------------------------------------------------------

TUUVER_BAGANA: tuple[tuple[str, float], ...] = (
    ("№", 9.0),
    ("Хийцийн нэр", 48.0),
    ("Марк", 38.0),
    ("Хэмжих\nнэгж", 13.0),
    ("Тоо\nхэмжээ", 14.0),
    ("Нэгж", 13.0),
    ("Нийт", 13.0),
    ("Тайлбар", 22.44),
)

TUUVER_MOR = 4.6  # нэг мөрийн өндөр, мм
TUUVER_HOOSON = 8  # гараар бөглөх хоосон мөрийн тоо


class Huudas:
    """Нэг тулгуурыг танай АЗ хуудасны блок дотор зурна.

    Дээр нь гарчиг ба масштаб, зүүн талд өндөрлөгийн зураг + суурийн план,
    баруун талд ТАЙЛБАР ба МАТЕРИАЛЫН ТҮҮВЭР, баруун доод буланд булангийн
    хүснэгт (атрибутууд нь бөглөгдсөн).
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
        zurag_ner: str = "",
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

        self.x0, self.y0, self.x1, self.y1 = dotor_huree("A3", self.huree_block)
        # Баруун талын багана нь штампын өргөнтэй яг тэнцүү — түүний яг дээр
        # материалын түүвэр суух тул хоёр ирмэг нэг босоо шугам болно.
        self.tailbar_urgun = sum(u for _, u in TUUVER_BAGANA)
        self.zurag_x1 = self.x1 - self.tailbar_urgun - 4.0
        # Булангийн хүснэгтийн дээд ирмэг
        self.shtamp_deed = self.y0 + SHTAMP_UNDUR
        # Материалын түүврийн дээд ирмэг: гарчиг + толгой + мөрүүд
        self.tuuver_y0 = self.shtamp_deed + 3.0
        self.tuuver_undur = 5.0 + 7.0 + TUUVER_MOR * (1 + TUUVER_HOOSON)
        self.tuuver_y1 = self.tuuver_y0 + self.tuuver_undur

        self.zurag_urgun = self.zurag_x1 - self.x0
        # Гарчиг ба масштабын мөр дээд талд байр эзэлнэ.
        self.garchig_y = self.y1 - 7.0
        # Босоо чиглэлд өндөрлөг БА суурийн план хоёулаа багтах ёстой: хоёулаа
        # масштабаас хамаардаг тул нийлбэрээр нь масштабаа сонгоно, зайг мм-ээр
        # тусад нь хасна.
        self.suuri_undur_m = _suuri_undur(t)
        zai_mm = 28.0  # газрын шугам ба план хоорондын зай + доод захын зай
        bolomj = (self.garchig_y - 6.0 - self.y0 - zai_mm) * 0.97
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

    def shugam(self, x0: float, y0: float, x1: float, y1: float, layer: str = L_HUREE) -> None:
        """Цаасны мм координатаар шулуун татна."""
        self.z.shugam(self.mm(x0), self.mm(y0), self.mm(x1), self.mm(y1), layer)

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

    @property
    def garchig(self) -> str:
        """Хуудасны гарчиг танай нэршлээр: "П110-1 МАЯГИЙН ЗАВСРЫН ТУЛГУУР"."""
        return f"{self.t.shifr} МАЯГИЙН {self.t.angilal.upper()} ТУЛГУУР"

    def bulangiin_husnegt(self) -> None:
        """Булангийн хүснэгт + атрибутуудыг бөглөнө."""
        _shtamp_oruulah(
            self.dwg, self.mm, self.shtamp, self.x1, self.y0, self.masshtab / 1000.0,
            {
                "ТӨСЛИЙН-НЭР": self.tosol,
                "ЗУРАГ-НЭР": self.zurag_ner or self.garchig,
                "АЗ": "A3",
                "И_НЭР": self.inzhener,
                "МАСШ": f"1:{self.masshtab}",
                "ОГНОО": self.ognoo,
                "Г_НЭР": self.zursan,
                "Ш_НЭР": self.shalgasan,
                "ШИФР": self.shifr_zurag,
                "ТОО": "1",
            },
        )

    def gartsag(self) -> None:
        """Зургийн дээд гарчиг ба масштаб — танай маягаар доогуур зураастай."""
        cx = (self.x0 + self.zurag_x1) / 2.0
        self.bichig(cx, self.garchig_y, self.garchig, 4.0, tov=True)
        urt = len(self.garchig) * 4.0 * 0.62 / 2.0
        self.shugam(cx - urt, self.garchig_y - 1.8, cx + urt, self.garchig_y - 1.8, L_BICHIG)
        self.bichig(cx, self.garchig_y - 7.0, f"М 1:{self.masshtab}", 3.0, tov=True)

    def tuuver(self) -> None:
        """МАТЕРИАЛЫН ТҮҮВЭР — баруун доод хүснэгт.

        Каталог нь тулгуурын хийцийн жагсаалт агуулдаггүй: зөвхөн бүтэн массыг
        мэднэ. Тиймээс эхний мөрийг бөглөөд үлдсэнийг ГАРААР бөглөх хоосон
        мөрөөр гаргана — хуурамч мөр зохиохоос хоосон мөр дээр нь бичих нь дээр.
        """
        x0, x1 = self.x1 - self.tailbar_urgun, self.x1
        y0, y1 = self.tuuver_y0, self.tuuver_y1
        y_garchig = y1 - 5.0  # нэгтгэсэн гарчгийн мөрийн доод ирмэг
        y_tolgoi = y_garchig - 7.0  # багана толгойн доод ирмэг

        # Хүрээ ба хэвтээ шугамууд
        for y in (y0, y_tolgoi, y_garchig, y1):
            self.shugam(x0, y, x1, y)
        for k in range(1, 2 + TUUVER_HOOSON):
            self.shugam(x0, y_tolgoi - k * TUUVER_MOR, x1, y_tolgoi - k * TUUVER_MOR)

        # Багана толгой. "Жин, кг" нь Нэгж/Нийт хоёрыг нэгтгэнэ.
        x = x0
        for ner, urgun in TUUVER_BAGANA:
            self.shugam(x, y0, x, y_garchig)
            tov_x = x + urgun / 2.0
            if ner in ("Нэгж", "Нийт"):
                self.bichig(tov_x, y_tolgoi + 1.2, ner, 2.0, tov=True)
            else:
                mor = ner.split("\n")
                for i, m in enumerate(mor):
                    y_m = y_garchig - 2.8 - i * 2.6 - (0.0 if len(mor) > 1 else 0.7)
                    self.bichig(tov_x, y_m, m, 2.0, tov=True)
            x += urgun
        self.shugam(x1, y0, x1, y1)
        self.shugam(x0, y0, x0, y1)
        # "Жин, кг" — хоёр баганыг нэгтгэсэн дээд хагас
        x_jin = x0 + sum(u for n, u in TUUVER_BAGANA if n not in ("Нэгж", "Нийт", "Тайлбар"))
        urgun_jin = sum(u for n, u in TUUVER_BAGANA if n in ("Нэгж", "Нийт"))
        self.shugam(x_jin, y_tolgoi + 3.5, x_jin + urgun_jin, y_tolgoi + 3.5)
        self.bichig(x_jin + urgun_jin / 2.0, y_tolgoi + 4.6, "Жин, кг", 2.0, tov=True)

        # Нэгтгэсэн гарчгийн мөр
        self.bichig(
            (x0 + x1) / 2.0, y_garchig + 1.4,
            f"{self.t.shifr} тулгуурын материалын түүвэр", 2.2, tov=True,
        )

        # Эхний мөр — каталогийн мэддэг цорын ганц хийц
        jin = f"{self.t.jin:.0f}" if self.t.jin is not None else ""
        temdeglel = ""
        if self.t.jin_ts is not None:
            temdeglel = f"цинктэй {self.t.jin_ts:.0f}"
        utga = ("1", "Тулгуур", self.t.shifr, "ш", "1", jin, jin, temdeglel)
        y_mor = y_tolgoi - TUUVER_MOR + 1.4
        x = x0
        for (ner, urgun), v in zip(TUUVER_BAGANA, utga, strict=True):
            if v:
                if ner in ("Хийцийн нэр", "Марк"):
                    self.bichig(x + 1.5, y_mor, v, 2.0)
                else:
                    self.bichig(x + urgun / 2.0, y_mor, v, 2.0, tov=True)
            x += urgun

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
        """Баруун талын ТАЙЛБАР — материалын түүврийн дээр."""
        x0 = self.x1 - self.tailbar_urgun
        x = x0 + 2.0
        y = self.y1 - 6.0
        self.bichig(x, y, "ТАЙЛБАР", 3.0)
        self.shugam(x, y - 1.8, x + 22.0, y - 1.8, L_BICHIG)
        y -= 7.0
        for gar, utga in _tailbar_mor(self.t):
            if not utga:
                continue
            for i, mor in enumerate(_taslah(utga, 40)):
                if i == 0:
                    self.bichig(x, y, f"{gar}:", 2.2)
                self.bichig(x + 40.0, y, mor, 2.2)
                y -= 4.0
        if not self.t.batalgaa:
            y -= 2.5
            self.bichig(x, y, "≈ Хэмжээс ойролцоо — каталогийн эскизээс уншаагүй.", 2.2)

    def barih(self) -> Drawing:
        """Бүх хэсгийг угсарна."""
        self.huree()
        self.gartsag()
        self.zurag()
        self.tailbar()
        self.tuuver()
        self.bulangiin_husnegt()
        return self.dwg


def _shtamp_oruulah(
    dwg: Drawing,
    mm: Callable[[float], float],
    shtamp: str,
    bx: float,
    by: float,
    scale: float,
    utga: dict[str, str],
) -> None:
    """Булангийн хүснэгтийг оруулж атрибутуудыг бөглөнө.

    `bx`, `by` нь блокийн эх цэг цаасны мм-ээр — ихэнх штампынх нь баруун доод
    булан. Атрибутын байрлал мэдэгдэхгүй бол блокийг бөглөөгүй байдлаар нь
    тавина: буруу байрлалд бичээс хаяхаас хоосон штамп нь дээр.
    """
    if not shtamp:
        return
    atributtai = bool(SHTAMP_ATT)
    dwg.add(
        Insert(shtamp, (mm(bx), mm(by)), scale=scale, layer=lay(L_HUREE),
               atributtai=atributtai)
    )
    if not atributtai:
        return
    for tag, ax, ay, ah in SHTAMP_ATT:
        dwg.add(
            Attrib(
                tag,
                utga.get(tag, ""),
                (mm(bx + ax), mm(by + ay)),
                height=mm(ah),
                style=BICHGIIN_HEV,
                layer=lay(L_HUREE),
            )
        )
    dwg.add(SeqEnd(layer=lay(L_HUREE)))


#: Бичгийн хэвийн үсгийн ойролцоо өргөн / өндөр харьцаа. Яг утга нь фонтоос
#: хамаарна; шошго нүднээсээ халихгүй байх л зорилго тул бага зэрэг өгөөмөр.
USEG_HARTSAA = 0.65


def _shoshgo_undur(shoshgo: str, zai_mm: float) -> float:
    """`zai_mm` урттай нүдэнд багтах үсгийн өндөр (мм), `H_SHOSHGO`-оос хэтрэхгүй."""
    urt = max(len(shoshgo), 1) * USEG_HARTSAA
    return max(min(H_SHOSHGO, zai_mm * 0.94 / urt), 1.4)


def _temdeg_zurah(z: Zurag, mm: Callable[[float], float], x: float, y: float, hev: str) -> None:
    """Планы тэмдгийг цаасны мм координатад зурна (тайлбар ба план мөрөнд нэг ижил)."""
    if hev == "anker":
        r = 2.2
        z.zam(
            [(mm(x - r), mm(y + r)), (mm(x + r), mm(y + r)), (mm(x), mm(y - r))],
            L_BICHIG,
            hulhii=True,
        )
    elif hev == "dund":
        z.toirog(mm(x), mm(y), mm(2.0))
    elif hev == "tsooneg":
        z.toirog(mm(x), mm(y), mm(2.2))
        z.toirog(mm(x), mm(y), mm(0.9))
    elif hev == "ergelt":
        # Эргэлтийн чиглэл: шугамаас гарах ташуу зураас
        z.zam(
            [(mm(x - 2.5), mm(y - 2.5)), (mm(x + 2.5), mm(y + 2.5)), (mm(x + 0.5), mm(y + 2.5))],
            L_BICHIG,
        )


def _plan_temdeg_zurah(
    z: Zurag, mm: Callable[[float], float], x: float, y: float, t: Tulguur
) -> None:
    """Тулгуурын ангилалд тохирох планы тэмдэг."""
    hev = "anker" if t.angilal in (ANKER, TOGSGOL, SALAA) else "dund"
    _temdeg_zurah(z, mm, x, y, hev)


def _jijig_utga(t: Tulguur) -> tuple[str, ...]:
    """Доод богино мөрүүдийн утга, `JIJIG_MOR`-ийн дарааллаар."""
    traverse = "—"
    if t.tor:
        traverse = f"{_too(max(x.urt for x in t.tor))} м"
    return (
        t.material,
        traverse,
        f"{t.jin:.0f}" if t.jin is not None else "—",
        "",  # ТОО ШИРХЭГ — төслөөр бөглөгдөнө
    )


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
    """Тулгуурын бүлгийн гарчиг (танай нэршлээр)."""
    if t.angilal in (ANKER, TOGSGOL, SALAA):
        return "АНКЕР ТУЛГУУР"
    return "ДУНДЫН ТУЛГУУР"


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


def husnegt(bag: Sequence[Tulguur], out: Path, **tohirgoo: object) -> bool:
    """Нэг тэмдэглэгээний хуудсыг үүсгэж DWG болгож бичнэ."""
    h = Husnegt(bag, **tohirgoo)  # type: ignore[arg-type]
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
    p.add_argument("--huree-block", default=A3_BLOCK, help="АЗ хуудасны блокийн нэр")
    p.add_argument("--garchig", default="ТУЛГУУР БАЙГУУЛАЛТЫН ТЭМДЭГЛЭГЭЭ БА ТУЛГУУРЫН ХЭМЖЭЭС")
    p.add_argument("--tosol", default="", help="төслийн нэр (булангийн хүснэгтэд)")
    p.add_argument("--ognoo", default="", help="огноо")
    p.add_argument("--zurag-shifr", default="", help="зургийн шифр")
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

    # Дундын эхэнд, анкер дараа нь — танай хуудасны дараалал.
    bag.sort(key=lambda t: (_buleg(t) != "ДУНДЫН ТУЛГУУР", *erembe(t)))

    a.out.mkdir(parents=True, exist_ok=True)
    ok = 0
    huudas = [bag[i : i + a.bagana] for i in range(0, len(bag), a.bagana)]
    for n, heseg in enumerate(huudas, start=1):
        ner = f"husnegt-{n:02d}" if len(huudas) > 1 else "husnegt"
        ok += husnegt(
            heseg, a.out / f"{ner}.dwg", tsaas=a.tsaas, masshtab=a.masshtab,
            garchig=a.garchig, shtamp=a.shtamp, huree_block=a.huree_block,
            tosol=a.tosol, ognoo=a.ognoo, shifr_zurag=a.zurag_shifr,
        )
    print(f"\n{ok}/{len(huudas)} хуудас -> {a.out}")
    return 0 if ok == len(huudas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
