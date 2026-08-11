"""Тестүүд аппуудыг модуль болгон импортлохын тулд замд нь оруулна.

`parts3d`, `tulguur2d` хоёр нь багц биш, файл болж ажилладаг скриптүүдийн
хавтас (файл бүр `sys.path`-даа өөрийн хавтсыг нэмдэг), тиймээс энгийн
`import gui` ажиллуулахын тулд тэр хавтас замд байх ёстой.

ХОЁУЛАНД НЬ `gui.py` БАЙГАА. Тиймээс `parts3d` эхэнд, `tulguur2d` төгсгөлд
ордог: `import gui` нь `parts3d`-ийнхийг олох ёстой. `tulguur2d`-ийн GUI-г
тестлэх бол `importlib`-ээр замаар нь шууд ачаална уу.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PARTS3D = REPO / "parts3d"
TULGUUR2D = REPO / "tulguur2d"

if str(PARTS3D) not in sys.path:
    sys.path.insert(0, str(PARTS3D))
if str(TULGUUR2D) not in sys.path:
    sys.path.append(str(TULGUUR2D))
