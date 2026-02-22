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
from textual.message import Message
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import (
    Button,
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
from textual_fspicker import FileOpen
from textual_image.widget import AutoImage
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


# Creating a textual message to notify when
# a file has been modified.
class FileModified(Message):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__()


# Create a Watchdog event handler that sends
# Textual messages when a file modied event is recieved.
class TexualFileSystemEventHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_modified(self, event):
        self.app.post_message(FileModified(event.src_path))


class SaveScreen(Screen):
    DEFAULT_CSS = """
Horizontal {
align: right top;
}
"""

    def compose(self):
        with VerticalGroup():
            yield Label("Name")
            yield Input(id="name")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("OK", id="ok")

    def on_button_pressed(self, event):
        if event.button.id == "ok":
            name = self.query_one("#name").value
            script_file = pathlib.Path(name)

            self.app.get_active_tab().set_files(script_file)

        self.app.pop_screen()


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
        with Collapsible(title="Command"):
            yield TextArea.code_editor(text="", id="cmd-window")

        with Horizontal():
            with Vertical():
                yield Label("Script")
                yield TextArea.code_editor(id="script-window")
                with VerticalGroup():
                    yield Static(f"Scratch Directory: {self.scratch_dir}")
                    yield Static(
                        f"Current Working Directory: {pathlib.Path('.').absolute()}"
                    )
                with VerticalGroup():
                    yield Label(
                        "Script File",
                    )
                    yield Input(id="script-file-input")
                with VerticalGroup():
                    yield Label(
                        "Graphic File",
                    )
                    yield Input(id="graphic-file-input")
                with VerticalGroup():
                    yield Label(
                        "Command File",
                    )
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
        self.query_one("#script-window").text = self.script_text
        self.query_one("#script-file-input").value = str(self.script_file)
        self.query_one("#graphic-file-input").value = str(self.graphic_file)
        self.query_one("#cmd-file-input").value = str(self.cmd_file)
        self.query_one(
            "#script-file-input"
        ).tooltip = "Name of the file that the script will be written to. By default, the script will be written to a temporary directory, but this can be changed to load and save from a different location."
        self.query_one(
            "#graphic-file-input"
        ).tooltip = "Name of the image file that will be generated."
        self.query_one(
            "#cmd-file-input"
        ).tooltip = "Name of the command script (the script that generates the image file from the script file) that will be written and excecuted to process the script and generate the image file."

        self.query_one(
            "#cmd-window"
        ).tooltip = "This script is used to process the input script and produce the graphic file. It will be passed two arguments. The first argument is the name of the input script, eview writes and updates then file as the user edits the script. The second argument is the name of the graphic file that should be generated."
        self.query_one(
            "#script-window"
        ).tooltip = "Edit the input script here. This script will be saved and processed to generate the graphic file."

        self._script_file_change_handler = TexualFileSystemEventHandler(self)
        self._script_file_observer = Observer()
        self._script_file_observer.start()
        self._script_file_write = True

    def on_unmount(self):
        self._script_file_observer.stop()
        self._script_file_observer.join()

    def on_show(self):
        self._debounce_timer._start()

    def on_file_modified(self, message: FileModified):
        if message.path == str(self.script_file.absolute()):
            self._script_file_write = False
            self._load_script_text()

    @on(Input.Blurred, "#script-file-input")
    @on(Input.Submitted, "#script-file-input")
    def _set_script_file(self, event):
        self.set_script_file(event.input.value)

    @on(Input.Blurred, "#cmd-file-input")
    @on(Input.Submitted, "#cmd-file-input")
    def _set_cmd_file(self, event):
        self.set_cmd_file(event.input.value)

    @on(Input.Blurred, "#graphic-file-input")
    @on(Input.Submitted, "#graphic-file-input")
    def _set_graphic_file(self, event):
        self.set_graphic_file(event.input.value)

    def _load_script_text(self):
        if self.script_file.exists():
            self.script_text = self.script_file.read_text()
        self.query_one("#script-window").text = self.script_text

    def set_script_file(self, filename):
        self.script_file = pathlib.Path(filename)
        if not self.script_file.exists():
            self.script_file.write_text(self.script_text)
        else:
            self.script_text = self.script_file.read_text()
        self.query_one("#script-window").text = self.script_text
        self.query_one("#script-file-input").value = str(self.script_file)
        self._debounce_timer.reset()

        self._script_file_observer.schedule(
            self._script_file_change_handler, self.script_file.parent
        )

    def set_cmd_file(self, filename):
        self.cmd_file = pathlib.Path(filename)
        if not self.cmd_file.exists():
            self.cmd_file.write_text(self.cmd_text)
        else:
            self.cmd_text = self.cmd_file.read_text()
        self.query_one("#cmd-window").text = self.cmd_text
        self.query_one("#cmd-file-input").value = str(self.cmd_file)
        self._debounce_timer.reset()

    def set_graphic_file(self, filename):
        self.graphic_file = pathlib.Path(filename)
        self.query_one("#graphic-file-input").value = str(self.graphic_file)
        self._debounce_timer.reset()

    def set_files(self, script_filename):
        script_file = pathlib.Path(script_filename)
        cmd_file = script_file.with_suffix(".run")
        graphic_file = script_file.with_suffix(".png")

        self.set_script_file(script_file)
        self.set_cmd_file(cmd_file)
        self.set_graphic_file(graphic_file)

    def set_graphic(self, file):
        self.query_one("#graphic-window").image = file

    @on(TextArea.Changed, "#script-window")
    @on(TextArea.Changed, "#cmd-window")
    def reset_debounce_timer(self, event):
        self._debounce_timer.reset()

    @work()
    async def generate_graphic(self):
        self._debounce_timer.pause()

        self.script_text = self.query_one("#script-window").text
        if self.script_text == "":
            return

        self.cmd_text = self.query_one("#cmd-window").text

        self.cmd_file.write_text(self.cmd_text)
        os.chmod(self.cmd_file, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
        if self._script_file_write:
            self.script_file.write_text(self.script_text)
        self._script_file_write = True
        self.set_graphic(None)
        self.query_one("#output-window").text = "Running..."
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.cmd_file.absolute()),
                str(self.script_file),
                str(self.graphic_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await proc.communicate()
            self.query_one("#output-window").text = stdout.decode()
        except subprocess.CalledProcessError as e:
            self.query_one("#output-window").text = "Failed!" + "\n\n" + str(e)
            pass
        except Exception as e:
            self.query_one("#output-window").text = "Failed!" + "\n\n" + str(e)
            return

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

    class typst:
        cmd = r"""#! /bin/bash
TMPFILE=__eview_typst_tmp.png
typst compile --ppi 300 --format png "${1}" "${TMPFILE}"
convert -trim -border 5 -density 150x150 "${TMPFILE}" "${2}"
rm "${TMPFILE}"
"""
        script = r"""
y = mx + b
"""

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

    class python:
        class matplotlib:
            cmd = r"""#! /usr/bin/env python
#! /usr/bin/env -S uv --script
import matplotlib.pyplot as plt
import sys, pathlib
SCRIPT_FILE = sys.argv[1]
GRAPHIC_FILE = sys.argv[2]

exec(pathlib.Path(SCRIPT_FILE).read_text())

plt.savefig(GRAPHIC_FILE)
"""
            script = r"""
plt.plot([0, 1, 2, 3], [0, 1, 4, 9])
plt.xlabel("X-axis")
plt.ylabel("Y-axis")
plt.title("Sample Plot")

"""


class EviewApp(App):
    BINDINGS = [
        ("s", "save", "Save"),
        ("o", "open", "Open"),
    ]

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
            with TabPane("python", id="python-tab"):
                with TabbedContent(id="python-tab-group") as tc:
                    with AppTab(
                        "matplotlib",
                        Viewers.python.matplotlib.cmd,
                        Viewers.python.matplotlib.script,
                        id="python-matplotlib-tab",
                    ):
                        pass
            with AppTab(
                "typst",
                Viewers.typst.cmd,
                Viewers.typst.script,
                id="typst-tab",
            ):
                pass
            with AppTab(
                "custom",
                Viewers.custom.cmd,
                Viewers.custom.script,
                id="custom-tab",
            ):
                pass
        yield Footer()

    def on_mount(self):
        if self.filename is not None:
            if self.filename.suffix in [".gp", ".gnuplot"]:
                active_tab = "gnuplot-tab"
                self.query_one("#main-tab-group").active = active_tab

            if self.filename.suffix in [".tex"]:
                active_tab = "tex2im-math-tab"
                self.query_one("#main-tab-group").active = "tex2im-tab"
                self.query_one("#tex2im-tab-group").active = active_tab

            if self.filename.suffix in [".typ"]:
                active_tab = "typst-tab"
                self.query_one("#main-tab-group").active = active_tab

            active_tab = self.query_one(f"#{active_tab}")
            active_tab.set_files(self.filename)

    def action_save(self):
        self.push_screen(SaveScreen())

    def get_active_tab(self):
        for tab in self.query(AppTab):
            tg_id = tab.parent.parent.id
            if self.query_one(f"#{tg_id}").active == tab.id:
                return tab

    @work()
    async def action_open(self):
        result = await self.push_screen_wait(FileOpen())
        self.get_active_tab().set_files(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="eview",
        description="Edit scripts for generating graphics and see the results in real-time.",
    )
    parser.add_argument("filename", nargs="?")

    args = parser.parse_args()

    app = EviewApp(args.filename)
    app.run()
