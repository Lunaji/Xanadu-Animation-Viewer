import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QFileDialog,
    QMessageBox,
    QHeaderView
)
from PySide6.QtGui import QAction
from PySide6.QtCore import (
    QTimer,
    QSettings,
    qDebug,
    QFileInfo,
    QAbstractItemModel,
    Qt,
    QModelIndex
)
import pyqtgraph.opengl as gl
from PySide6.QtUiTools import QUiLoader
from xanlib import load_xbf


def decompose(vertices):
    positions = np.array([v.position for v in vertices])

    norm_scale = 100
    norm_ends = positions + norm_scale*np.array([v.normal for v in vertices])
    normals = np.empty((len(vertices)*2,3))
    normals[0::2] = positions
    normals[1::2] = norm_ends

    return positions, normals

def has_vertex_animation_frames(node):
    return node.vertex_animation is not None and node.vertex_animation.frames

def get_mesh(node):

    positions,normals = decompose(node.vertices)
    faces = np.array([face.vertex_indices for face in node.faces])

    mesh = gl.GLMeshItem(
        vertexes=positions,
        faces=faces,
        drawFaces=False,
        drawEdges=True,
    )

    normal_arrows = gl.GLLinePlotItem(
        pos=normals,
        color=(1, 0, 0, 1),
        width=2,
        mode='lines'
    )

    va_mesh = []
    va_normals = []
    if has_vertex_animation_frames(node):
        for frame in node.vertex_animation.frames:
            frame_positions, frame_normals = decompose(frame)

            va_mesh.append(gl.GLMeshItem(
                    vertexes=frame_positions,
                    faces=faces,
                    drawFaces=False,
                    drawEdges=True,
                ))

            va_normals.append(gl.GLLinePlotItem(
                pos=frame_normals,
                color=(1, 0, 0, 1),
                width=2,
                mode='lines'
            ))


    return {
        'mesh': mesh,
        'normals': normal_arrows,
        'vertex animation mesh': va_mesh,
        'vertex animation normals': va_normals
    }


class SceneModel(QAbstractItemModel):

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.scene = scene

    def index(self, row, column, parent=QModelIndex()):
        if not parent.isValid():
            node = self.scene.nodes[row]
        else:
            parent_node = parent.internalPointer()
            node = parent_node.children[row]
        return self.createIndex(row, column, node)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        child = index.internalPointer()
        parent_node = child.parent
        if parent_node is None: #assert can't ?
            return QModelIndex()

        grandparent_node = parent_node.parent
        if grandparent_node is None:
            nodes_row = self.scene.nodes
        else:
            nodes_row = grandparent_node.children
        row = next((i for i,node in enumerate(nodes_row) if node==parent_node), None)
        if row is None: # assert can't ?
            return QModelIndex()
        return self.createIndex(row, 0, parent_node)

    def rowCount(self, index=QModelIndex()):
        if not index.isValid():
            return len(self.scene.nodes)
        return len(index.internalPointer().children)

    def columnCount(self, index=QModelIndex()):
        return 3

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        node = index.internalPointer()
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return node.name

        if role == Qt.CheckStateRole:
            if column == 1:
                return Qt.Checked if node.vertex_animation is not None else Qt.Unchecked
            elif column == 2:
                return Qt.Checked if node.key_animation is not None else Qt.Unchecked

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return "Node Name"
            elif section == 1:
                return "V"
            elif section == 2:
                return "K"
        return None


class AnimationViewer():
    def __init__(self, ui):
        self.ui = ui
        self.ui.setGeometry(100, 100, 1280, 720)

        self.settings = QSettings('DualNatureStudios', 'AnimationViewer')
        self.recent_files = self.settings.value("recentFiles")
        if self.recent_files is None:
            self.recent_files = []


        self.gl_items = {}

        self.ui.viewer.view = gl.GLViewWidget()
        self.ui.viewer.layout = QVBoxLayout(self.ui.viewer)
        self.ui.viewer.layout.addWidget(self.ui.viewer.view)
        self.ui.viewer.view.setCameraPosition(
            distance=100000,
            elevation = 300,
            azimuth = 90
        )

        self.ui.action_Open.triggered.connect(self.openFile)
        self.updateRecentFilesMenu()

        self.ui.actionToggle_Wireframe.triggered.connect(self.toggle_wireframe)
        self.ui.actionToggle_Normals.triggered.connect(self.toggle_normals)

        self.timer = QTimer(self.ui)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)

        self.current_frame = 0


    def toggle_wireframe(self):
        for mesh in filter(lambda item: isinstance(item, gl.GLMeshItem), self.ui.viewer.view.items):
            mesh.opts['drawFaces'] = not mesh.opts['drawFaces']
        self.ui.viewer.view.update()

    def toggle_normals(self):
        for key in self.gl_items:
            if self.gl_items[key]['mesh'].visible():
                normals = self.gl_items[key]['normals']
                normals.setVisible(not normals.visible())

    def clear_node_details(self):
        self.ui.nodeFlagsValue.setText('')
        self.ui.vertexCountValue.setText('')
        self.ui.faceCountValue.setText('')
        self.ui.childCountValue.setText('')

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
                mesh = gl_items['vertex animation mesh'][0]
                normals = gl_items['vertex animation normals'][0]
            else:
                mesh = gl_items['mesh']
                normals = gl_items['normals']
            mesh.setVisible(True)
            if self.ui.actionToggle_Normals.isChecked():
                normals.setVisible(True)

        self.ui.nodeFlagsValue.setText(str(selected_node.flags))
        self.ui.vertexCountValue.setText(str(len(selected_node.vertices)))
        self.ui.faceCountValue.setText(str(len(selected_node.faces)))
        self.ui.childCountValue.setText(str(len(selected_node.children)))


    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self.ui, "Open File", "", "XBF Files (*.xbf)")
        if fileName:
            self.loadFile(fileName)

    def load_glItem(self, item):
        item.setVisible(False)
        self.ui.viewer.view.addItem(item)

    def loadFile(self, fileName):

        try:
            scene = load_xbf(fileName)
        except Exception as e:
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setWindowTitle("File Loading Error")
            error_dialog.setText('Invalid XBF file')
            error_dialog.exec()
            qDebug(str(f'Error loading file: {fileName}\n{e}'))
            return

        self.ui.viewer.view.clear() # reset() ?
        self.gl_items = {}
        self.clear_node_details()



        self.scene_model = SceneModel(scene)
        ui.nodeList.setModel(self.scene_model)
        self.ui.nodeList.selectionModel().selectionChanged.connect(self.on_node_selected)
        #Expand root nodes
        #Maybe TODO: only if a limited number
        for row in range(self.scene_model.rowCount()):
            index = self.scene_model.index(row, 0)
            self.ui.nodeList.setExpanded(index, True)
        self.ui.nodeList.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ui.nodeList.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.ui.nodeList.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)

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


        self.ui.fileValue.setText(QFileInfo(scene.file).fileName())
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

    def update_frame(self):
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
                self.current_frame = (self.current_frame + 1) % len(selected_node.vertex_animation.frames)
                self.hide_all()
                mesh['vertex animation mesh'][self.current_frame].setVisible(True)
                if self.ui.actionToggle_Normals.isChecked():
                    mesh['vertex animation normals'][self.current_frame].setVisible(True)


if __name__ == '__main__':
    loader = QUiLoader()
    app = QApplication(sys.argv)
    ui = loader.load('form.ui')
    viewer = AnimationViewer(ui)
    viewer.ui.show()
    sys.exit(app.exec())
