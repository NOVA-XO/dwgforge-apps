r"""Тулгуурын каталогийн өгөгдлийн сан — ЭСП-ийн 1968-1976 оны каталог (инв. 5713тм-т2).

Каталогийн хуудас бүр нэг `Huudas` блок болно: тухайн хуудасны бүх тулгуурт
нийтлэг зүйлийг (хүчдэл, ангилал, материал, гололёдын район, утас, тросны
марк) блокт нэг удаа бичээд, тулгуур бүрт зөвхөн өөрийнх нь ялгаатай зүйлийг
(шифр, хэмжээс, масс, монтажийн схем) бичнэ. Каталог өөрөө яг ийм бүтэцтэй.

ХЭМЖЭЭСИЙН ҮНЭН БАЙДАЛ. Каталог бол сканердсан гар зураг: шифр, масс,
монтажийн схем, утас/тросны марк нь тод уншигдана, эскиз дээрх хэмжээсийн
тоонууд заримдаа уншигдахгүй. Тиймээс бичлэг бүр `batalgaa` талбартай:

    batalgaa=True   — хэмжээсийг каталогийн эскизээс шууд уншсан
    batalgaa=False  — тухайн гэр бүлийн (ижил төрөл, хүчдэл) хэмжээсээс
                      гаргасан ойролцоо утга. Схемийн шинжтэй, зурагт
                      "ойролцоо" гэж тэмдэглэгдэнэ.

Аль ч утгыг засаж болно: эхний ажиллуулалтад `tulguuruud.json` үүсэх бөгөөд
тэнд байгаа утга энэ файлын утгыг дарж бичнэ.

Ажиллуулах:
    cd <repo>
    .\\.venv\\Scripts\\python.exe tulguur2d\\tulguursan.py     # хүснэгтийн тойм
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = HERE / "tulguuruud.json"

# -- ангилал ---------------------------------------------------------------

ZAVSAR = "завсрын"  # промежуточная
ZAVSAR_ONTSOG = "завсрын өнцгийн"  # промежуточная угловая
ANKER = "анкер-өнцгийн"  # анкерно-угловая
TOGSGOL = "төгсгөлийн"  # концевая
SALAA = "салаалах"  # ответвительная
SHILJILT = "шилжилтийн"  # переходная (большой переход)
POSTAVKA = "подставка"  # подставка (өндөрлөгч)

# -- материал --------------------------------------------------------------

GAN = "ган"
JB = "төмөр бетон"

# -- силуэтийн хэв (zurag.py эдгээрийг зурна) -------------------------------

SULJEE = "сүлжээ"  # свободностоящая решётчатая
TATLAGA = "оттяжкатай"  # на оттяжках (нэг шон + татлага)
PORTAL = "портал"  # портал (хоёр хөл + хөндлөвч)
PORTAL_T = "портал-татлага"  # портал на оттяжках (ВЛ 500 кВ ПБ)
SHON = "шон"  # ганц төмөр бетон шон
HOS_SHON = "хос шон"  # хоёр шон (портал ЖБ / ПВС)
GURAV_SHON = "гурван шон"  # гурван бие даасан шон (К, УБМ)


@dataclass(frozen=True, slots=True)
class Tor:
    """Нэг траверс: газраас дээших өндөр ба хоёр гарын урт (м).

    `zuun`/`baruun` нь тулгуурын тэнхлэгээс гадагш хэмжсэн урт. Нэг талдаа
    гартай траверс (жишээ нь салаалах тулгуур) бол нөгөө талыг 0 гэж бичнэ.
    """

    z: float
    zuun: float
    baruun: float

    @property
    def urt(self) -> float:
        """Траверсын нийт урт (м)."""
        return self.zuun + self.baruun


@dataclass(frozen=True, slots=True)
class Tulguur:
    """Каталогийн нэг мөр: нэг тулгуурын шифр, хэмжээс, масс, паспорт."""

    shifr: str
    hutsel: int  # кВ
    tsep: int  # цепийн тоо: 1 эсвэл 2
    angilal: str
    material: str
    hev: str

    undur: float  # нийт өндөр, м (тросостойк орно)
    dood: float  # доод траверс хүртэлх өндөр, м
    suuri: float  # суурийн (фундаментын тэнхлэг хоорондын) өргөн, м
    orgil: float  # биеийн оройн өргөн, м
    tor: tuple[Tor, ...]

    uzuur: int = 0  # тросостойкийн тоо (0, 1, 2)
    tatlaga: float = 0.0  # оттяжкийн анкерын зай тэнхлэгээс, м (0 = байхгүй)
    hol: float = 0.0  # порталын хөл хоорондын зай, м (0 = хамаарахгүй)

    jin: float | None = None  # масса цинкгүй, кг
    jin_ts: float | None = None  # масса цинктэй, кг
    shem: str = ""  # монтажийн схемийн дугаар
    huudas: int = 0  # каталогийн хуудас (лист)
    utas: str = ""  # марка проводов
    tros: str = ""  # марка троса
    mus: str = ""  # гололёдын район
    temdeglel: str = ""  # дополнительные данные
    batalgaa: bool = False  # хэмжээс каталогийн эскизээс уншсан эсэх

    @property
    def ner(self) -> str:
        """Файлын нэрэнд тохирсон, кирилл үсэггүй шифр."""
        return _translit(self.shifr)

    @property
    def torzai(self) -> float:
        """Хамгийн урт траверсын хагас (м) — зургийн өргөнийг тодорхойлно."""
        if not self.tor:
            return max(self.suuri, self.tatlaga) / 2.0
        return max(max(t.zuun, t.baruun) for t in self.tor)

    @property
    def urgun(self) -> float:
        """Зургийн нийт өргөн (м) — татлага, суурь, траверс гурвын хамгийн их нь."""
        return 2.0 * max(self.torzai, self.suuri / 2.0, self.tatlaga, self.hol / 2.0)


@dataclass(frozen=True, slots=True)
class Huudas:
    """Каталогийн нэг хуудас: нийтлэг талбарууд + тухайн хуудасны тулгуурууд."""

    huudas: int
    garchig: str
    tulguur: tuple[Tulguur, ...]


def T(
    shifr: str,
    *,
    tsep: int = 1,
    angilal: str = ZAVSAR,
    material: str = GAN,
    hev: str = SULJEE,
    undur: float,
    dood: float,
    suuri: float,
    orgil: float = 0.4,
    tor: tuple[tuple[float, float, float], ...] = (),
    uzuur: int = 0,
    tatlaga: float = 0.0,
    hol: float = 0.0,
    jin: float | None = None,
    jin_ts: float | None = None,
    shem: str = "",
    utas: str = "",
    tros: str = "",
    mus: str = "",
    temdeglel: str = "",
    batalgaa: bool = False,
    hutsel: int = 0,
    huudas: int = 0,
) -> Tulguur:
    """Хүснэгт бичихэд зориулсан богино байгуулагч.

    `tor` нь `(z, зүүн, баруун)` гурвалуудын цуваа — метрээр, газраас дээш.
    Хүчдэл, хуудсыг блокоос авах тул энд бичих шаардлагагүй.
    """
    return Tulguur(
        shifr=shifr,
        hutsel=hutsel,
        tsep=tsep,
        angilal=angilal,
        material=material,
        hev=hev,
        undur=undur,
        dood=dood,
        suuri=suuri,
        orgil=orgil,
        tor=tuple(Tor(z, zuun, baruun) for z, zuun, baruun in tor),
        uzuur=uzuur,
        tatlaga=tatlaga,
        hol=hol,
        jin=jin,
        jin_ts=jin_ts,
        shem=shem,
        huudas=huudas,
        utas=utas,
        tros=tros,
        mus=mus,
        temdeglel=temdeglel,
        batalgaa=batalgaa,
    )


def H(
    huudas: int,
    garchig: str,
    *,
    hutsel: int,
    utas: str = "",
    tros: str = "",
    mus: str = "",
    tulguur: tuple[Tulguur, ...] = (),
) -> Huudas:
    """Нэг хуудасны блок. Нийтлэг талбарыг тулгуур бүр рүү тараана."""
    filled = tuple(
        replace(
            t,
            hutsel=t.hutsel or hutsel,
            huudas=huudas,
            utas=t.utas or utas,
            tros=t.tros or tros,
            mus=t.mus or mus,
        )
        for t in tulguur
    )
    return Huudas(huudas=huudas, garchig=garchig, tulguur=filled)


# --------------------------------------------------------------------------
# Өндөрлөх подставка: "+5" гэсэн дагавар нь тулгуурыг 5 метр өндөрлөсөн гэсэн
# үг (каталогийн тайлбар, лист 10). Тиймээс биеийг бүхэлд нь дээш зөөж,
# суурийг өргөсгөнө — тусад нь эскиз бичих шаардлагагүй.
# --------------------------------------------------------------------------


def orgot(
    suuri_tulguur: Tulguur,
    shifr: str,
    nemelt: float,
    *,
    jin: float | None = None,
    jin_ts: float | None = None,
    suuri: float | None = None,
    temdeglel: str = "",
) -> Tulguur:
    """`suuri_tulguur`-ыг `nemelt` метрээр өндөрлөсөн хувилбар.

    Подставка нь биеийн ДООД талд ордог тул бүх траверс, орой `nemelt`-ээр
    дээшилж, суурийн өргөн нэмэгддэг (каталогийн эскизүүд үүнийг харуулдаг:
    У110-1 суурь 4.8 м, У110-1+5 нь 6.3 м).
    """
    return replace(
        suuri_tulguur,
        shifr=shifr,
        undur=suuri_tulguur.undur + nemelt,
        dood=suuri_tulguur.dood + nemelt,
        suuri=suuri if suuri is not None else suuri_tulguur.suuri * (1.0 + 0.055 * nemelt),
        tor=tuple(Tor(t.z + nemelt, t.zuun, t.baruun) for t in suuri_tulguur.tor),
        jin=jin,
        jin_ts=jin_ts,
        temdeglel=temdeglel or suuri_tulguur.temdeglel,
    )


def huvilbar(suuri_tulguur: Tulguur, shifr: str, **oorchlolt: object) -> Tulguur:
    """Ижил эскизтэй, зөвхөн масс/тэмдэглэл нь өөр хувилбар (жишээ нь "Н")."""
    return replace(suuri_tulguur, shifr=shifr, **oorchlolt)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Хайлт, шүүлт
# --------------------------------------------------------------------------

# Орос, монгол хоёрын кирилл хоёулаа орно: шифр нь орос (П, У, Б), тэмдэглэл
# нь монгол (зүүн, баруун) байдаг тул Ү, Ө хоёр ЗААВАЛ хэрэгтэй — эс тэгвээс
# файлын нэрэнд ASCII биш үсэг үлдэнэ.
_TRANSLIT = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L", "М": "M",
    "Н": "N", "О": "O", "Ө": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
    "У": "U", "Ү": "U", "Ф": "F", "Х": "H", "Ц": "Ts", "Ч": "Ch", "Ш": "Sh",
    "Щ": "Sch", "Ы": "Y", "Э": "E", "Ю": "Yu", "Я": "Ya", "Ь": "", "Ъ": "",
}  # fmt: skip

_NER_ZOVSHOOROL = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.+")


def _translit(shifr: str) -> str:
    """Кирилл шифрийг файлын нэрэнд тохирсон латин болгоно (П110-1 -> P110-1).

    Үр дүн нь зөвхөн ASCII: үлдсэн ямар ч тэмдэгт (хаалт, зай, ташуу зураас)
    зураас болж хувирна — эс тэгвээс Windows дээр файл үүсэхгүй эсвэл өөр
    системд шилжихэд эвдэрнэ.
    """
    out: list[str] = []
    for ch in shifr:
        upper = ch.upper()
        if upper in _TRANSLIT:
            latin = _TRANSLIT[upper]
            out.append(latin if ch.isupper() else latin.lower())
        elif ch in _NER_ZOVSHOOROL:
            out.append(ch)
        else:
            out.append("-")
    ner = "".join(out)
    while "--" in ner:
        ner = ner.replace("--", "-")
    return ner.strip("-")


@dataclass
class Katalog:
    """Ачаалагдсан каталог: хуудсууд ба шифрийн индекс."""

    huudas: tuple[Huudas, ...] = ()
    _index: dict[str, Tulguur] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Шифрийн индексийг барина (шифр давхардвал алдаа)."""
        for h in self.huudas:
            for t in h.tulguur:
                key = t.shifr.casefold()
                if key in self._index:
                    msg = f"шифр давхардлаа: {t.shifr} (хуудас {t.huudas})"
                    raise ValueError(msg)
                self._index[key] = t

    def __len__(self) -> int:
        """Каталог дахь тулгуурын тоо."""
        return len(self._index)

    @property
    def buh(self) -> tuple[Tulguur, ...]:
        """Бүх тулгуур, каталогийн дарааллаар."""
        return tuple(t for h in self.huudas for t in h.tulguur)

    def ol(self, shifr: str) -> Tulguur:
        """Шифрээр нэг тулгуур олно. Олдохгүй бол ойролцоо санал гаргана."""
        t = self._index.get(shifr.casefold())
        if t is not None:
            return t
        oir = [s.shifr for s in self.buh if shifr.casefold() in s.shifr.casefold()]
        sanal = f" Ойролцоо: {', '.join(oir[:8])}" if oir else ""
        msg = f"{shifr!r} каталогт алга.{sanal}"
        raise KeyError(msg)

    def shuult(
        self,
        *,
        hutsel: int | None = None,
        angilal: str | None = None,
        material: str | None = None,
        tsep: int | None = None,
        hev: str | None = None,
        hai: str = "",
    ) -> tuple[Tulguur, ...]:
        """Шүүлтүүрт таарсан тулгуурууд."""
        out = []
        for t in self.buh:
            if hutsel is not None and t.hutsel != hutsel:
                continue
            if angilal is not None and t.angilal != angilal:
                continue
            if material is not None and t.material != material:
                continue
            if tsep is not None and t.tsep != tsep:
                continue
            if hev is not None and t.hev != hev:
                continue
            if hai and hai.casefold() not in t.shifr.casefold():
                continue
            out.append(t)
        return tuple(out)

    def hutseluud(self) -> tuple[int, ...]:
        """Каталогт байгаа хүчдэлүүд, өсөхөөр."""
        return tuple(sorted({t.hutsel for t in self.buh}))


