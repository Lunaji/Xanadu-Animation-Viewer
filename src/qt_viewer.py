import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QListWidgetItem,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QAction, QColorConstants
from PySide6.QtCore import QTimer, QSettings, qDebug, QFileInfo
import pyqtgraph.opengl as gl
from PySide6.QtUiTools import QUiLoader
from xanlib import load_xbf


def convert_signed_5bit(v):
    sign=-1 if (v%32)>15 else 1
    return sign*(v%16)

def decompose_regular(vertices):
    positions = np.array([v.position for v in vertices])

    norm_scale = 100
    norm_ends = positions + norm_scale*np.array([v.normal for v in vertices])
    normals = np.empty((len(vertices)*2,3))
    normals[0::2] = positions
    normals[1::2] = norm_ends

    return positions, normals


def decompose_animated(vertices):
    positions = np.array([vertex[:3] for vertex in vertices])

    norm_scale = 100
    norm_ends = positions + norm_scale*np.array([
            [
                convert_signed_5bit((vertex[3] >> x) & 0x1F)
                for x in (0, 5, 10)
            ] for vertex in vertices
        ])
    normals = np.empty((len(vertices)*2,3))
    normals[0::2] = positions
    normals[1::2] = norm_ends

    return positions, normals

def find_node(node, name):
    if node.name == name:
        return node

    for child in node.children:
        r = find_node(child, name)
        if r is not None:
            return r

    return None


class AnimationViewer():
    def __init__(self, ui):
        self.current_frame = 0
        self.selected_node = None
        self.ui = ui

        self.initUI()

        #TODO: dict of meshes
        self.mesh = None
        self.normal_arrows = None


    def find_va_nodes(self, node):

        node_item = QListWidgetItem(node.name)
        if node.vertex_animation:
            node_item.setBackground(QColorConstants.Svg.lightgreen)
        self.ui.nodeList.addItem(node_item)

        for child in node.children:
            self.find_va_nodes(child)


    def initUI(self):
        self.ui.setGeometry(100, 100, 1280, 720)

        self.settings = QSettings('DualNatureStudios', 'AnimationViewer')
        self.recent_files = self.settings.value("recentFiles")
        if self.recent_files is None:
            self.recent_files = []

        self.ui.viewer.view = gl.GLViewWidget()
        self.ui.viewer.layout = QVBoxLayout(self.ui.viewer)
        self.ui.viewer.layout.addWidget(self.ui.viewer.view)
        self.ui.viewer.view.setCameraPosition(
            distance=100000,
            elevation = 300,
            azimuth = 90
        )

        self.timer = QTimer(self.ui)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)

        self.ui.action_Open.triggered.connect(self.openFile)
        self.updateRecentFilesMenu()

        self.ui.nodeList.itemSelectionChanged.connect(self.on_node_selected)


    def clear_node_details(self):
        self.ui.nodeFlagsValue.setText('')
        self.ui.vertexCountValue.setText('')
        self.ui.faceCountValue.setText('')
        self.ui.childCountValue.setText('')


    def cleanup_meshes(self):
        if self.mesh is not None:
            self.ui.viewer.view.removeItem(self.mesh)
            self.mesh = None
        if self.normal_arrows is not None:
            self.ui.viewer.view.removeItem(self.normal_arrows)
            self.normal_arrows = None


    def on_node_selected(self):
        items = self.ui.nodeList.selectedItems()
        if not items:
            return
        item = items[0]

        for node in self.scene.nodes:
            r = find_node(node, item.text())
            if r is not None:
                break

        if r is not None:
            self.selected_node = r
            self.cleanup_meshes()

            if self.selected_node.vertex_animation:
                positions,normals = decompose_animated(self.selected_node.vertex_animation.frames[0])
            else:
                positions,normals = decompose_regular(self.selected_node.vertices)

            self.mesh = gl.GLMeshItem(
                vertexes=positions,
                faces=np.array([face.vertex_indices for face in self.selected_node.faces]),
                drawFaces=False,
                drawEdges=True,
            )
            self.ui.viewer.view.addItem(self.mesh)

            self.normal_arrows = gl.GLLinePlotItem(
                pos=normals,
                color=(1, 0, 0, 1),
                width=2,
                mode='lines'
            )
            self.ui.viewer.view.addItem(self.normal_arrows)

            self.ui.nodeFlagsValue.setText(str(self.selected_node.flags))
            self.ui.vertexCountValue.setText(str(len(self.selected_node.vertices)))
            self.ui.faceCountValue.setText(str(len(self.selected_node.faces)))
            self.ui.childCountValue.setText(str(len(self.selected_node.children)))


    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self.ui, "Open File", "", "XBF Files (*.xbf)")
        if fileName:
            self.loadFile(fileName)

    def loadFile(self, fileName):

        try:
            self.scene = load_xbf(fileName)
        except Exception as e:
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("File Loading Error")
            error_dialog.setText('Invalid XBF file')
            error_dialog.exec()
            qDebug(str(f'Error loading file: {fileName}\n{e}'))
            return

        self.ui.nodeList.clear()
        self.cleanup_meshes()
        self.clear_node_details()

        for node in self.scene.nodes:
            self.find_va_nodes(node)

        self.ui.fileValue.setText(QFileInfo(self.scene.file).fileName())
        self.ui.versionValue.setText(str(self.scene.version))

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


    def update_frame(self):

        if self.selected_node is not None:

            if self.selected_node.vertex_animation is not None:
                self.current_frame = (self.current_frame + 1) % len(self.selected_node.vertex_animation.frames)

                positions, normals = decompose_animated(self.selected_node.vertex_animation.frames[self.current_frame])

                if self.mesh is not None:
                    self.mesh.setMeshData(
                        vertexes=positions,
                        faces=np.array([face.vertex_indices for face in self.selected_node.faces]),
                    )

                if self.normal_arrows is not None:
                    self.normal_arrows.setData(pos=normals)


if __name__ == '__main__':
    loader = QUiLoader()
    app = QApplication(sys.argv)
    ui = loader.load('form.ui')
    viewer = AnimationViewer(ui)
    viewer.ui.show()
    sys.exit(app.exec())
