import sys
import argparse
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtUiTools import QUiLoader
from PySide6.QtScxml import QScxmlStateMachine
from animation_viewer import AnimationViewer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Xanadu Viewer')
    parser.add_argument('file', nargs='?', help='File to open')
    args, qt_args = parser.parse_known_args()

    loader = QUiLoader()
    app = QApplication(qt_args)

    script_dir = Path(__file__).resolve().parent
    ui = loader.load(script_dir / 'form.ui')
    state_machine = QScxmlStateMachine.fromFile(str(script_dir / 'animation_state_machine.scxml'))

    viewer = AnimationViewer(ui, state_machine)
    if args.file is not None:
        viewer.loadFile(args.file)
    viewer.ui.show()

    sys.exit(app.exec())