# --------------------------------------------------------------------------
# JSON-оор дарж бичих
# --------------------------------------------------------------------------


def _to_json(t: Tulguur) -> dict[str, object]:
    return {
        "hutsel": t.hutsel,
        "tsep": t.tsep,
        "angilal": t.angilal,
        "material": t.material,
        "hev": t.hev,
        "undur": t.undur,
        "dood": t.dood,
        "suuri": t.suuri,
        "orgil": t.orgil,
        "tor": [[x.z, x.zuun, x.baruun] for x in t.tor],
        "uzuur": t.uzuur,
        "tatlaga": t.tatlaga,
        "hol": t.hol,
        "jin": t.jin,
        "jin_ts": t.jin_ts,
        "shem": t.shem,
        "huudas": t.huudas,
        "utas": t.utas,
        "tros": t.tros,
        "mus": t.mus,
        "temdeglel": t.temdeglel,
        "batalgaa": t.batalgaa,
    }


def _from_json(shifr: str, raw: dict[str, object]) -> Tulguur:
    tor = tuple(Tor(float(a), float(b), float(c)) for a, b, c in raw.get("tor", []))  # type: ignore[union-attr]
    fields = {k: v for k, v in raw.items() if k != "tor"}
    return Tulguur(shifr=shifr, tor=tor, **fields)  # type: ignore[arg-type]


