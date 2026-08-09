"""Тестүүд `parts3d`-ийг модуль болгон импортлохын тулд замд нь оруулна.

`parts3d` нь багц биш, файл болж ажилладаг скриптүүдийн хавтас (`gui.py` өөрөө
`sys.path`-даа өөрийн хавтсыг нэмдэг), тиймээс энгийн `import gui` ажиллуулахын
тулд тэр хавтас замд байх ёстой.
"""

from __future__ import annotations

import sys
from pathlib import Path

PARTS3D = Path(__file__).resolve().parent.parent / "parts3d"
if str(PARTS3D) not in sys.path:
    sys.path.insert(0, str(PARTS3D))
