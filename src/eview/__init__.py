import argparse
import asyncio
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile

from textual import log, on, work
from textual.app import App
from textual.containers import (
    Container,
    Horizontal,
    HorizontalGroup,
    ScrollableContainer,
    Vertical,
    VerticalGroup,
)
from textual.timer import Timer
from textual.widgets import (
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual_image.widget import AutoImage


class AppTab(TabPane):
    DEFAULT_CSS = """
AppTab {
AutoImage {
height: auto; 
width: auto; 
}
}

"""

    def __init__(self, title, cmd_text, script_text, id):
        super().__init__(title, id=id)
        self.scratch_dir = pathlib.Path(tempfile.mkdtemp())
        self.cmd_file = self.scratch_dir / "run"
        self.script_file = self.scratch_dir / "in.txt"
        self.graphic_file = self.scratch_dir / "out.png"

        self.cmd_text = cmd_text
        self.script_text = script_text

    def __del__(self):
        if self.scratch_dir.exists():
            shutil.rmtree(self.scratch_dir)

    def compose(self):
        self._debounce_time = 0.5
        self._debounce_timer: Timer | None = None
        with Collapsible(title="Cmd"):
            yield TextArea.code_editor(text="", id="cmd-window")

        with Horizontal():
            with Vertical():
                yield Label("Script")
                yield TextArea.code_editor(id="input-window")
                with VerticalGroup():
                    yield Label("Scatch Folder")
                    yield Static(str(self.scratch_dir))
                with VerticalGroup():
                    yield Label("Input File")
                    yield Input(id="input-file-input")
                with VerticalGroup():
                    yield Label("Output File")
                    yield Input(id="output-file-input")
                with VerticalGroup():
                    yield Label("Cmd File")
                    yield Input(id="cmd-file-input")
            with VerticalGroup():
                yield Label("Graphic")
                yield AutoImage(id="graphic-window")
                yield Label("Output")
                yield TextArea(id="output-window")

    def on_mount(self):
        self._debounce_timer = Timer(
            self, self._debounce_time, callback=self.generate_graphic
        )

        self.query_one("#cmd-window").text = self.cmd_text
        self.query_one("#input-window").text = self.script_text
        self.query_one("#input-file-input").value = str(self.script_file)
        self.query_one("#output-file-input").value = str(self.graphic_file)
        self.query_one("#cmd-file-input").value = str(self.cmd_file)

    def on_show(self):
        self._debounce_timer._start()

    @on(Input.Blurred, "#input-file-input")
    @on(Input.Submitted, "#input-file-input")
    def _set_input_file(self, event):
        self.set_input_file(event.input.value)

    @on(Input.Blurred, "#cmd-file-input")
    @on(Input.Submitted, "#cmd-file-input")
    def _set_cmd_file(self, event):
        self.set_cmd_file(event.input.value)

    @on(Input.Blurred, "#output-file-input")
    @on(Input.Submitted, "#output-file-input")
    def _set_output_file(self, event):
        self.set_output_file(event.input.value)

    def set_input_file(self, filename):
        self.script_file = pathlib.Path(filename)
        if not self.script_file.exists():
            self.script_file.write_text(self.script_text)
        else:
            self.script_text = self.script_file.read_text()
        self.query_one("#input-window").text = self.script_text
        self.query_one("#input-file-input").value = str(self.script_file)
        self._debounce_timer.reset()

    def set_cmd_file(self, filename):
        self.cmd_file = pathlib.Path(filename)
        if not self.cmd_file.exists():
            self.cmd_file.write_text(self.cmd_text)
        else:
            self.cmd_text = self.cmd_file.read_text()
        self.query_one("#cmd-window").text = self.cmd_text
        self.query_one("#cmd-file-input").value = str(self.cmd_file)
        self._debounce_timer.reset()

    def set_output_file(self, filename):
        self.graphic_file = pathlib.Path(filename)
        self.query_one("#output-file-input").value = str(self.graphic_file)
        self._debounce_timer.reset()

    def set_graphic(self, file):
        self.query_one("#graphic-window").image = file

    @on(TextArea.Changed, "#input-window")
    @on(TextArea.Changed, "#cmd-window")
    def reset_debounce_timer(self, event):
        self._debounce_timer.reset()

    @work()
    async def generate_graphic(self):
        self._debounce_timer.pause()
        self.script_text = self.query_one("#input-window").text
        if self.script_text == "":
            return

        self.cmd_text = self.query_one("#cmd-window").text

        self.cmd_file.write_text(self.cmd_text)
        os.chmod(self.cmd_file, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
        self.script_file.write_text(self.script_text)
        self.set_graphic(None)
        self.query_one("#output-window").text = "Running..."
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cmd_file,
                self.script_file,
                self.graphic_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            self.query_one("#output-window").text = stdout.decode()
        except subprocess.CalledProcessError:
            self.query_one("#output-window").text = "Failed!"
            pass

        if (
            proc.returncode == 0
            and self.graphic_file.exists()
            and os.path.getsize(self.graphic_file) > 0
        ):
            try:
                self.query_one("#graphic-window").image = str(self.graphic_file)
            except:
                pass
        else:
            pass


class Viewers:
    class gnuplot:
        cmd = r"""#! /bin/bash

gnuplot -e "set term png; set output '${2}'; load '${1}'"
"""
        script = r"""
plot sin(x)
"""

    class tex2im:
        class math:
            cmd = r"""#! /bin/bash
# some useful options
# -B INT : set border width in pixels
# -n :     don't insert equation environment (for non-math latex images)
# -t :     text color
# -b :     background color
# -z :     transparent background

tex2im "${1}" -o "${2}"
"""
            script = r"""
\div{\vec{E}} = \rho / \epsilon_0
"""

        class tikz:
            cmd = r"""#! /bin/bash
# some useful options
# -B INT : set border width in pixels
# -n :     don't insert equation environment (for non-math latex images)
# -t :     text color
# -b :     background color
# -z :     transparent background

tex2im -n -B 10 "${1}" -o "${2}"
"""

            script = str(r"""
\begin{tikzpicture}
\draw (0,0) -- (1,1)
\end{tikzpicture}
""")

    class custom:
        cmd = r"""#! /bin/bash
SCRIPT_FILE="${1}"
IMAGE_FILE="${2}"
# insert command that will create an image named ${IMAGE_FILE}
bash ${SCRIPT_FILE}
"""
        script = r"""
# Edit command script to process this file and then edit this file.
echo "Hello World!"
"""


class PviewApp(App):
    def __init__(self, filename):
        super().__init__()
        self.filename = pathlib.Path(filename) if filename is not None else None

    def compose(self):
        self._debounce_time = 0.5
        self._debounce_timer: Timer | None = None
        yield Header()
        with TabbedContent(id="main-tab-group"):
            with AppTab(
                "gnuplot", Viewers.gnuplot.cmd, Viewers.gnuplot.script, id="gnuplot-tab"
            ):
                pass
            with TabPane("tex2im", id="tex2im-tab"):
                with TabbedContent(id="tex2im-tab-group") as tc:
                    with AppTab(
                        "math",
                        Viewers.tex2im.math.cmd,
                        Viewers.tex2im.math.script,
                        id="tex2im-math-tab",
                    ):
                        pass
                    with AppTab(
                        "tikz",
                        Viewers.tex2im.tikz.cmd,
                        Viewers.tex2im.tikz.script,
                        id="tex2im-tikz-tab",
                    ):
                        pass
            with AppTab(
                "custom",
                Viewers.custom.cmd,
                Viewers.custom.script,
                id="custom-tab",
            ):
                pass

    def on_mount(self):
        if self.filename is not None:
            if self.filename.suffix in [".gp", ".gnuplot"]:
                self.query_one("#gnuplot-tab").set_input_file(self.filename)
                self.query_one("#main-tab-group").active = "gnuplot-tab"

            if self.filename.suffix in [".tex"]:
                self.query_one("#tex2im-math-tab").set_input_file(self.filename)
                self.query_one("#main-tab-group").active = "tex2im-tab"
                self.query_one("#tex2im-tab-group").active = "tex2im-math-tab"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eview",
        description="Edit scripts for generating graphics and see the results in real-time.",
    )
    parser.add_argument("filename", nargs="?")

    args = parser.parse_args()

    app = PviewApp(args.filename)
    app.run()
