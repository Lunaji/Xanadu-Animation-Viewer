from PySide6.QtCore import (
    QObject,
    QSettings,
    QFileInfo,
    QTimer,
    QPoint,
    SLOT,
    Slot,
    qDebug,
)
from PySide6.QtGui import QAction
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QListWidgetItem,
)
from PySide6.QtCore import Qt
import numpy as np
from xanlib import load_xbf
from xanviewer.scene_model import SceneModel
from xanviewer.fxdata_parser import parse_animations


def has_vertex_animation_frames(node):
    return node.vertex_animation is not None and node.vertex_animation.frames


def decompose(vertices):
    positions = np.array([v.position for v in vertices])

    norm_scale = 100
    norm_ends = positions + norm_scale * np.array([v.normal for v in vertices])
    normals = np.empty((len(vertices) * 2, 3))
    normals[0::2] = positions
    normals[1::2] = norm_ends

    return positions, normals


def get_mesh(node):
    positions, normals = decompose(node.vertices)
    faces = np.array([face.vertex_indices for face in node.faces])

    mesh = gl.GLMeshItem(
        vertexes=positions,
        faces=faces,
        drawFaces=False,
        drawEdges=True,
    )

    normal_arrows = gl.GLLinePlotItem(
        pos=normals, color=(1, 0, 0, 1), width=2, mode="lines"
    )

    va_mesh = []
    va_normals = []
    if has_vertex_animation_frames(node):
        for frame in node.vertex_animation.frames:
            frame_positions, frame_normals = decompose(frame)

            va_mesh.append(
                gl.GLMeshItem(
                    vertexes=frame_positions,
                    faces=faces,
                    drawFaces=False,
                    drawEdges=True,
                )
            )

            va_normals.append(
                gl.GLLinePlotItem(
                    pos=frame_normals, color=(1, 0, 0, 1), width=2, mode="lines"
                )
            )

    return {
        "mesh": mesh,
        "normals": normal_arrows,
        "vertex animation mesh": va_mesh,
        "vertex animation normals": va_normals,
    }


