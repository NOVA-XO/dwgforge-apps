r"""Блок оруулах (INSERT) entity — dwgforge-ийн entity протоколыг хангана.

`dwgforge` нь LINE, CIRCLE, ARC, LWPOLYLINE, POINT, TEXT, MTEXT долоог мэднэ.
Блок оруулах нь энэ аппын хэрэгцээ (танай штампыг зурагт тавих) тул санг
өөрчлөхгүйгээр энд нэмнэ: `Drawing.add()` нь бүтцийн (structural) протокол
хүлээж авдаг учир `dxf_type`, `layer`, `to_lisp()` гурвыг хангасан ямар ч
объектыг зурагт нэмж болно.

ЗААВАЛ АНХААР: `entmake`-ээр INSERT үүсгэхэд тухайн блок зургийн блокийн
хүснэгтэд БАЙХ ёстой. Тиймээс энэ нь зөвхөн танай зургаас гаргасан үрлэг
(`zagvar.py uram`) дээр ажиллана — тэнд танай блокууд бүгд байгаа.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from dwgforge.entities import (
    assoc_list,
    dxf_int,
    dxf_point,
    dxf_real,
    dxf_str,
    entity_header,
)
from dwgforge.errors import GeometryError
from dwgforge.geometry import Pt, as_pt
from dwgforge.lisp import Node

__all__ = ["Attrib", "Insert", "SeqEnd"]


@dataclass(frozen=True, slots=True)
class Insert:
    """Нэрээр нь блок оруулна (INSERT).

    Атрибут (ATTDEF) бүхий блок орох боловч атрибутын ТЕКСТ гарахгүй: тэр нь
    тусдаа ATTRIB entity + SEQEND шаарддаг. Штампын нүдийг дүүргэх шаардлагатай
    бол текстийг нь тусад нь бичих (`Zurag.bichig`) нь илүү найдвартай.
    """

    ner: str
    at: Pt
    scale: float = 1.0
    rotation: float = 0.0
    layer: str = "0"
    color: int | None = None
    atributtai: bool = False

    dxf_type: ClassVar[str] = "INSERT"

    def __post_init__(self) -> None:
        """Нэр хоосон биш, масштаб эерэг эсэхийг шалгана."""
        object.__setattr__(self, "at", as_pt(self.at))
        if not self.ner or not self.ner.strip():
            msg = "блокийн нэр хоосон байна"
            raise GeometryError(msg)
        if self.scale <= 0.0:
            msg = f"блокийн масштаб эерэг байх ёстой, {self.scale} ирлээ"
            raise GeometryError(msg)

    def to_lisp(self) -> Node:
        """DXF assoc жагсаалт болгож буулгана."""
        groups = entity_header("INSERT", "AcDbBlockReference", self.layer, self.color)
        if self.atributtai:
            # 66=1 нь "энэ INSERT-ийн дараа ATTRIB-ууд, эцэст нь SEQEND ирнэ"
            # гэсэн үг. Тэдгээрийг ДАРААЛЛААР нь нэмэх ёстой — дундуур нь өөр
            # entity орвол AutoCAD хэлхээг таслана.
            groups.append(dxf_int(66, 1))
        groups += [
            dxf_str(2, self.ner, kind="name"),
            dxf_point(10, self.at),
            dxf_real(41, self.scale),
            dxf_real(42, self.scale),
            dxf_real(43, self.scale),
            dxf_real(50, self.rotation),
        ]
        return assoc_list(groups)


@dataclass(frozen=True, slots=True)
class Attrib:
    """Блокийн атрибутын УТГА (ATTRIB) — `Insert(atributtai=True)`-ийн дараа.

    Байрлал нь МОДЕЛЬ координат: блокийн дотоод байрлалыг оруулах цэг,
    масштабтай нь хослуулж өөрөө тооцно.
    """

    tag: str
    value: str
    at: Pt
    height: float = 2.5
    style: str = "Standard"
    rotation: float = 0.0
    layer: str = "0"
    color: int | None = None

    dxf_type: ClassVar[str] = "ATTRIB"

    def __post_init__(self) -> None:
        """Тэмдэг, өндрийг шалгана."""
        object.__setattr__(self, "at", as_pt(self.at))
        if not self.tag.strip():
            msg = "атрибутын tag хоосон байна"
            raise GeometryError(msg)
        if self.height <= 0.0:
            msg = f"атрибутын өндөр эерэг байх ёстой, {self.height} ирлээ"
            raise GeometryError(msg)

    def to_lisp(self) -> Node:
        """DXF assoc жагсаалт: AcDbText -> AcDbAttribute гэсэн дарааллаар."""
        groups = entity_header("ATTRIB", "AcDbText", self.layer, self.color)
        groups += [
            dxf_point(10, self.at),
            dxf_real(40, self.height),
            dxf_str(1, self.value),
            dxf_real(50, self.rotation),
            dxf_str(7, self.style, kind="name"),
            dxf_str(100, "AcDbAttribute", kind="name"),
            dxf_str(2, self.tag, kind="name"),
            dxf_int(70, 0),
        ]
        return assoc_list(groups)


@dataclass(frozen=True, slots=True)
class SeqEnd:
    """ATTRIB-уудын хэлхээг хаана. `Insert(atributtai=True)` бүрт ЗААВАЛ хэрэгтэй."""

    layer: str = "0"

    dxf_type: ClassVar[str] = "SEQEND"

    def to_lisp(self) -> Node:
        """``(list (cons 0 "SEQEND") ...)``."""
        return assoc_list(entity_header("SEQEND", "AcDbEntity", self.layer, None)[:3])
