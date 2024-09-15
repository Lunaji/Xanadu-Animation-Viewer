import sys
import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QListWidget,
    QMenuBar,
    QMenu,
    QFileDialog,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtGui import QAction
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import QTimer, QSettings, qDebug, QFileInfo
import pyqtgraph.opengl as gl
from xanlib import load_xbf


def convert_signed_5bit(v):
    sign=-1 if (v%32)>15 else 1
    return sign*(v%16)

def decompose(vertices):
    positions = np.array([vertex[:3] for vertex in vertices])
    
    norm_scale = 100
    normals = np.empty((positions.shape[0], 2, 3))
    #interleave instead ?
    normals[:, 0] = positions
    normals[:, 1] = positions + norm_scale*np.array([
            [
                convert_signed_5bit((vertex[3] >> x) & 0x1F)
                for x in (0, 5, 10)
            ] for vertex in vertices
        ])
    
    return positions, normals
    


def find_node(node, name):
    if node.name == name:
        return node
    
    for child in node.children:
        r = find_node(child, name)
        if r is not None:
            return r
    
    return None
    
        
class AnimationViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_frame = 0
        self.selected_node = None

        self.initUI()
        
        #TODO: dict of meshes
        self.mesh = None
        self.normal_arrows = None

        
    def find_va_nodes(self, node):
        
        if node.vertex_animation is not None:
            self.va_nodes_list.addItem(node.name)
            
        for child in node.children:
            self.find_va_nodes(child)
        

    def initUI(self):
        self.setWindowTitle('Animation Viewer')
        self.setGeometry(100, 100, 1280, 720)
        
        self.settings = QSettings('DualNatureStudios', 'AnimationViewer')
        self.recent_files = self.settings.value("recentFiles")

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        self.gl_widget = QOpenGLWidget(self)
        self.gl_widget.view = gl.GLViewWidget()
        self.gl_widget.layout = QVBoxLayout(self.gl_widget)
        self.gl_widget.layout.addWidget(self.gl_widget.view)
        self.gl_widget.view.setCameraPosition(
            distance=100000,
            elevation = 300,
            azimuth = 90
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)
        
        menubar = self.menuBar()

        fileMenu = menubar.addMenu('&File')

        openAct = QAction('&Open', self)
        openAct.setShortcut('Ctrl+O')
        openAct.triggered.connect(self.openFile)
        fileMenu.addAction(openAct)

        self.recentMenu = fileMenu.addMenu('Recent Files')
        self.updateRecentFilesMenu()

        exitAct = QAction('&Exit', self)
        exitAct.setShortcut('Ctrl+Q')
        exitAct.triggered.connect(self.close)
        fileMenu.addAction(exitAct)
        
        self.va_nodes_list = QListWidget(self)
        self.va_nodes_list.itemClicked.connect(self.on_node_clicked)
            
        label = QLabel("Nodes with Vertex Animation", self)
        
        scene_details_box = QGroupBox("Scene details", self)
        scene_details_layout = QVBoxLayout()
        self.scene_details_widgets = {
            'File': QLabel(f'File:'),
            'Version': QLabel(f'Version:')
        }
        for widget in self.scene_details_widgets.values():
            scene_details_layout.addWidget(widget)
        scene_details_box.setLayout(scene_details_layout)
        
        node_details_box = QGroupBox("Node details", self)
        node_details_layout = QVBoxLayout()
        self.node_details_widgets = {
            attr: QLabel(self) for attr in ('Flags','VertexCount','FaceCount','ChildCount')
        }        
        self.clear_node_details()
        for widget in self.node_details_widgets.values():
            node_details_layout.addWidget(widget)
        scene_details_box.setLayout(scene_details_layout)
        node_details_box.setLayout(node_details_layout)
            
        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(scene_details_box)
        sidebar_layout.addWidget(label)
        sidebar_layout.addWidget(self.va_nodes_list)
        sidebar_layout.addWidget(node_details_box)
        
        layout = QHBoxLayout(central_widget)
        layout.addWidget(self.gl_widget)
        layout.addLayout(sidebar_layout)
        layout.setStretch(0, 3)  # Give more space to GLWidget (index 0)
        layout.setStretch(1, 1)  # Give less space to Sidebar (index 1)
        
    def clear_node_details(self):
        self.node_details_widgets['Flags'].setText(f'Flags:')
        self.node_details_widgets['VertexCount'].setText(f'Vertex #:')
        self.node_details_widgets['FaceCount'].setText(f'Face #:')
        self.node_details_widgets['ChildCount'].setText(f'Child #:')
        
        
    def cleanup_meshes(self):
        if self.mesh is not None:
            self.gl_widget.view.removeItem(self.mesh)
            self.mesh = None
        if self.normal_arrows is not None:
            self.gl_widget.view.removeItem(self.normal_arrows)
            self.normal_arrows = None
        
        
    def on_node_clicked(self, item):
        for node in self.scene.nodes:
            r = find_node(node, item.text())
            if r is not None:
                break
            
        if r is not None:            
            self.selected_node = r
            
            self.cleanup_meshes()
            
            #Use non-animated mesh instead for init?
            positions, normals = decompose(self.selected_node.vertex_animation.body[0])
                
            self.mesh = gl.GLMeshItem(
                vertexes=positions,
                faces=np.array([face.vertex_indices for face in self.selected_node.faces]),
                drawFaces=False,
                drawEdges=True,
            )        
            self.gl_widget.view.addItem(self.mesh)
            
            self.normal_arrows = gl.GLLinePlotItem(
                pos=normals,
                color=(1, 0, 0, 1),
                width=2,
                mode='lines'
            )
            self.gl_widget.view.addItem(self.normal_arrows)
            
            self.node_details_widgets['Flags'].setText(f'Flags: {self.selected_node.flags}')
            self.node_details_widgets['VertexCount'].setText(f'Vertex #: {len(self.selected_node.vertices)}')
            self.node_details_widgets['FaceCount'].setText(f'Face #: {len(self.selected_node.faces)}')
            self.node_details_widgets['ChildCount'].setText(f'Child #: {len(self.selected_node.children)}')


    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "XBF Files (*.xbf)")
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
        
        self.va_nodes_list.clear()
        self.cleanup_meshes()
        self.clear_node_details()
        
        for node in self.scene.nodes:
            self.find_va_nodes(node)
            
        self.scene_details_widgets['File'].setText(f'File: {QFileInfo(self.scene.file).fileName()}')
        self.scene_details_widgets['Version'].setText(f'Version: {self.scene.version}')

        if fileName in self.recent_files:
            self.recent_files.remove(fileName)
        self.recent_files.insert(0, fileName)
        self.recent_files = self.recent_files[:5]
        self.settings.setValue("recentFiles", self.recent_files)
        self.updateRecentFilesMenu()
        

    def updateRecentFilesMenu(self):
        self.recentMenu.clear()
        for fileName in self.recent_files:
            action = QAction(fileName, self)
            action.triggered.connect(lambda checked, f=fileName: self.loadFile(f))
            self.recentMenu.addAction(action)
        

    def update_frame(self):
        
        if self.selected_node is not None:
            
            self.current_frame = (self.current_frame + 1) % len(self.selected_node.vertex_animation.body)
            
            positions, normals = decompose(self.selected_node.vertex_animation.body[self.current_frame])
            
            if self.mesh is not None:            
                self.mesh.setMeshData(
                    vertexes=positions,
                    faces=np.array([face.vertex_indices for face in self.selected_node.faces]),
                )
                
            if self.normal_arrows is not None:
                self.normal_arrows.setData(pos=normals)
        

if __name__ == '__main__':
    app = QApplication(sys.argv)

    viewer = AnimationViewer()
    viewer.show()

    sys.exit(app.exec())
