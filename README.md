# parts3d — параметрт 3D эд ангийн сан

`dwgforge` дээр баригдсан хэрэглээний сан. Хоолойн эд ангийг **параметрээр**
3D solid болгож үүсгэж, DWG болгож хадгална. Локал вэб GUI дагалдана.

> **Parametric 3D piping parts, built on `dwgforge`.** Generates real AutoCAD
> 3D solids (not surfaces) with a working bore, and ships a dependency-free
> local web GUI. English notes at the bottom.

---

## Юу үүсгэдэг вэ

| Эд анги | Параметрүүд |
|---|---|
| **Хоолой** `Pipe` | `dn`, `length`, `od`, `wall` |
| **Тохой** `Elbow` | `dn`, `angle`, `bend_radius`, `od`, `wall` |
| **Тройник** `Tee` | `dn`, `branch_dn`, `run_length`, `branch_length` |
| **Шилжилт** `Reducer` | `dn`, `dn_small`, `length` |
| **Фланец** `Flange` | `dn`, `hub_length`, `outer`, `thickness`, `bolt_circle`, `bolt_hole`, `bolt_count` |

Бүгд **дотоод нүхтэй** — эзэлхүүнээр шалгагдсан. DN100 хоолой бүтэн цилиндрээс
5 дахин хөнгөн байх ёстой, тэгж байгааг `parts_shalgah.py` баталдаг.

## Шаардлага

- **AutoCAD 2026 эсвэл Civil 3D 2026** — `accoreconsole.exe` түүнтэй хамт ирдэг.
  Үүнгүйгээр ажиллахгүй.
- Python 3.12
- `dwgforge` (энэ repo)

## Суулгах

```powershell
git clone https://github.com/NOVA-XO/dwgforge.git
cd dwgforge
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m dwgforge doctor     # AutoCAD олдож байгаа эсэх
```

## Ашиглах

### 1. GUI (хамгийн хялбар)

```powershell
.\.venv\Scripts\python.exe parts3d\gui.py
```

Браузер `http://localhost:8765` дээр нээгдэнэ. Эд ангийн таб сонгож, хэмжээсээ
оруулаад **Үүсгэх**. 3–8 секундэд DWG гарна.

Сервер нь зөвхөн `127.0.0.1`-ийг сонсоно — сүлжээнд нээлттэй биш, нэвтрэлт
байхгүй. Хуваалцах бол урьдаар токен нэмэх хэрэгтэй.

### 2. Багцаар

```powershell
.\.venv\Scripts\python.exe parts3d\parts.py
```

`parts.py`-ийн `main()` доторх жагсаалтыг засаж, хүссэн эд ангиа үүсгэнэ.

### 3. Кодоос

```python
import sys

sys.path.insert(0, "parts3d")
from pathlib import Path
from parts import Elbow, emit, run
from partsan import load_table

run(emit([Elbow(dn=150, angle=45.0, bend_radius=300.0)], load_table()), Path("tohoi.dwg"))
```

## Хэмжээсийг засах — гурван түвшин

1. **`hemjees.json`** — DN хүснэгт (гадна диаметр, ханын зузаан, фланецын
   хэмжээс). Энд засвал бүх эд ангид нөлөөлнө.
2. **Дуудахдаа** — `Pipe(dn=100, wall=8.0)` нэг удаагийн дарж бичилт.
3. **GUI дээр** — талбарыг хоосон орхивол хүснэгтээс авна, утга бичвэл дарж бичнэ.

## Үйлдвэрлэгчийн хэмжээс — `local/`

Bray, Alfa Laval зэрэг компаниуд гарын авлагадаа хэмжээсийг дахин түгээхийг
хориглосон заалттай ("shall not be copied ... without express written
permission"). Тиймээс тэдгээрийн хүснэгт **энэ repo-д ОРООГҮЙ** — `parts3d/local/`
хавтаснаас уншина, тэр хавтас нь gitignore хийгдсэн.

`dn` (ASME B36.10 хоолой) ба `flange` (EN 1092-1) нь **нийтлэгдсэн стандарт**
тул `hemjees.json` дотор хэвээр байна.

Буцах хавхлага үүсгэхийн тулд `parts3d/local/bray_check.json`:

```json
{
  "_багана": "[A face-to-face, B бие OD, C, D] мм",
  "50":  [<A>, <B>, <C>, <D>],
  "100": [<A>, <B>, <C>, <D>]
}
```

`A` ба `B`-г үйлдвэрлэгчийн гарын авлагаас авна. `C`, `D` нь заавал биш —
`C` байвал өргөх цагирагийн өндрийг тогтооход ашиглана.

AlfaNova үүсгэгчид `parts3d/local/alfanova400.json` хэрэгтэй; бүтцийг
`alfanova400.py`-ийн эхнээс үзнэ үү. Файл байхгүй бол тодорхой алдаа өгнө.

## Туслах хэрэгслүүд

| Файл | Юу хийдэг |
|---|---|
| `parts_shalgah.py` | Үүсгэсэн эд ангийн эзэлхүүнийг тооцоотой тулгана |
| `dwg_unshih.py` | Байгаа DWG-г задлан шинжилнэ — давхарга, блок, entity, эзэлхүүн |
| `dwg_gunzgii.py` | Блокийн ДОТОРХ геометрийг задалж хэмжинэ (санах ойд, файл хөндөхгүй) |
| `alfanova400.py` | Alfa Laval AlfaNova 400 дулаан солилцуурын параметрт загвар |

## Дизайны шалтгаанууд

Эдгээр нь бүгд бодит туршилтаар тогтоогдсон:

- **`entmake` нь 3D бие үүсгэж чадахгүй.** Хоосон бие буцаадаг — хэмжээсгүй.
  Тиймээс солид үүсгэхэд `(command "_.CYLINDER" ...)` гэх мэт командууд хэрэгтэй.
  Энэ нь dwgforge-ийн "entmake 100%" зарчмаас ялгаатай тул тусдаа сан болсон.
- **`OSMODE 0` заавал.** Объект барих нь цэгийн оролтыг таслан авч, командын
  дараалал алдагдвал бүх геометр чимээгүй эвдэрнэ.
- **Команд бүрийн дараа `CMDNAMES` шалгана.** Асуулт дуусаагүй байхад дараагийн
  мөр орвол түүнийг хариулт гэж уншаад цааш эвдэрнэ.
- **`INSUNITS = 4` (мм).** Загварын өгөгдмөл нь метр — тэгвэл эд анги мм-ийн
  зурагт орохдоо 1000 дахин томорно.
- **Хөнгөн үрлэг зураг.** Civil 3D-ийн загвар 916 KB. `acadiso` (31 KB)-г
  `/i`-гээр өгснөөр эд анги тус бүр 930 KB-аас **35 KB** болсон.

---

## English

`parts3d` generates parametric 3D piping parts as real AutoCAD solids, driven
from Python via `dwgforge`. Requires AutoCAD 2026 / Civil 3D 2026 for
`accoreconsole.exe`.

Run the GUI with `python parts3d/gui.py` (stdlib `http.server`, no extra
dependencies) and open `http://localhost:8765`. Edit `hemjees.json` to change
the DN table, or pass overrides per part.

`entmake` cannot build ACIS solids — it returns a degenerate body with no
extents — so solid modelling here drives the command line instead, with
`OSMODE 0` and a `CMDNAMES` drain after every command. Both were verified
empirically; without them the geometry corrupts silently.