r"""Компанийн зургаас СТАНДАРТЫГ татаж авах — давхарга, бичгийн хэв, блок.

Зорилго: бидний үүсгэсэн эскиз танай бусад зурагтай ижил харагдах. Үүний тулд
шинэ давхарга/фонт зохиохгүй, танай зурагт БАЙГААГ нь ашиглана.

    python tulguur2d/zagvar.py унших <танай.dwg>     # дотор нь юу байгааг харах
    python tulguur2d/zagvar.py holboh <танай.dwg>    # zagvar.json үүсгэх
    python tulguur2d/zagvar.py uram <танай.dwg>      # цэвэр үрлэг DWG бэлдэх

Гурван зүйл татагдана:

  ДАВХАРГА  нэр, өнгө, шугамын төрөл, зузаан. `zagvar.json` дотор бидний
            дотоод үүрэг (бие, траверс, хэмжээс...) танай давхарга руу холбогдоно.
  БИЧГИЙН ХЭВ (STYLE) фонтын файл (.shx/.ttf), өргөний коэффициент. Кирилл
            зөв гарахын тулд ЗААВАЛ танай хэвийг ашиглана.
  БЛОК      нэрсийн жагсаалт — штамп, тэмдэглэгээ. Эдгээрийг зурагтаа
            INSERT хийж болно (`zurag.py`-ийн `block` параметр).

Эх файлыг ХЭЗЭЭ Ч ХӨНДӨХГҮЙ: зөвхөн уншина, `uram` нь ХУУЛБАР дээр ажиллана.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge.backends import find_accoreconsole

HERE = Path(__file__).parent
ZAGVAR = HERE / "zagvar.json"

# Талбарын салгагч. .scr файлд ЗАЙ, ТАБ нь ENTER гэж тоологддог тул
# тэдгээрийг ашиглаж болохгүй; xref-ийн давхарга "XREF|LAYER" гэж
# нэрлэгддэг тул ганц "|" ч болохгүй. Энэ гурвал нэрэнд таарахгүй.
SEP = "~@~"

# accoreconsole дуусаагүй командыг барьж гацдаг тул үлдэгдлийг цэвэрлэнэ.
DRAIN = (
    '(setq _d 0) (while (and (/= (getvar "CMDNAMES") "") (< _d 30)) (command "") (setq _d (1+ _d)))'
)

# Бидний дотоод үүрэг → тайлбар. `holboh` нь эдгээрийг танай давхарга руу таана.
UUREG: dict[str, str] = {
    "ТУЛГУУР-БИЕ": "тулгуурын биеийн гадна контур",
    "ТУЛГУУР-СҮЛЖЭЭ": "сүлжээ, раскос, дотоод холбоос",
    "ТУЛГУУР-ТРАВЕРС": "траверс",
    "ТУЛГУУР-ТРОСОСТОЙК": "тросостойк, молниеотвод",
    "ТУЛГУУР-ОТТЯЖКА": "оттяжка",
    "ГАЗАР": "газрын шугам, штриховк",
    "ТЭНХЛЭГ": "тулгуурын тэнхлэг (тасархай)",
    "ХЭМЖЭЭС": "хэмжээсийн шугам, тоо",
    "БИЧИГ": "бичээс, паспорт",
    "ХҮРЭЭ": "хүрээ",
}


def _unshih_lisp() -> list[str]:
    """Хүснэгтүүдийг (LAYER, STYLE, DIMSTYLE, LTYPE, BLOCK) уншиж хэвлэх LISP."""
    return [
        '(setvar "CMDECHO" 0)',
        '(defun PR (s) (princ (strcat "\n@@@" s)) (princ))',
        '(defun S (x) (if x x ""))',
        '(defun N (x) (if x (itoa x) ""))',
        '(defun R (x) (if x (rtos x 2 3) ""))',
        DRAIN,
        f'(PR (strcat "DWG{SEP}" (getvar "DWGNAME")))',
        f'(PR (strcat "INSUNITS{SEP}" (itoa (getvar "INSUNITS"))))',
        f'(PR (strcat "DIMSCALE{SEP}" (R (getvar "DIMSCALE"))))',
        f'(PR (strcat "LTSCALE{SEP}" (R (getvar "LTSCALE"))))',
        f'(PR (strcat "TEXTSTYLE{SEP}" (getvar "TEXTSTYLE")))',
        f'(PR (strcat "CLAYER{SEP}" (getvar "CLAYER")))',
        # --- давхарга: нэр, өнгө, шугамын төрөл, тугнууд, ашиглалтын тоо ---
        '(setq L (tblnext "LAYER" T))',
        "(while L"
        ' (setq nm (cdr (assoc 2 L)) ss (ssget "_X" (list (cons 8 nm))))'
        f' (PR (strcat "LAYER{SEP}" nm "{SEP}" (N (cdr (assoc 62 L))) "{SEP}"'
        f' (S (cdr (assoc 6 L))) "{SEP}" (N (cdr (assoc 70 L))) "{SEP}"'
        ' (if ss (itoa (sslength ss)) "0")))'
        ' (setq L (tblnext "LAYER")))',
        # --- бичгийн хэв: фонтын файл, өндөр, өргөний коэффициент ---
        '(setq T1 (tblnext "STYLE" T))',
        "(while T1"
        f' (PR (strcat "STYLE{SEP}" (S (cdr (assoc 2 T1))) "{SEP}" (S (cdr (assoc 3 T1)))'
        f' "{SEP}" (S (cdr (assoc 4 T1))) "{SEP}" (R (cdr (assoc 40 T1)))'
        f' "{SEP}" (R (cdr (assoc 41 T1))) "{SEP}" (R (cdr (assoc 50 T1)))'
        f' "{SEP}" (N (cdr (assoc 70 T1)))))'
        ' (setq T1 (tblnext "STYLE")))',
        # --- хэмжээсийн хэв ---
        '(setq D (tblnext "DIMSTYLE" T))',
        f'(while D (PR (strcat "DIMSTYLE{SEP}" (S (cdr (assoc 2 D)))))'
        ' (setq D (tblnext "DIMSTYLE")))',
        # --- шугамын төрөл ---
        '(setq Y (tblnext "LTYPE" T))',
        f'(while Y (PR (strcat "LTYPE{SEP}" (S (cdr (assoc 2 Y))))) (setq Y (tblnext "LTYPE")))',
        # --- блок: нэр, entity тоо, ХЭМЖЭЭ, атрибутууд (нэргүйг алгасна) ---
        # Хэмжээг цэгийн бүлгүүдээс (10, 11) авна: core console дээр
        # vla-getboundingbox найдваргүй ажилладаг.
        '(setq B (tblnext "BLOCK" T))',
        "(while B"
        " (setq nm (cdr (assoc 2 B)))"
        ' (if (not (wcmatch nm "`**"))'
        '  (progn (setq e (cdr (assoc -2 (entget (tblobjname "BLOCK" nm)))) k 0'
        "          xa 1e9 ya 1e9 xb -1e9 yb -1e9)"
        "   (while e (setq d (entget e) k (1+ k))"
        "    (foreach g d (if (and (listp (cdr g)) (member (car g) (list 10 11)))"
        "     (progn (setq q (cdr g))"
        "      (setq xa (min xa (car q)) xb (max xb (car q))"
        "            ya (min ya (cadr q)) yb (max yb (cadr q))))))"
        '    (if (= (cdr (assoc 0 d)) "ATTDEF")'
        f'     (PR (strcat "ATT{SEP}" nm "{SEP}" (S (cdr (assoc 2 d))) "{SEP}"'
        f'      (R (car (cdr (assoc 10 d)))) "{SEP}" (R (cadr (cdr (assoc 10 d)))) "{SEP}"'
        '      (R (cdr (assoc 40 d))))))'
        "    (setq e (entnext e)))"
        '   (setq ss (ssget "_X" (list (cons 2 nm))))'
        f'   (PR (strcat "BLOCK{SEP}" nm "{SEP}" (itoa k) "{SEP}"'
        f'    (if ss (itoa (sslength ss)) "0") "{SEP}"'
        f'    (if (> xb -1e8) (R (- xb xa)) "") "{SEP}"'
        f'    (if (> yb -1e8) (R (- yb ya)) "") "{SEP}"'
        f'    (if (> xb -1e8) (R xa) "") "{SEP}"'
        '    (if (> yb -1e8) (R ya) "")))))'
        ' (setq B (tblnext "BLOCK")))',
        '(PR "DONE")',
        "(princ)",
    ]


def _ajilluulah(dwg: Path, forms: list[str], *, timeout: float = 900.0) -> str:
    """accoreconsole-оор LISP ажиллуулж, хэвлэсэн бүхнийг текстээр буцаана."""
    exe = find_accoreconsole()
    if exe is None:
        msg = "accoreconsole олдсонгүй — AutoCAD/Civil 3D суулгасан эсэхээ шалгана уу"
        raise RuntimeError(msg)
    scr = dwg.with_name(dwg.stem + "-zagvar.scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(forms) + "\r\n").encode("utf-8"))
    try:
        proc = subprocess.run(
            [str(exe), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=str(dwg.parent),
        )
    finally:
        scr.unlink(missing_ok=True)
    return (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")


def _mor(text: str, ner: str) -> list[list[str]]:
    """`@@@NER<таб>a<таб>b` мөрүүдийг талбар болгон задална.

    Салгагч нь ТАБ: xref-ийн давхарга "XREF|LAYER" гэж нэрлэгддэг тул
    босоо зураас салгагч болж чадахгүй.
    """
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith(f"@@@{ner}{SEP}"):
            out.append(s[3 + len(ner) + len(SEP) :].split(SEP))
    return out


def _too(raw: str) -> int:
    """LISP-ээс ирсэн тоог уншина; "nil"/хоосон бол 0."""
    raw = (raw or "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else 0


def _bod(raw: str) -> float:
    """LISP-ээс ирсэн бодит тоог уншина; уншигдахгүй бол 0.0."""
    try:
        return float((raw or "").strip())
    except ValueError:
        return 0.0


def _neg(text: str, ner: str) -> str:
    v = _mor(text, ner)
    return v[0][0] if v else ""


def unshih(dwg: Path) -> dict:
    """DWG-ийн хүснэгтүүдийг уншиж, бүтэцтэй өгөгдөл болгоно."""
    text = _ajilluulah(dwg, _unshih_lisp())
    if "@@@DONE" not in text:
        aldaa = [ln.strip() for ln in text.splitlines() if "error" in ln.lower()][:3]
        msg = "AutoCAD зургийг уншиж дуусгасангүй. " + " / ".join(aldaa)
        raise RuntimeError(msg)
    atts: dict[str, list[dict]] = {}
    for r in _mor(text, "ATT"):
        if len(r) >= 5:
            atts.setdefault(r[0], []).append(
                {"tag": r[1], "x": _bod(r[2]), "y": _bod(r[3]), "h": _bod(r[4])}
            )
    return {
        "esh": str(dwg),
        "insunits": _neg(text, "INSUNITS"),
        "dimscale": _neg(text, "DIMSCALE"),
        "ltscale": _neg(text, "LTSCALE"),
        "textstyle": _neg(text, "TEXTSTYLE"),
        "clayer": _neg(text, "CLAYER"),
        "davharga": [
            {"ner": r[0], "ongo": r[1], "ltype": r[2], "flags": r[3], "too": _too(r[4])}
            for r in _mor(text, "LAYER")
            if len(r) >= 5
        ],
        "hev": [
            {"ner": r[0], "font": r[1], "bigfont": r[2], "undur": r[3], "urgun": r[4]}
            for r in _mor(text, "STYLE")
            if len(r) >= 5
        ],
        "dimhev": [r[0] for r in _mor(text, "DIMSTYLE")],
        "ltype": [r[0] for r in _mor(text, "LTYPE")],
        "block": [
            {
                "ner": r[0],
                "entity": _too(r[1]),
                "orsonoo": _too(r[2]),
                "urgun": _bod(r[3]) if len(r) > 3 else 0.0,
                "undur": _bod(r[4]) if len(r) > 4 else 0.0,
                "x0": _bod(r[5]) if len(r) > 5 else 0.0,
                "y0": _bod(r[6]) if len(r) > 6 else 0.0,
                "att": atts.get(r[0], []),
            }
            for r in _mor(text, "BLOCK")
            if len(r) >= 3
        ],
    }


# --------------------------------------------------------------------------
# Танай давхаргыг бидний үүрэгт таах
# --------------------------------------------------------------------------

# Түлхүүр үг → үүрэг. Үүрэг бүрт эхний тохирсон давхарга сонгогдоно.
# Монгол галиг (VNDSEN, NARIIN, HEMJEE, TENHLEG), орос, англи гурвууланг барина.
TAALT: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ХЭМЖЭЭС", ("hemjee", "hemj", "хэмж", "dim", "размер")),
    ("БИЧИГ", ("text", "бич", "текст", "надпис", "annot", "shrift")),
    ("ТЭНХЛЭГ", ("tenhleg", "тэнхл", "axis", "center", "ось")),
    ("ГАЗАР", ("ground", "grnd", "газ", "gazar", "земл", "хөрс", "hatch")),
    ("ХҮРЭЭ", ("frame", "хүр", "рамк", "штамп", "stamp", "border", "titl", "table")),
    ("ТУЛГУУР-ОТТЯЖКА", ("оття", "guy", "tatlaga", "тат", "dashed")),
    ("ТУЛГУУР-ТРОСОСТОЙК", ("тросостойк", "trosostoyk")),
    ("ТУЛГУУР-ТРАВЕРС", ("травер", "traver", "консол")),
    ("ТУЛГУУР-СҮЛЖЭЭ", ("nariin", "нарийн", "сүлж", "решет", "раскос", "brace", "thin")),
    ("ТУЛГУУР-БИЕ", ("vndsen", "үндсэн", "undsen", "опор", "tulguur", "tower", "стойк", "main")),
)


def ger_buli(clayer: str) -> str:
    """Ажлын давхаргаас стандартын БҮЛИЙН угтварыг таана ("S-0-2-NARIIN" -> "S-0-").

    Нэг зурагт олон эх сурвалжийн давхарга холилдсон байдаг (PDF-ээс импортлосон,
    гуравдагч этгээдийн блокоос орж ирсэн). Тэдгээрийн дунд ажлын стандартыг
    ялгах хамгийн найдвартай тэмдэг нь зохиогчийн сүүлд ажилласан давхарга.
    """
    heseg = clayer.split("-")
    return "-".join(heseg[:2]) + "-" if len(heseg) >= 3 else ""


def taah(davharga: list[dict], clayer: str = "") -> dict[str, str]:
    """Танай давхаргын нэрсээс бидний үүрэг бүрт таарахыг нь сонгоно.

    Таамаг л гаргана — `zagvar.json`-г нээж гараар засах нь хэвийн зүйл.
    Эрэмбэ: (1) ажлын бүлийн угтвартай, (2) entity-тэй, (3) олон entity-тэй.
    Ингэснээр импортлосон хог давхарга ("hemjees", "dim") жинхэнэ стандартыг
    ("S-0-5-HEMJEE") дарахгүй.
    """
    ugtvar = ger_buli(clayer).casefold()
    ner = sorted(
        davharga,
        key=lambda d: (
            not (ugtvar and d["ner"].casefold().startswith(ugtvar)),
            d["too"] == 0,
            -d["too"],
        ),
    )
    holbolt: dict[str, str] = {}
    for uureg, tulhuur in TAALT:
        for d in ner:
            nm = d["ner"].casefold()
            if any(t.casefold() in nm for t in tulhuur):
                holbolt[uureg] = d["ner"]
                break
    # Металл хийцийн үлдсэн хэсэг (траверс, тросостойк) нь тусдаа давхаргатай
    # байх шаардлагагүй — тэдгээр нь биеийн ижил үндсэн шугам.
    bie = holbolt.get("ТУЛГУУР-БИЕ", "")
    if bie:
        for uureg in ("ТУЛГУУР-ТРАВЕРС", "ТУЛГУУР-ТРОСОСТОЙК"):
            holbolt.setdefault(uureg, bie)
    return holbolt


def bichgiin_hev(medee: dict) -> str:
    """Ашиглах бичгийн хэвийг сонгоно.

    Хамгийн найдвартай нь зохиогчийн ИДЭВХТЭЙ хэв (TEXTSTYLE) — тэр нь тухайн
    зурагт бодитоор ажилладаг, кирилл гардаг нь батлагдсан. Байхгүй бол
    GOST/ISOCPEUR фонттой хэв рүү шилжинэ.
    """
    hev = medee.get("hev") or []
    if not hev:
        return "Standard"
    idevhtei = (medee.get("textstyle") or "").strip()
    if idevhtei and any(h["ner"].casefold() == idevhtei.casefold() for h in hev):
        return idevhtei
    for tulhuur in ("gost", "isocpeu", "iso", "arial"):
        for h in hev:
            if tulhuur in (h.get("font") or "").casefold():
                return h["ner"]
    return hev[0]["ner"]


#: АЗ хуудасны нэрлэсэн хэмжээ, мм. Хүрээний блокийг үүгээр таана.
TSAAS_HEMJEE: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}


def huree_taah(block: list[dict], tsaas: str = "A3") -> str:
    """Цаасны хүрээний блокийг ХЭМЖЭЭГЭЭР нь таана.

    Нэрээр таах найдваргүй — нэг зурагт "...A3" гэсэн хэд хэдэн блок
    байж болно; харин 420x297 гэсэн хэмжээ эргэлзээ төрүүлэхгүй.
    """
    hus_u, hus_o = TSAAS_HEMJEE.get(tsaas, TSAAS_HEMJEE["A3"])
    nert = [
        b for b in block
        if abs(b.get("urgun", 0.0) - hus_u) <= 2.0 and abs(b.get("undur", 0.0) - hus_o) <= 2.0
    ]
    if not nert:
        return ""
    # Эх цэг нь зүүн доод буланд байгаа нь тавихад хамгийн энгийн.
    nert.sort(key=lambda b: (abs(b.get("x0", 0.0)) + abs(b.get("y0", 0.0)), -b["orsonoo"]))
    return nert[0]["ner"]


#: Булангийн хүснэгтийн боломжит хэмжээ, мм (ГОСТ 2.104 маягийн штамп).
SHTAMP_URGUN_HYAZGAAR = (120.0, 260.0)
SHTAMP_UNDUR_HYAZGAAR = (20.0, 80.0)


def shtamp_taah(block: list[dict]) -> dict:
    """Булангийн хүснэгтийг таана: атрибуттай + штампын хэмжээтэй + хамгийн олон
    удаа зурагт орсон нь.

    Атрибутын ТООГООР эрэмбэлж болохгүй: "Revision Block" гэх мэт өөрчлөлтийн
    хүснэгт 70 атрибуттай байж, 12 атрибуттай жинхэнэ штампыг дардаг. Харин
    штамп бол хуудас бүрт ордог тул орсон тоо нь хамгийн найдвартай тэмдэг.
    """
    ua, ub = SHTAMP_URGUN_HYAZGAAR
    oa, ob = SHTAMP_UNDUR_HYAZGAAR
    nert = [
        b for b in block
        if b.get("att") and ua <= b.get("urgun", 0.0) <= ub and oa <= b.get("undur", 0.0) <= ob
    ]
    if not nert:
        nert = [b for b in block if b.get("att")]
    if not nert:
        return {}
    nert.sort(key=lambda b: (-b["orsonoo"], -len(b["att"])))
    b = nert[0]
    return {
        "ner": b["ner"],
        "urgun": b.get("urgun", 0.0),
        "undur": b.get("undur", 0.0),
        "x0": b.get("x0", 0.0),
        "y0": b.get("y0", 0.0),
        "att": [[a["tag"], a["x"], a["y"], a["h"]] for a in b["att"]],
    }


def holboh(dwg: Path, out: Path = ZAGVAR) -> dict:
    """DWG-ийг уншаад `zagvar.json` бичнэ — давхаргын холбоос, бичгийн хэв."""
    medee = unshih(dwg)
    tanisan = taah(medee["davharga"], medee.get("clayer", ""))
    zagvar = {
        "_тайлбар": (
            "Бидний дотоод үүрэг → танай давхаргын нэр. Гараар засаж болно. "
            "Хоосон үлдээвэл тухайн үүрэг '0' давхаргад орно. "
            "Энэ файл байгаа үед zurag.py танай давхарга, бичгийн хэвийг ашиглана."
        ),
        "esh": str(dwg),
        "uram": "",
        "bichgiin_hev": bichgiin_hev(medee),
        "huree_block": huree_taah(medee["block"]),
        "shtamp": shtamp_taah(medee["block"]),
        "hunii_ner": {"inzhener": "", "zursan": "", "shalgasan": ""},
        "holbolt": {u: tanisan.get(u, "") for u in UUREG},
        "tailbar": dict(UUREG),
        "songoh_bolomj": {
            "davharga": [d["ner"] for d in sorted(medee["davharga"], key=lambda x: -x["too"])],
            "hev": [h["ner"] for h in medee["hev"]],
            "block": [b["ner"] for b in sorted(medee["block"], key=lambda x: -x["orsonoo"])],
        },
    }
    out.write_text(json.dumps(zagvar, ensure_ascii=False, indent=1), encoding="utf-8")
    return zagvar


def hevleh(medee: dict) -> None:
    """Уншсан мэдээллийг хүн уншихаар хэвлэнэ."""
    units = {"0": "тодорхойгүй", "1": "инч", "4": "мм", "5": "см", "6": "м"}
    print(f"\n{'=' * 74}")
    print(f"{Path(medee['esh']).name}")
    print(f"{'=' * 74}")
    print(f"  нэгж={units.get(medee['insunits'], medee['insunits'])}  "
          f"DIMSCALE={medee['dimscale']}  LTSCALE={medee['ltscale']}  "
          f"идэвхтэй хэв={medee['textstyle']}")

    ashigtai = [d for d in medee["davharga"] if d["too"] > 0]
    print(f"\n  ДАВХАРГА: {len(medee['davharga'])} (entity-тэй нь {len(ashigtai)})")
    for d in sorted(ashigtai, key=lambda x: -x["too"])[:30]:
        print(f"    {d['ner']:<34} өнгө={d['ongo']:>4}  {d['ltype']:<14} {d['too']:>7} entity")
    if len(ashigtai) > 30:
        print(f"    ... бас {len(ashigtai) - 30}")

    print(f"\n  БИЧГИЙН ХЭВ: {len(medee['hev'])}")
    for h in medee["hev"]:
        print(f"    {h['ner']:<24} фонт={h['font']:<20} big={h['bigfont']:<14} "
              f"өргөн={h['urgun']}")

    orson = [b for b in medee["block"] if b["orsonoo"] > 0]
    print(f"\n  БЛОК: {len(medee['block'])} (зурагт орсон нь {len(orson)})")
    for b in sorted(orson, key=lambda x: -x["orsonoo"])[:20]:
        print(f"    {b['ner']:<40} {b['entity']:>5} entity  x{b['orsonoo']}")
    if len(orson) > 20:
        print(f"    ... бас {len(orson) - 20}")

    print(f"\n  ХЭМЖЭЭСИЙН ХЭВ: {', '.join(medee['dimhev'][:12])}")


def uram(dwg: Path, out: Path) -> Path:
    """Танай зургийн ХУУЛБАРААС цэвэр үрлэг (seed) DWG бэлдэнэ.

    Model space-ийн бүх entity устана; давхарга, бичгийн хэв, блокийн
    тодорхойлолт, хэмжээсийн хэв ҮЛДЭНЭ. Үүнийг accoreconsole-д загвар болгож
    өгвөл бидний зураг танай стандарт дээр шууд баригдана.

    PURGE ХИЙХГҮЙ: purge нь ашиглагдаагүй блокийг устгачихна — харин бидэнд
    яг тэдгээр (штамп, тэмдэглэгээ) хэрэгтэй.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(dwg.read_bytes())
    forms = [
        '(setvar "CMDECHO" 0)',
        '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
        DRAIN,
        # Царцсан давхарга дээрх entity устдаггүй тул эхлээд бүгдийг гаргана.
        '(command "_.-LAYER" "_T" "*" "_ON" "*" "_U" "*" "")',
        DRAIN,
        '(setq ss (ssget "_X"))',
        f'(PR (strcat "BAIGAA{SEP}" (if ss (itoa (sslength ss)) "0")))',
        '(if ss (command "_.ERASE" ss ""))',
        DRAIN,
        '(setq ss2 (ssget "_X"))',
        f'(PR (strcat "ULDSEN{SEP}" (if ss2 (itoa (sslength ss2)) "0")))',
        f'(command "_.SAVEAS" "2018" "{out.as_posix()}")',
        DRAIN,
        '(PR "DONE")',
        "(princ)",
    ]
    text = _ajilluulah(out, forms)
    if "@@@DONE" not in text:
        msg = "Үрлэг зураг бэлдэж чадсангүй — AutoCAD дуусгасангүй"
        raise RuntimeError(msg)
    print(f"  устгасан entity: {_neg(text, 'BAIGAA')}  үлдсэн: {_neg(text, 'ULDSEN')}")
    return out


