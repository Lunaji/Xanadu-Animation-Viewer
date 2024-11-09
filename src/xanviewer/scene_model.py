from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import QApplication, QStyle


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
        if parent_node is None:  # assert can't ?
            return QModelIndex()

        grandparent_node = parent_node.parent
        if grandparent_node is None:
            nodes_row = self.scene.nodes
        else:
            nodes_row = grandparent_node.children
        row = next((i for i, node in enumerate(nodes_row) if node == parent_node), None)
        if row is None:  # assert can't ?
            return QModelIndex()
        return self.createIndex(row, 0, parent_node)

    def rowCount(self, index=QModelIndex()):
        if not index.isValid():
            return len(self.scene.nodes)
        return len(index.internalPointer().children)

    def columnCount(self, index=QModelIndex()):
        return 7

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        node = index.internalPointer()
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return node.name
            elif column == 1:
                return len(node.vertices)
            elif column == 2:
                return len(node.faces)

        if role == Qt.CheckStateRole:
            if column == 3:
                return Qt.Checked if node.rgb is not None else Qt.Unchecked
            elif column == 4:
                return Qt.Checked if node.smoothing_groups is not None else Qt.Unchecked
            elif column == 5:
                return Qt.Checked if node.vertex_animation is not None else Qt.Unchecked
            elif column == 6:
                return Qt.Checked if node.key_animation is not None else Qt.Unchecked

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return "Object"

        if role == Qt.DecorationRole and orientation == Qt.Horizontal:
            if section == 1:
                return QApplication.style().standardIcon(
                    QStyle.SP_FileDialogContentsView
                )
            elif section == 2:
                return QApplication.style().standardIcon(QStyle.SP_TitleBarShadeButton)
            elif section == 3:
                return QApplication.style().standardIcon(QStyle.SP_BrowserReload)
            elif section == 4:
                return QApplication.style().standardIcon(QStyle.SP_BrowserStop)
            elif section == 5:
                return QApplication.style().standardIcon(QStyle.SP_ArrowRight)
            elif section == 6:
                return QApplication.style().standardIcon(QStyle.SP_ArrowDown)

        if role == Qt.ToolTipRole and orientation == Qt.Horizontal:
            if section == 1:
                return "Vertex Count"
            elif section == 2:
                return "Face Count"
            elif section == 3:
                return "Prelight"
            elif section == 4:
                return "Smoothing Groups"
            elif section == 5:
                return "Vertex Animation"
            elif section == 6:
                return "Keyframe Animation"

        return None