class AnimationViewer(QObject):
    def __init__(self, ui, state_machine):
        super().__init__()

        self.ui = ui

        self.settings = QSettings("DualNatureStudios", "AnimationViewer")
        self.recent_files = self.settings.value("recentFiles") or []

        self.gl_items = {}

        self.ui.viewer.view = gl.GLViewWidget()
        self.ui.viewer.layout = QVBoxLayout(self.ui.viewer)
        self.ui.viewer.layout.addWidget(self.ui.viewer.view)
        self.ui.viewer.view.setCameraPosition(
            distance=100000, elevation=300, azimuth=90
        )

        self.ui.action_Open.triggered.connect(self.openFile)
        self.updateRecentFilesMenu()

        self.ui.actionToggle_Wireframe.triggered.connect(self.toggle_wireframe)
        self.ui.actionToggle_Normals.triggered.connect(self.toggle_normals)

        self.timer = QTimer(self.ui)
        self.timer.timeout.connect(self.timer_out)
        self.ui.frame_slider.valueChanged.connect(self.update_frame)

        self.ui.fps_box.valueChanged.connect(
            lambda fps: self.timer.setInterval(1000 // fps)
        )

        self.state_machine = state_machine
        self.state_machine.connectToEvent("stop", self, SLOT("stop_animation()"))
        self.state_machine.connectToEvent("enable_play", self, SLOT("on_enable_play()"))
        self.state_machine.connectToEvent("play", self, SLOT("on_play()"))
        self.state_machine.connectToEvent("pause", self, SLOT("on_pause()"))
        self.state_machine.init()
        self.state_machine.start()

        self.ui.play_button.toggled.connect(self.on_play_button_toggled)

        self.ui.animationsList.currentItemChanged.connect(self.on_animation_selected)

        self.ui.nodeList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.nodeList.customContextMenuRequested.connect(self.show_context_menu)
        self.ui.actionCopy.triggered.connect(self.copy_to_clipboard)

    @Slot(QPoint)
    def show_context_menu(self, position):
        index = self.ui.nodeList.indexAt(position)
        if not index.isValid():
            return

        context_menu = QMenu(self.ui.nodeList)
        context_menu.addAction(self.ui.actionCopy)
        context_menu.exec(self.ui.nodeList.viewport().mapToGlobal(position))

    @Slot()
    def copy_to_clipboard(self):
        selected_index = self.ui.nodeList.currentIndex()
        selected_node = selected_index.internalPointer()
        QApplication.clipboard().setText(selected_node.name)

    @Slot(bool)
    def on_play_button_toggled(self, checked):
        if checked:
            self.state_machine.submitEvent("play")
        else:
            self.state_machine.submitEvent("pause")

    @Slot()
    def on_enable_play(self):
        self.ui.play_button.setEnabled(True)

    @Slot()
    def on_play(self):
        self.timer.start(1000 // self.ui.fps_box.value())

    @Slot()
    def on_pause(self):
        self.timer.stop()

    @Slot()
    def stop_animation(self):
        self.ui.play_button.setEnabled(False)
        self.ui.play_button.setChecked(False)
        self.ui.frame_slider.setMaximum(0)

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_animation_selected(self, current, previous):
        self.ui.segmentsList.clear()
        if current is None:
            return
        animation = current.data(Qt.UserRole)
        for segment in animation.segments:
            self.ui.segmentsList.addItem(str(segment))

    def toggle_wireframe(self):
        for mesh in filter(
            lambda item: isinstance(item, gl.GLMeshItem), self.ui.viewer.view.items
        ):
            mesh.opts["drawFaces"] = not mesh.opts["drawFaces"]
        self.ui.viewer.view.update()

    def toggle_normals(self):
        for key in self.gl_items:
            if self.gl_items[key]["mesh"].visible():
                normals = self.gl_items[key]["normals"]
                normals.setVisible(not normals.visible())
            for i, va_mesh in enumerate(self.gl_items[key]["vertex animation mesh"]):
                if va_mesh.visible():
                    normals = self.gl_items[key]["vertex animation normals"][i]
                    normals.setVisible(not normals.visible())

    def hide_all(self):
        for item in self.ui.viewer.view.items:
            item.setVisible(False)

    def on_node_selected(self, selected, deselected):

        if not selected.indexes():
            return

        self.hide_all()

        selected_node = selected.indexes()[0].internalPointer()

        gl_items = self.gl_items.get(selected_node.name)
        if gl_items is not None:
            if has_vertex_animation_frames(selected_node):
                mesh = gl_items["vertex animation mesh"][0]
                normals = gl_items["vertex animation normals"][0]
                self.ui.frame_slider.setMaximum(
                    len(selected_node.vertex_animation.frames) - 1
                )
                self.state_machine.submitEvent("enable_play")
            else:
                mesh = gl_items["mesh"]
                normals = gl_items["normals"]
                self.state_machine.submitEvent("stop")
            mesh.setVisible(True)
            if self.ui.actionToggle_Normals.isChecked():
                normals.setVisible(True)

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self.ui, "Open File", "", "XBF Files (*.xbf)"
        )
        if fileName:
            self.loadFile(fileName)

    def load_glItem(self, item):
        item.setVisible(False)
        self.ui.viewer.view.addItem(item)

    def loadFile(self, fileName):

        try:
            scene = load_xbf(fileName)
        except Exception as e:
            error_dialog = QMessageBox(self.ui)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("File Loading Error")
            error_dialog.setText("Invalid XBF file")
            error_dialog.exec()
            qDebug(str(f"Error loading file: {fileName}\n{e}"))
            return

        self.ui.viewer.view.clear()  # reset() ?
        self.gl_items = {}
        self.ui.animationsList.clear()
        self.ui.segmentsList.clear()

        self.state_machine.submitEvent("stop")

        self.scene_model = SceneModel(scene)
        self.ui.nodeList.setModel(self.scene_model)
        self.ui.nodeList.selectionModel().selectionChanged.connect(
            self.on_node_selected
        )
        # Expand root nodes
        # Maybe TODO: only if a limited number
        for row in range(self.scene_model.rowCount()):
            index = self.scene_model.index(row, 0)
            self.ui.nodeList.setExpanded(index, True)
        for i in range(1, 7):
            self.ui.nodeList.header().setSectionResizeMode(
                i, QHeaderView.ResizeToContents
            )

        for node in scene:
            if node.vertices:
                items = get_mesh(node)
                self.gl_items[node.name] = items
                for value in items.values():
                    if isinstance(value, list):
                        for item in value:
                            self.load_glItem(item)
                    else:
                        self.load_glItem(value)

        animations = parse_animations(scene.FXData)
        for animation in animations:
            animation_item = QListWidgetItem(animation.name)
            animation_item.setData(Qt.UserRole, animation)
            self.ui.animationsList.addItem(animation_item)

        self.ui.fileValue.setText(QFileInfo(fileName).fileName())
        self.ui.versionValue.setText(str(scene.version))

        if fileName in self.recent_files:
            self.recent_files.remove(fileName)
        self.recent_files.insert(0, fileName)
        self.recent_files = self.recent_files[:5]
        self.settings.setValue("recentFiles", self.recent_files)
        self.updateRecentFilesMenu()

    def updateRecentFilesMenu(self):
        self.ui.recentMenu.clear()
        for fileName in self.recent_files:
            action = QAction(fileName, self.ui)
            action.triggered.connect(lambda checked, f=fileName: self.loadFile(f))
            self.ui.recentMenu.addAction(action)

    def timer_out(self):
        current_frame = self.ui.frame_slider.value()
        self.ui.frame_slider.setValue(
            (current_frame + 1) % self.ui.frame_slider.maximum()
        )

    def update_frame(self, current_frame):
        selection_model = self.ui.nodeList.selectionModel()
        if selection_model is None:
            return
        selected_indexes = selection_model.selectedIndexes()
        if not selected_indexes:
            return

        selected_node = selected_indexes[0].internalPointer()

        mesh = self.gl_items.get(selected_node.name)
        if mesh is not None:
            if has_vertex_animation_frames(selected_node):
                self.hide_all()
                mesh["vertex animation mesh"][current_frame].setVisible(True)
                if self.ui.actionToggle_Normals.isChecked():
                    mesh["vertex animation normals"][current_frame].setVisible(True)