def write_json(katalog: Katalog, path: Path = CONFIG) -> Path:
    """Каталогийг JSON болгож бичнэ — засварлах, харьцуулах зориулалттай."""
    data = {
        "_тайлбар": (
            "Хэмжээсийг энд засна (метрээр). batalgaa=false бол хэмжээс нь "
            "каталогийн эскизээс биш, ижил төрлийн тулгуураас гаргасан ойролцоо "
            "утга. Засаад batalgaa=true болговол зурагт 'ойролцоо' гэж бичихээ болино."
        ),
        "tulguur": {t.shifr: _to_json(t) for t in katalog.buh},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(huudas_data: tuple[Huudas, ...], path: Path = CONFIG) -> Katalog:
    """Каталогийг ачаална. `tulguuruud.json` байвал түүний утга давамгайлна."""
    katalog = Katalog(huudas_data)
    if not path.is_file():
        return katalog
    raw = json.loads(path.read_text(encoding="utf-8"))
    override = raw.get("tulguur", {})
    if not override:
        return katalog
    huudas = tuple(
        Huudas(
            huudas=h.huudas,
            garchig=h.garchig,
            tulguur=tuple(
                _from_json(t.shifr, override[t.shifr]) if t.shifr in override else t
                for t in h.tulguur
            ),
        )
        for h in katalog.huudas
    )
    return Katalog(huudas)


# Өгөгдөл нь `tulguurdata.py` дотор. Тэр модуль энэ схемийг импортлодог тул
# энд буцаад импортлохгүй — каталогоо `from tulguurdata import katalog` гэж ав.
