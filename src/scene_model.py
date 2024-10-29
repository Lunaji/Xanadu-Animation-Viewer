from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

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