def main(argv: list[str]) -> int:
    """`унших | holboh | uram <файл.dwg>`."""
    if argv and argv[0] in ("-h", "--help", "help", "тусламж"):
        print(__doc__)
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    tushaal, zam = argv[0], Path(argv[1])
    if not zam.is_file():
        print(f"файл олдсонгүй: {zam}")
        return 1

    if tushaal in ("унших", "unshih", "read"):
        hevleh(unshih(zam))
        return 0
    if tushaal in ("holboh", "холбох", "map"):
        z = holboh(zam)
        print(f"{ZAGVAR} бичигдлээ")
        print(f"  бичгийн хэв: {z['bichgiin_hev']}")
        print(f"  хүрээний блок: {z['huree_block'] or '(олдсонгүй)'}")
        sh = z["shtamp"]
        if sh:
            print(f"  булангийн хүснэгт: {sh['ner']}  "
                  f"{sh['urgun']:.1f}x{sh['undur']:.1f} мм, {len(sh['att'])} атрибут")
        print("  хүний нэр: zagvar.json-ы 'hunii_ner'-т бичнэ үү")
        for uureg, ner in z["holbolt"].items():
            temdeg = "  " if ner else "! "
            print(f"  {temdeg}{uureg:<22} -> {ner or '(олдсонгүй, гараар бичнэ үү)'}")
        return 0
    if tushaal in ("uram", "үрлэг", "seed"):
        gar = HERE / "uram" / "zagvar-uram.dwg"
        print(f"үрлэг бэлдэж байна -> {gar}")
        uram(zam, gar)
        return 0

    print(f"үл мэдэгдэх тушаал: {tushaal}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
