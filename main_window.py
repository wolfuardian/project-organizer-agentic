"""主視窗 — 側邊欄專案列表 + 檔案樹 + 右鍵選單."""

from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeView, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QMenu, QHeaderView,
    QAbstractItemView, QStatusBar,
)

from database import (
    get_connection, init_db, create_project, list_projects,
    delete_project, delete_node,
)
from scanner import scan_directory
from tree_model import ProjectTreeModel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Organizer")
        self.resize(1100, 700)

        self._conn = get_connection()
        init_db(self._conn)
        self._current_project_id: int | None = None
        self._tree_model: ProjectTreeModel | None = None

        self._build_ui()
        self._build_menu_bar()
        self._load_project_list()

        self.statusBar().showMessage("就緒")

    # ── UI 建構 ──────────────────────────────────────────

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Horizontal)

        # 左側：專案列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        left_layout.addWidget(QLabel("專案"))

        self._project_list = QListWidget()
        self._project_list.currentItemChanged.connect(self._on_project_selected)
        left_layout.addWidget(self._project_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("＋ 新增")
        btn_add.clicked.connect(self._add_project)
        btn_del = QPushButton("－ 移除")
        btn_del.clicked.connect(self._remove_project)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        left_layout.addLayout(btn_row)

        btn_rescan = QPushButton("🔄 重新掃描")
        btn_rescan.clicked.connect(self._rescan_project)
        left_layout.addWidget(btn_rescan)

        left.setMaximumWidth(260)

        # 右側：檔案樹
        self._tree_view = QTreeView()
        self._tree_view.setHeaderHidden(True)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setAcceptDrops(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)
        self._tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.setAnimated(True)
        self._tree_view.setIndentation(20)

        splitter.addWidget(left)
        splitter.addWidget(self._tree_view)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("檔案(&F)")
        act_add = QAction("新增專案(&N)", self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self._add_project)
        file_menu.addAction(act_add)

        act_quit = QAction("結束(&Q)", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        view_menu = menu.addMenu("檢視(&V)")
        act_refresh = QAction("重新整理(&R)", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._rescan_project)
        view_menu.addAction(act_refresh)

        act_collapse = QAction("全部收合(&C)", self)
        act_collapse.triggered.connect(self._tree_view.collapseAll)
        view_menu.addAction(act_collapse)

        act_expand = QAction("全部展開(&E)", self)
        act_expand.triggered.connect(self._tree_view.expandAll)
        view_menu.addAction(act_expand)

    # ── 專案管理 ─────────────────────────────────────────

    def _load_project_list(self) -> None:
        self._project_list.clear()
        for row in list_projects(self._conn):
            item = QListWidgetItem(f"📁 {row['name']}")
            item.setData(Qt.UserRole, row["id"])
            item.setToolTip(row["root_path"])
            self._project_list.addItem(item)

    def _add_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇專案根目錄")
        if not folder:
            return
        path = Path(folder)
        name, ok = QInputDialog.getText(
            self, "專案名稱", "輸入名稱：", text=path.name,
        )
        if not ok or not name.strip():
            return

        try:
            pid = create_project(self._conn, name.strip(), str(path))
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法建立專案：{e}")
            return

        self.statusBar().showMessage(f"掃描 {path} …")
        count = scan_directory(self._conn, pid, path)
        self._conn.commit()
        self.statusBar().showMessage(f"已掃描 {count} 個項目")

        self._load_project_list()
        # 自動選取新專案
        for i in range(self._project_list.count()):
            item = self._project_list.item(i)
            if item.data(Qt.UserRole) == pid:
                self._project_list.setCurrentItem(item)
                break

    def _remove_project(self) -> None:
        item = self._project_list.currentItem()
        if not item:
            return
        pid = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "確認", "確定要從列表移除此專案？（不會刪除實際檔案）",
        )
        if reply == QMessageBox.Yes:
            delete_project(self._conn, pid)
            self._load_project_list()
            self._tree_view.setModel(None)
            self._current_project_id = None

    def _rescan_project(self) -> None:
        if not self._current_project_id:
            return
        row = self._conn.execute(
            "SELECT root_path FROM projects WHERE id=?",
            (self._current_project_id,),
        ).fetchone()
        if not row:
            return
        path = Path(row["root_path"])
        if not path.exists():
            QMessageBox.warning(self, "錯誤", f"路徑不存在：{path}")
            return
        # 清除舊節點再重掃（DELETE 與 INSERT 在同一事務，掃描失敗則全部復原）
        self.statusBar().showMessage(f"重新掃描 {path} …")
        try:
            self._conn.execute(
                "DELETE FROM nodes WHERE project_id=?",
                (self._current_project_id,),
            )
            count = scan_directory(self._conn, self._current_project_id, path)
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            QMessageBox.warning(self, "掃描失敗", f"重新掃描時發生錯誤，已還原：\n{e}")
            return
        self.statusBar().showMessage(f"已掃描 {count} 個項目")
        if self._tree_model:
            self._tree_model.refresh()

    def _on_project_selected(self, current: QListWidgetItem,
                              previous: QListWidgetItem) -> None:
        if not current:
            return
        pid = current.data(Qt.UserRole)
        self._current_project_id = pid
        self._tree_model = ProjectTreeModel(self._conn, pid)
        self._tree_view.setModel(self._tree_model)
        self.statusBar().showMessage(f"已載入專案 #{pid}")

    # ── 右鍵選單 ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        index = self._tree_view.indexAt(pos)
        menu = QMenu(self)

        if index.isValid():
            node = index.internalPointer()

            act_open = menu.addAction("在檔案管理器中開啟")
            act_open.triggered.connect(lambda: self._open_in_explorer(node))

            menu.addSeparator()

            act_del = menu.addAction("從樹中移除")
            act_del.triggered.connect(lambda: self._delete_tree_node(node))

        act_new_folder = menu.addAction("新增虛擬資料夾")
        act_new_folder.triggered.connect(
            lambda: self._add_virtual_folder(index if index.isValid() else QModelIndex())
        )

        menu.exec_(self._tree_view.viewport().mapToGlobal(pos))

    def _open_in_explorer(self, node) -> None:
        if not self._current_project_id:
            return
        row = self._conn.execute(
            "SELECT root_path FROM projects WHERE id=?",
            (self._current_project_id,),
        ).fetchone()
        if not row:
            return
        import subprocess, sys
        full = Path(row["root_path"]) / node.rel_path
        if sys.platform == "win32":
            if full.is_dir():
                subprocess.Popen(["explorer", str(full)])
            else:
                subprocess.Popen(["explorer", "/select,", str(full)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(full)])
        else:
            subprocess.Popen(["xdg-open", str(full.parent if full.is_file() else full)])

    def _delete_tree_node(self, node) -> None:
        reply = QMessageBox.question(
            self, "確認", f"從樹中移除「{node.name}」？（不影響實際檔案）",
        )
        if reply == QMessageBox.Yes:
            delete_node(self._conn, node.db_id)
            if self._tree_model:
                self._tree_model.refresh()

    def _add_virtual_folder(self, parent_index: QModelIndex) -> None:
        name, ok = QInputDialog.getText(self, "虛擬資料夾", "名稱：")
        if not ok or not name.strip():
            return
        if not self._current_project_id or not self._tree_model:
            return

        parent_id = None
        if parent_index.isValid():
            parent_id = parent_index.internalPointer().db_id

        from database import upsert_node
        clean_name = name.strip()
        # 同一父節點下不允許重名虛擬資料夾
        existing = self._conn.execute(
            "SELECT id FROM nodes WHERE project_id=? AND parent_id IS ? "
            "AND name=? AND node_type='virtual'",
            (self._current_project_id, parent_id, clean_name),
        ).fetchone()
        if existing:
            QMessageBox.warning(self, "已存在", f"此位置已有虛擬資料夾「{clean_name}」")
            return
        parent_key = parent_id if parent_id is not None else 0
        upsert_node(
            self._conn, self._current_project_id,
            parent_id, clean_name, f"__virtual__/{parent_key}/{clean_name}",
            "virtual",
        )
        self._conn.commit()
        self._tree_model.refresh()
