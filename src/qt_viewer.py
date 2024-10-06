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


def decompose(vertices):
    positions = np.array([v.position for v in vertices])

    norm_scale = 100
    norm_ends = positions + norm_scale*np.array([v.normal for v in vertices])
    normals = np.empty((len(vertices)*2,3))
    normals[0::2] = positions
    normals[1::2] = norm_ends

    return positions, normals


class AnimationViewer():
    def __init__(self, ui):
        self.current_frame = 0
        self.selected_node = None
        self.ui = ui

        self.initUI()

        #TODO: dict of meshes
        self.mesh = None
        self.normal_arrows = None


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
        self.ui.animList.itemSelectionChanged.connect(self.on_anim_selected)
        self.ui.animRangeList.itemSelectionChanged.connect(self.on_anim_range_selected)
        self.ui.eventList.itemSelectionChanged.connect(self.on_event_selected)


    def clear_node_details(self):
        self.ui.nodeFlagsValue.setText('')
        self.ui.vertexCountValue.setText('')
        self.ui.faceCountValue.setText('')
        self.ui.childCountValue.setText('')

    def clear_anim_details(self):
        self.ui.animNameValue.setText('')
        self.ui.animArgsValue.setText('')

    def clear_anim_range_details(self):
        self.ui.animStartValue.setText('')
        self.ui.animEndValue.setText('')
        self.ui.animRepeatValue.setText('')
        self.ui.animUnk1Value.setText('')
        self.ui.animUnk2Value.setText('')

    def clear_event_details(self):
        self.ui.eventTypeName.setText('')
        self.ui.eventTypeValue.setText('')
        self.ui.eventName1Value.setText('')
        self.ui.eventName2Value.setText('')
        self.ui.eventFrameValue.setText('')
        self.ui.eventIslongValue.setText('')
        self.ui.eventUnknownValue.setText('')
        self.ui.eventHeadArgsValue.setText('')
        self.ui.eventTailArgsValue.setText('')

    def cleanup_meshes(self):
        if self.mesh is not None:
            self.ui.viewer.view.removeItem(self.mesh)
            self.mesh = None
        if self.normal_arrows is not None:
            self.ui.viewer.view.removeItem(self.normal_arrows)
            self.normal_arrows = None


    def on_node_selected(self):
        self.selected_node = None
        if len(self.ui.nodeList.selectedItems())>0:
            self.selected_node = self.ui.nodeList.selectedItems()[0].data(1)

        self.clear_node_details()
        if self.selected_node is not None:
            self.cleanup_meshes()

            if self.selected_node.vertex_animation is not None and self.selected_node.vertex_animation.frames is not None:
                positions,normals = decompose(self.selected_node.vertex_animation.frames[0])
            else:
                positions,normals = decompose(self.selected_node.vertices)

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

    
    def on_anim_selected(self):
        anim = None
        if len(self.ui.animList.selectedItems())>0:
            anim = self.ui.animList.selectedItems()[0].data(1)
        self.ui.animRangeList.clear()
        self.clear_anim_details()
        self.clear_anim_range_details()
        if anim is not None:            
            self.ui.animNameValue.setText(anim.name)

            args=""
            deuxcentquatre=0
            for val in anim.args:
                if val==204:
                    deuxcentquatre+=1
                else:
                    if deuxcentquatre>0:
                        args+=" 204("+str(deuxcentquatre)+")" if deuxcentquatre>1 else " 204"
                        deuxcentquatre=0
                    args+=" "+str(val)
            self.ui.animArgsValue.setText(args)
            
            for animRange in anim.ranges:
                animRange_item = QListWidgetItem(str(animRange.start) + " -> " + str(animRange.end) + " ("+str(animRange.repeat)+")")
                animRange_item.setData(1, animRange)
                self.ui.animRangeList.addItem(animRange_item)
            self.ui.animRangeList.setCurrentRow(0)
    
    def on_anim_range_selected(self):
        animRange = None
        if len(self.ui.animRangeList.selectedItems())>0:
            animRange = self.ui.animRangeList.selectedItems()[0].data(1)

        self.clear_anim_range_details()
        if animRange is not None:
            self.ui.animStartValue.setText(str(animRange.start))
            self.ui.animEndValue.setText(str(animRange.end))
            self.ui.animRepeatValue.setText(str(animRange.repeat))
            self.ui.animUnk1Value.setText(str(animRange.unknown1))
            self.ui.animUnk2Value.setText(str(animRange.unknown2))

    def on_event_selected(self):
        event = None
        if len(self.ui.eventList.selectedItems())>0:
            event = self.ui.eventList.selectedItems()[0].data(1)
        self.clear_event_details()
        if event is not None:            
            self.ui.eventTypeName.setText(event.typename)
            self.ui.eventTypeValue.setText(str(event.type))
            self.ui.eventName1Value.setText(event.name1)
            self.ui.eventName2Value.setText(event.name2)
            self.ui.eventFrameValue.setText(str(event.frame_index))
            self.ui.eventIslongValue.setText(str(event.is_long))
            self.ui.eventUnknownValue.setText(str(event.unknown))
            self.ui.eventHeadArgsValue.setText(", ".join([str(x) for x in event.head_args]))
            self.ui.eventTailArgsValue.setText(", ".join([str(x) for x in event.tail_args]))

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
        self.ui.animList.clear()
        self.ui.animRangeList.clear()
        self.clear_anim_details()
        self.clear_anim_range_details()
        self.ui.eventList.clear()
        self.clear_event_details()

        for node in self.scene:
            node_item = QListWidgetItem(node.name)
            if node.vertex_animation:
                node_item.setBackground(QColorConstants.Svg.lightgreen)
            node_item.setData(1,node)
            self.ui.nodeList.addItem(node_item)

        self.ui.fileValue.setText(QFileInfo(self.scene.file).fileName())
        self.ui.versionValue.setText(str(self.scene.version))

        for anim in self.scene.animations:
            anim_item = QListWidgetItem(anim.name)
            anim_item.setData(1, anim)
            self.ui.animList.addItem(anim_item)

        for event in self.scene.events:
            event_item = QListWidgetItem(event.typename+" "+event.name1+" "+event.name2)
            event_item.setData(1, event)
            self.ui.eventList.addItem(event_item)

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

            if self.selected_node.vertex_animation is not None and self.selected_node.vertex_animation.frames is not None:
                self.current_frame = (self.current_frame + 1) % len(self.selected_node.vertex_animation.frames)

                positions, normals = decompose(self.selected_node.vertex_animation.frames[self.current_frame])

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
