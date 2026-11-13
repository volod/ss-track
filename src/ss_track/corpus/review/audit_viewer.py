"""Local viewers for packet pictures: an ffplay flipbook and the desktop's folder opener.

They read only the packet's own picture files, named by their offset in the window.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

FLIPBOOK_FPS = 4  # a 16-frame window loops every four seconds
DIFFERENCE_GAIN = 8  # amplifies small frame differences so a distant bird stays visible

Viewer = Callable[[str, list[Path], bool], bool]  # title, pictures in order, differences
Reveal = Callable[[Path], bool]  # opens a folder of pictures


def reveal_folder(folder: Path) -> bool:
    """Open a packet folder in the desktop's viewer without waiting for it."""
    opener = shutil.which("xdg-open") or shutil.which("open")
    if opener is None:
        return False
    subprocess.Popen(
        [opener, str(folder)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def play_flipbook(item_id: str, pictures: list[Path], difference: bool) -> bool:
    """Loop an item's pictures in ffplay until closed; differences show frame-to-frame change."""
    executable = shutil.which("ffplay")
    if executable is None or not pictures:
        return False
    digits = len(pictures[0].stem)
    command = [executable, "-hide_banner", "-loglevel", "error", "-loop", "0"]
    command += ["-window_title", f"{item_id}{' differences' if difference else ''}"]
    command += ["-framerate", str(FLIPBOOK_FPS), "-start_number", "0"]
    command += ["-i", str(pictures[0].parent / f"%0{digits}d.png")]
    if difference:
        gain = f"'min(val*{DIFFERENCE_GAIN}\\,255)'"
        command += ["-vf", f"tblend=all_mode=difference,lutrgb=r={gain}:g={gain}:b={gain}"]
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0
