r"""Загвар (компанийн стандарт) ба хуудас угсралтын тест — AutoCAD ХЭРЭГГҮЙ.

Энд шалгах зүйл: танай зургаас уншсан давхарга/фонт зөв тааж холбогдож
байгаа эсэх, блок оруулах entity нь DXF-ийн дарааллаар буугаж байгаа эсэх,
хуудасны масштаб бүх тулгуурыг нүдэнд багтааж байгаа эсэх.
"""

from __future__ import annotations

import husnegt
import pytest
import tulguurdata
import zagvar
from oruulga import Insert

KATALOG = tulguurdata.katalog()


# --------------------------------------------------------------------------
# Блок оруулах entity
# --------------------------------------------------------------------------


def test_insert_dwgforge_ийн_entity_протоколыг_хангана() -> None:
    """`Drawing.add()` хүлээж авахын тулд гурван зүйл хэрэгтэй."""
    from dwgforge import Drawing

    ins = Insert("ШТАМП", (10.0, 20.0), scale=0.3, layer="ХҮРЭЭ")
    assert ins.dxf_type == "INSERT"
    assert ins.layer == "ХҮРЭЭ"
    dwg = Drawing()
    dwg.ensure_layer("ХҮРЭЭ")
    assert dwg.add(ins) is ins
    assert len(dwg) == 1
    assert not dwg.missing_layers()


def test_insert_dxf_бүлгүүд() -> None:
    """Блокийн нэр (2), байрлал (10), масштаб (41-43), эргэлт (50) орно."""
    lisp = Insert("ШТАМП", (1.0, 2.0), scale=0.25, rotation=0.5).to_lisp()
    text = lisp.render()
    assert '"INSERT"' in text
    assert '"AcDbBlockReference"' in text
    assert '"ШТАМП"' in text or "chr" in text  # кирилл нь chr-ээр ч дамжиж болно
    for code in (2, 10, 41, 42, 43, 50):
        assert str(code) in text


def test_insert_буруу_утга_алдаа_өгнө() -> None:
    """Хоосон нэр, сөрөг масштаб чимээгүй өнгөрөх ёсгүй."""
    from dwgforge.errors import GeometryError

    with pytest.raises(GeometryError):
        Insert("", (0.0, 0.0))
    with pytest.raises(GeometryError):
        Insert("ШТАМП", (0.0, 0.0), scale=0.0)


# --------------------------------------------------------------------------
# Давхаргын таалт
# --------------------------------------------------------------------------


def _davharga(*ner: str) -> list[dict]:
    return [{"ner": n, "ongo": "7", "ltype": "Continuous", "flags": "0", "too": 10} for n in ner]


def test_taah_монгол_галигтай_нэрийг_таана() -> None:
    """Танай S-0-* стандартын нэрс бидний үүрэгт таарна."""
    d = _davharga(
        "S-0-1-VNDSEN", "S-0-2-NARIIN", "S-0-4-TEXT", "S-0-5-HEMJEE",
        "S-0-6-TENHLEG", "S-0-10-HATCH", "S-0-3-DASHED",
    )
    h = zagvar.taah(d, "S-0-2-NARIIN")
    assert h["ТУЛГУУР-БИЕ"] == "S-0-1-VNDSEN"
    assert h["ТУЛГУУР-СҮЛЖЭЭ"] == "S-0-2-NARIIN"
    assert h["ХЭМЖЭЭС"] == "S-0-5-HEMJEE"
    assert h["ТЭНХЛЭГ"] == "S-0-6-TENHLEG"
    assert h["ГАЗАР"] == "S-0-10-HATCH"


def test_taah_ажлын_бүлийг_импортын_хогоос_ялгана() -> None:
    """Импортлосон "hemjees" (олон entity) стандартыг дарах ёсгүй."""
    d = [
        {"ner": "hemjees", "ongo": "7", "ltype": "", "flags": "0", "too": 5247},
        {"ner": "S-0-5-HEMJEE", "ongo": "7", "ltype": "", "flags": "0", "too": 1088},
    ]
    assert zagvar.taah(d, "S-0-2-NARIIN")["ХЭМЖЭЭС"] == "S-0-5-HEMJEE"
    # Ажлын давхарга мэдэгдэхгүй бол хамгийн олон хэрэглэгдсэн нь ялна.
    assert zagvar.taah(d, "")["ХЭМЖЭЭС"] == "hemjees"


