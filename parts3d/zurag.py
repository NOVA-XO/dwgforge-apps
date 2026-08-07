r"""DWG -> PNG урьдчилсан харагдац, AutoCAD-ын өөрийнх нь плоттероор.

Гуравдагч этгээдийн рендер хэрэглэхгүй: "PublishToWeb PNG.pc3" нь AutoCAD-тай
хамт ирдэг растер плоттер бөгөөд далд шугамыг арилгасан цэвэр дүрс гаргадаг.
Ингэснээр урьдчилсан харагдац нь ЯГ тэр солидоос гардаг.

-PLOT командын дараалал нь эмзэг. Растер плоттерт "цаасны нэгж" гэсэн асуулт
БАЙХГҮЙ (пиксел нь нэгжгүй) — тэнд "_M" өгвөл чиглэлийн хариулт болж уншигдаад
команд тасарна. Цаасны хэмжээг ч нэрээр өгөхгүй, өгөгдмөлийг нь авна.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dwgforge.backends import find_accoreconsole

DRAIN = (
    '(setq _d 0) (while (and (/= (getvar "CMDNAMES") "") (< _d 30)) (command "") (setq _d (1+ _d)))'
)

# -VIEW-ийн танидаг нэрс.
VIEWS = {
    "swiso": "_SWISO",
    "seiso": "_SEISO",
    "neiso": "_NEISO",
    "nwiso": "_NWISO",
    "top": "_TOP",
    "front": "_FRONT",
    "right": "_RIGHT",
}


def render(dwg: Path, out_png: Path, view: str = "swiso", shade: str = "_H") -> Path | None:
    """DWG-г PNG болгоно. Амжилтгүй бол None.

    ``shade``: "_H" далд шугам арилгасан, "_W" утсан загвар, "_R" рендер.
    """
    exe = find_accoreconsole()
    if exe is None or not dwg.is_file():
        return None
    out_png.parent.mkdir(parents=True, exist_ok=True)
    for old in out_png.parent.glob(out_png.stem + "*.png"):
        old.unlink()

    forms = [
        '(setvar "CMDECHO" 0)',
        '(setvar "FILEDIA" 0)',
        '(setvar "BACKGROUNDPLOT" 0)',
        '(setvar "DISPSILH" 1)',
        '(setvar "ISOLINES" 16)',
        '(defun PR (s) (princ (strcat "\\n@@@" s)) (princ))',
        f'(command "_.-VIEW" "{VIEWS.get(view, "_SWISO")}")',
        DRAIN,
        '(command "_.ZOOM" "_E")',
        DRAIN,
        '(command "_.ZOOM" "0.9x")',
        DRAIN,
        '(command "_.-PLOT"',
        '  "_Y"',  # Detailed plot configuration?
        '  ""',  # Layout <Model>
        '  "PublishToWeb PNG.pc3"',  # Output device
        '  ""',  # Paper size — өгөгдмөл (Sun Hi-Res 1600x1280)
        # Растер плоттерт НЭГЖИЙН асуулт байхгүй. Энд "_M" өгвөл түүнийг
        # чиглэлийн хариулт гэж уншаад бүх дараалал нурна.
        '  "_L"',  # Landscape
        '  "_N"',  # Plot upside down?
        '  "_E"',  # Plot area: Extents
        '  "_F"',  # Scale: Fit
        '  "_C"',  # Offset: Center
        '  "_Y"',  # Plot with plot styles?
        '  "monochrome.ctb"',  # Plot style table
        '  "_Y"',  # Plot with lineweights?
        f'  "{shade}"',  # Shade plot
        f'  "{out_png.as_posix()}"',  # Output file
        '  "_N"',  # Save changes to page setup?
        '  "_Y"',  # Proceed?
        ")",
        DRAIN,
        '(PR "DONE")',
        "(princ)",
    ]
    scr = out_png.with_suffix(".scr")
    scr.write_bytes(b"\xef\xbb\xbf" + ("\r\n".join(forms) + "\r\n").encode("utf-8"))
    proc = subprocess.run(
        [str(exe), "/i", str(dwg), "/s", str(scr), "/l", "en-US"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=600,
        check=False,
        cwd=str(out_png.parent),
    )
    text = (proc.stdout + proc.stderr).decode("utf-16-le", errors="replace")
    scr.unlink(missing_ok=True)

    # Плоттер нэрийг өөрчилж бичиж болно (жишээ нь "plan-1.png") тул хайна.
    made = sorted(out_png.parent.glob(out_png.stem + "*.png"))
    if not made:
        (out_png.with_suffix(".log")).write_text(text, encoding="utf-8")
        return None
    if made[0] != out_png:
        made[0].replace(out_png)
    return out_png


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        raise SystemExit(2)
    src = Path(args[0]).resolve()
    view = args[1] if len(args) > 1 else "swiso"
    png = src.parent / ".preview" / f"{src.stem}-{view}.png"
    got = render(src, png, view=view)
    if got is None:
        print(f"амжилтгүй — {png.with_suffix('.log')} харна уу")
        raise SystemExit(1)
    print(f"OK  {got}  ({got.stat().st_size:,} byte)")
