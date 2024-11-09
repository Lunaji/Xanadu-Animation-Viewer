import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtUiTools import QUiLoader
from PySide6.QtScxml import QScxmlStateMachine
from PySide6.QtGui import QIcon
from xanviewer.animation_viewer import AnimationViewer


def main():
    parser = argparse.ArgumentParser(description="Xanadu Viewer")
    parser.add_argument("file", nargs="?", help="File to open")
    args, qt_args = parser.parse_known_args()

    script_dir = Path(__file__).resolve().parent

    loader = QUiLoader()
    app = QApplication(qt_args)
    app.setWindowIcon(QIcon(str(script_dir / "assets/xanadu_icon.png")))

    ui = loader.load(script_dir / "form.ui")
    state_machine = QScxmlStateMachine.fromFile(
        str(script_dir / "animation_state_machine.scxml")
    )

    viewer = AnimationViewer(ui, state_machine)
    viewer.ui.show()
    if args.file is not None:
        viewer.loadFile(args.file)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
