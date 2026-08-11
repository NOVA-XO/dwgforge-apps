# dwgforge-apps

AutoCAD-тай ажилладаг хэрэглээний програмууд. Бүгд [`dwgforge`](https://github.com/NOVA-XO/dwgforge)
сан дээр баригдана — сан нь Python-оос AutoLISP үүсгэж, `accoreconsole.exe`-ээр
жинхэнэ DWG болгож гүйцэтгэдэг.

> **Applications built on `dwgforge`.** The library is a separate repository and
> a separate release; this one holds the programs that use it.

## Аппууд

| Хавтас | Юу хийдэг |
|---|---|
| [`parts3d/`](parts3d/) | Параметрт 3D хоолойн эд анги (хоолой, тохой, тройник, шилжилт, фланец, буцах хавхлага) + Blender маягийн 3D харагдацтай локал вэб GUI |
| [`tulguur2d/`](tulguur2d/) | ЭСП-ийн 1976 оны каталогийн 371 ЦДАШ-ын тулгуур (ВЛ 35–500 кВ, ган ба төмөр бетон) — 2D эскиз DWG + жагсаалт, тойм хуудас, локал вэб GUI |

## Шаардлага

- **AutoCAD 2026 эсвэл Civil 3D 2026** — `accoreconsole.exe` түүнтэй хамт ирдэг
- Python 3.12+

## Суулгах

```powershell
git clone https://github.com/NOVA-XO/dwgforge-apps.git
cd dwgforge-apps
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Сангийн хараахан гараагүй өөрчлөлт дээр ажиллах бол сангаа дарж бичнэ:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ..\dwgforge
```

Шалгах: `.\.venv\Scripts\python.exe -m dwgforge doctor` — AutoCAD олдож байгаа эсэх.

## Шинэ апп хэрхэн эхлүүлэх вэ

Шинэ хавтас үүсгээд сангийн урд хаалгыг дуудна. Гүйцэтгэлийн давхаргыг
өөрөө бичих шаардлагагүй — `.scr` бичих, UTF-16LE тайлах, мөрийн урт хэмжих,
хаалт тоолох, timeout тавих ажлыг сан хариуцна:

```python
from dwgforge import Drawing, Layer, write_dwg

dwg = Drawing()
dwg.add_layer(Layer("ТЭНХЛЭГ", color=3))
dwg.line((0, 0), (1000, 0), layer="ТЭНХЛЭГ")
print(write_dwg(dwg, "out/plan.dwg").summary())
```

3D биет үүсгэх бол `dwgforge.solids`-ийг ашиглана (`parts3d/parts.py`-г жишээ
болгож харна уу).

**Санд юу байх ёстой, юу энд байх ёстой вэ:** AutoCAD-ын аль ч програмд
хэрэгтэй зүйл (солид үүсгэх, DWG-г PNG/STL болгох, зураг шинжлэх) санд
харьяалагдана. Тухайн салбарын мэдлэг (хоолойн DN хүснэгт, үйлдвэрлэгчийн
каталог, GUI-ийн талбарын нэрс) энд үлдэнэ.

## Үйлдвэрлэгчийн хэмжээс

Bray, Alfa Laval зэрэг компаниуд гарын авлагынхаа хэмжээсийг дахин түгээхийг
хориглосон тул тэдгээр тоо **энэ repo-д ОРООГҮЙ**. `parts3d/local/` хавтас нь
gitignore хийгдсэн; бүтцийг нь [`parts3d/README.md`](parts3d/README.md)
тайлбарласан.