def test_ger_buli() -> None:
    """Бүлийн угтварыг ажлын давхаргаас гаргана."""
    assert zagvar.ger_buli("S-0-2-NARIIN") == "S-0-"
    assert zagvar.ger_buli("0") == ""


def test_bichgiin_hev_идэвхтэйг_эрхэмлэнэ() -> None:
    """Зохиогчийн ашиглаж байсан хэв нь кирилл гардаг нь батлагдсан."""
    medee = {
        "textstyle": "DRAW-2.5",
        "hev": [{"ner": "Standard", "font": "txt.shx"}, {"ner": "DRAW-2.5", "font": "isocpeu_mon.ttf"}],
    }
    assert zagvar.bichgiin_hev(medee) == "DRAW-2.5"
    # Идэвхтэй хэв нь хүснэгтэд байхгүй бол фонтоор сонгоно.
    medee["textstyle"] = "БАЙХГҮЙ"
    assert zagvar.bichgiin_hev(medee) == "DRAW-2.5"
    assert zagvar.bichgiin_hev({"hev": []}) == "Standard"


def _block(ner: str, urgun: float, undur: float, orsonoo: int, att: int = 0) -> dict:
    return {
        "ner": ner, "urgun": urgun, "undur": undur, "x0": 0.0, "y0": 0.0,
        "entity": 10, "orsonoo": orsonoo,
        "att": [{"tag": f"T{i}", "x": 0.0, "y": float(i), "h": 2.0} for i in range(att)],
    }


def test_huree_taah_хэмжээгээр_таана() -> None:
    """Хүрээг НЭРЭЭР нь биш, 420x297 гэсэн хэмжээгээр нь таана."""
    block = [
        _block("A3 ЖИШЭЭ", 410.0, 290.0, 50),  # ойролцоо ч таарахгүй
        _block("ХУУДАС", 420.0, 297.0, 20),
        _block("ТОМ", 1189.0, 841.0, 3),
    ]
    assert zagvar.huree_taah(block, "A3") == "ХУУДАС"
    assert zagvar.huree_taah(block, "A0") == "ТОМ"
    assert zagvar.huree_taah([], "A3") == ""


def test_shtamp_taah_олон_атрибуттайг_биш_олон_орсныг_сонгоно() -> None:
    """Өөрчлөлтийн хүснэгт 70 атрибуттай байж жинхэнэ штампыг дарах ёсгүй."""
    block = [
        _block("ӨӨРЧЛӨЛТ", 221.0, 36.0, 7, att=70),
        _block("ШТАМП", 170.0, 36.0, 127, att=12),
    ]
    sh = zagvar.shtamp_taah(block)
    assert sh["ner"] == "ШТАМП"
    assert len(sh["att"]) == 12
    assert sh["att"][0] == ["T0", 0.0, 0.0, 2.0]
    assert zagvar.shtamp_taah([_block("ХООСОН", 100.0, 20.0, 5)]) == {}


def test_taah_металл_хийц_биеийн_давхарга_руу_унана() -> None:
    """Траверс, тросостойк тусдаа давхаргагүй бол биетэй нэг давхаргад орно."""
    h = zagvar.taah(_davharga("S-0-1-VNDSEN", "S-0-2-NARIIN"), "S-0-2-NARIIN")
    assert h["ТУЛГУУР-ТРАВЕРС"] == "S-0-1-VNDSEN"
    assert h["ТУЛГУУР-ТРОСОСТОЙК"] == "S-0-1-VNDSEN"


# --------------------------------------------------------------------------
# Хуудас угсралт
# --------------------------------------------------------------------------


