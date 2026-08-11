r"""tulguur2d-ийн каталог ба зурагчийн тест — AutoCAD ХЭРЭГГҮЙ.

Зурагч нь `Drawing` объект хүртэл л шалгагдана; түүнийг DWG болгох ажил бол
`dwgforge`-ийн тест. Энд шалгах зүйл нь: каталогийн бүрэн бүтэн байдал
(шифр давхардаагүй, хэмжээс уялдаатай) ба зурагч бүх 371 мөрийг унахгүйгээр
геометр болгож чадах эсэх.
"""

from __future__ import annotations

import json

import pytest
import tulguurdata
import tulguursan
from tulguursan import GAN, JB, Katalog, Tor, Tulguur

KATALOG = tulguurdata.katalog()
BUH = KATALOG.buh


def test_katalog_ачаалагдана() -> None:
    """Каталог хоосон биш, хуудас бүр тулгууртай."""
    assert len(KATALOG) > 300
    assert len(BUH) == len(KATALOG)
    assert all(h.tulguur for h in KATALOG.huudas)
    assert all(h.garchig for h in KATALOG.huudas)


def test_шифр_давхардаагүй() -> None:
    """Индекс барих үед давхардал алдаа өгдөг — энэ нь түүнийг батална."""
    shifr = [t.shifr for t in BUH]
    assert len(set(shifr)) == len(shifr)


def test_файлын_нэр_давхардаагүй() -> None:
    """Кирилл шифр латин болоход хоёр тулгуур нэг файл руу бичигдэх ёсгүй."""
    ner = [t.ner for t in BUH]
    assert len(set(ner)) == len(ner)
    for t in BUH:
        assert t.ner.isascii(), t.shifr
        assert not set(t.ner) & set('<>:"/\\|?*'), t.ner


@pytest.mark.parametrize("t", BUH, ids=lambda t: t.shifr)
def test_хэмжээс_уялдаатай(t: Tulguur) -> None:
    """Өндөр эерэг, доод траверс нийт өндрөөс хэтрэхгүй, траверс биед багтана."""
    assert t.undur > 0.0
    assert 0.0 <= t.dood <= t.undur + 1e-9, t.shifr
    assert t.suuri >= 0.0
    assert t.tsep in (1, 2)
    assert t.hutsel in (35, 110, 150, 220, 330, 500)
    assert t.material in (GAN, JB)
    assert 12 <= t.huudas <= 82
    for tor in t.tor:
        assert 0.0 < tor.z <= t.undur + 1e-9, f"{t.shifr}: траверс {tor.z} > {t.undur}"
        assert tor.zuun >= 0.0 and tor.baruun >= 0.0
        assert tor.urt > 0.0, f"{t.shifr}: хоёр талдаа гаргүй траверс"


def test_завсрын_опор_доод_траверстай() -> None:
    """Завсрын опорын доод траверс нь пролётын хүснэгтийн габаритаас гардаг."""
    for t in BUH:
        if t.angilal == tulguursan.ZAVSAR and t.tor:
            assert t.dood >= 3.0, t.shifr


def test_масс_бодитой() -> None:
    """Масс өгөгдсөн бол эерэг, цинктэй нь цинкгүйгээсээ хүнд."""
    for t in BUH:
        if t.jin is not None:
            assert t.jin > 0.0, t.shifr
        if t.jin is not None and t.jin_ts is not None:
            assert t.jin_ts >= t.jin, t.shifr


def test_ol_олдохгүй_үед_санал_гаргана() -> None:
    """Буруу шифрт зүгээр KeyError биш, ойролцоо хувилбарууд гарна."""
    with pytest.raises(KeyError, match="Ойролцоо"):
        KATALOG.ol("П110")
    assert KATALOG.ol("п110-1").shifr == "П110-1"  # том/жижиг үсэг хамаарахгүй


def test_shuult_шүүнэ() -> None:
    """Шүүлтүүр бүр өөрийн талбарыг шүүнэ, хосолбол огтлолцоно."""
    zuun_arav = KATALOG.shuult(hutsel=110)
    assert zuun_arav and all(t.hutsel == 110 for t in zuun_arav)
    jb = KATALOG.shuult(material=JB)
    assert jb and all(t.material == JB for t in jb)
    hos = KATALOG.shuult(hutsel=220, tsep=2)
    assert hos and all(t.hutsel == 220 and t.tsep == 2 for t in hos)
    assert all("У330" in t.shifr for t in KATALOG.shuult(hai="У330"))
    assert KATALOG.shuult(hutsel=35, material=JB, tsep=2)


def test_hutseluud_эрэмбэлэгдсэн() -> None:
    """Хүчдэлүүд өсөх дарааллаар, давхардалгүй."""
    kv = KATALOG.hutseluud()
    assert kv == tuple(sorted(set(kv)))
    assert kv == (35, 110, 150, 220, 330, 500)


