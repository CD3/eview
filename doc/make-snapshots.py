import time
from pathlib import Path

from textual._doc import take_svg_screenshot

from eview import EviewApp

app = EviewApp(None)
press = []
terminal_size = (160, 50)
run_before = None
screenshot_1 = take_svg_screenshot(
    app=app,
    press=press,
    terminal_size=terminal_size,
    run_before=run_before,
)

Path("screenshot_1.svg").write_text(screenshot_1)