def test_masshtab_бүх_тулгуурыг_багтаана() -> None:
    """Сонгосон масштабаар хамгийн өндөр тулгуур нүдэнд багтах ёстой."""
    bag = [KATALOG.ol(s) for s in ("У110-2", "У110-2+14", "П110-4")]
    m = husnegt.masshtab_songoh(bag, urgun_mm=50.0, undur_mm=120.0)
    assert m in husnegt.MASSHTAB
    for t in bag:
        assert t.undur / m * 1000.0 <= 120.0 + 1e-9, t.shifr


def test_masshtab_стандарт_утга_буцаана() -> None:
    """Дурын тоо биш, зурагт бичихэд тохирох стандарт масштаб."""
    for undur_mm in (60.0, 90.0, 150.0):
        assert husnegt.masshtab_songoh(list(KATALOG.buh), 50.0, undur_mm) in husnegt.MASSHTAB


def test_erembe_нэмэлтийг_тоогоор_эрэмбэлнэ() -> None:
    """"+14" нь "+5"-аас ХОЙНО байх ёстой (текст эрэмбэ буруу өгдөг)."""
    shifr = ["У110-2+14", "У110-2", "У110-2+5", "У110-2+9"]
    bag = [KATALOG.ol(s) for s in shifr]
    bag.sort(key=husnegt.erembe)
    assert [t.shifr for t in bag] == ["У110-2", "У110-2+5", "У110-2+9", "У110-2+14"]


def test_buleg_анкер_дундыг_ялгана() -> None:
    """Анкер, төгсгөл, салаа нь нэг бүлэг; завсрын нь нөгөө бүлэг."""
    assert "TENTION" in husnegt._buleg(KATALOG.ol("У110-2"))
    assert "SUSPENSION" in husnegt._buleg(KATALOG.ol("П110-4"))
    assert "TENTION" in husnegt._buleg(KATALOG.ol("КСБ110-1"))


def test_hol_bairlal_хэв_бүрт_тохирно() -> None:
    """Фундаментын тоо нь тулгуурын хэвтэй нийцнэ."""
    assert len(husnegt._hol_bairlal(KATALOG.ol("П110-4"))) == 4  # сүлжээ = 4 хөл
    assert len(husnegt._hol_bairlal(KATALOG.ol("ПБ35-1"))) == 1  # шон = 1
    assert len(husnegt._hol_bairlal(KATALOG.ol("ПБ1"))) == 2  # портал = 2
    assert len(husnegt._hol_bairlal(KATALOG.ol("У1"))) == 3  # гурван шон = 3


def test_husnegt_бүрэн_баригдана() -> None:
    """Хуудас нь entity-тэй, бүх давхарга бүртгэлтэй, штамп орсон байна."""
    bag = [KATALOG.ol(s) for s in ("У110-2", "У110-2+5", "П110-4")]
    h = husnegt.Husnegt(bag, shtamp="ШТАМП")
    dwg = h.barih()
    assert len(dwg) > 200
    assert not dwg.missing_layers()
    assert sum(1 for e in dwg.entities if e.dxf_type == "INSERT") == 1
    text = " ".join(e.value for e in dwg.entities if e.dxf_type == "TEXT")
    for t in bag:
        assert t.shifr in text
    assert "ПК00+00" in text
    assert f"1:{h.masshtab}" in text


def test_husnegt_штампгүй_ч_ажиллана() -> None:
    """Танай блок байхгүй орчинд ч хуудас гарах ёстой."""
    dwg = husnegt.Husnegt([KATALOG.ol("П110-4")], shtamp="").barih()
    assert not any(e.dxf_type == "INSERT" for e in dwg.entities)
    assert len(dwg) > 50


def test_husnegt_цаасны_хэмжээ() -> None:
    """A3-аас том цаас сонговол багана өргөсөж, масштаб нарийсна."""
    bag = [KATALOG.ol(s) for s in ("У330-2+14", "П330-2")]
    a3 = husnegt.Husnegt(bag, tsaas="A3")
    a1 = husnegt.Husnegt(bag, tsaas="A1")
    assert a1.bagana_urgun > a3.bagana_urgun
    assert a1.masshtab <= a3.masshtab