def test_json_буцаж_ижил_гарна(tmp_path) -> None:
    """JSON-оор бичээд буцааж уншихад хэмжээс өөрчлөгдөхгүй."""
    path = tmp_path / "tulguuruud.json"
    tulguursan.write_json(KATALOG, path)
    dahin = tulguursan.load(tulguurdata.HUUDAS, path)
    assert len(dahin) == len(KATALOG)
    for eh in BUH:
        shine = dahin.ol(eh.shifr)
        assert shine == eh, eh.shifr


def test_json_дарж_бичнэ(tmp_path) -> None:
    """`tulguuruud.json` дахь утга нь Python дахь утгыг дардаг."""
    path = tmp_path / "tulguuruud.json"
    tulguursan.write_json(KATALOG, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["tulguur"]["П110-1"]["undur"] = 99.0
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    assert tulguursan.load(tulguurdata.HUUDAS, path).ol("П110-1").undur == 99.0


def test_давхардсан_шифр_алдаа_өгнө() -> None:
    """Хоёр ижил шифр нэг каталогт орвол чимээгүй алдагдахгүй."""
    t = BUH[0]
    huudas = tulguursan.Huudas(huudas=12, garchig="тест", tulguur=(t, t))
    with pytest.raises(ValueError, match="давхардлаа"):
        Katalog((huudas,))


def test_tor_урт() -> None:
    """`Tor.urt` нь хоёр гарын нийлбэр."""
    assert Tor(10.0, 2.0, 3.0).urt == 5.0


# --------------------------------------------------------------------------
# Зурагч
# --------------------------------------------------------------------------


@pytest.mark.parametrize("t", BUH, ids=lambda t: t.shifr)
def test_бүх_тулгуур_зурагдана(t: Tulguur) -> None:
    """Мөр бүр геометр болно: хангалттай элемент, бүх давхарга бүртгэлтэй."""
    import zurag

    dwg = zurag.barih(t)
    assert len(dwg) > 20, f"{t.shifr}: хэт цөөн элемент"
    # `zagvar.json` байвал давхарга нь КОМПАНИЙН нэрээр бүртгэгдэнэ — тест нь
    # хоёр горимд ажиллахын тулд холбоосыг дамжуулж шалгана.
    burtgel = {d.name for d in dwg.layers}
    assert {zurag.lay(ner) for ner, _ in zurag.DAVHARGA} == burtgel
    # Бүртгэгдээгүй давхарга ашиглавал AutoCAD өөрөө үүсгэчихдэг тул анзаарагдахгүй.
    assert not dwg.missing_layers(), t.shifr


def test_зураг_газрын_түвшнээс_дээш() -> None:
    """Тулгуурын бие газраас дээш — паспорт, хэмжээс л доор байна."""
    import zurag

    t = KATALOG.ol("П110-1")
    dwg = zurag.barih(t, hemjees=False, huree=False)
    hiits = {zurag.lay(x) for x in (zurag.L_BIE, zurag.L_TOR, zurag.L_TROS)}
    bie = [e for e in dwg.entities if e.layer in hiits]
    assert bie
    for e in bie:
        for p in getattr(e, "points", (getattr(e, "start", None), getattr(e, "end", None))):
            if p is not None:
                assert p.y >= -0.01, f"{t.shifr}: {e.dxf_type} газраас доош"


def test_хэмжээс_нэмэгддэг() -> None:
    """`hemjees=False` нь хэмжээсийн давхаргын элементийг арилгана."""
    import zurag

    t = KATALOG.ol("У220-2")
    hemtei = zurag.barih(t, hemjees=True)
    hemgui = zurag.barih(t, hemjees=False)
    hem = zurag.lay(zurag.L_HEM)
    assert sum(1 for e in hemtei.entities if e.layer == hem) > 0
    assert sum(1 for e in hemgui.entities if e.layer == hem) == 0
    assert len(hemtei) > len(hemgui)


def test_паспортод_шифр_ба_лист_орно() -> None:
    """Зураг өөрөө хаанаас гарсныг хэлдэг байх ёстой."""
    import zurag

    t = KATALOG.ol("ПБ35-1")
    text = " ".join(
        e.value for e in zurag.barih(t).entities if e.dxf_type == "TEXT"
    )
    assert t.shifr in text
    assert f"лист {t.huudas}" in text
    assert "5713тм-т2" in text
    assert "төмөр бетон" in text


def test_ойролцоо_хэмжээс_тэмдэглэгдэнэ() -> None:
    """`batalgaa=False` бол зураг дээр анхааруулга гарна."""
    from dataclasses import replace

    import zurag

    t = replace(KATALOG.ol("П110-1"), batalgaa=False)
    text = " ".join(e.value for e in zurag.barih(t).entities if e.dxf_type == "TEXT")
    assert "ойролцоо" in text


def test_толгой_зурагт_бүх_хэв_орно() -> None:
    """Каталогийн 7 силуэтийн хэв бүрт наад зах нь нэг тулгуур байх ёстой."""
    import zurag

    hev = {t.hev for t in BUH}
    assert len(hev) >= 6
    for h in hev:
        t = next(x for x in BUH if x.hev == h)
        assert len(zurag.barih(t)) > 20, h
