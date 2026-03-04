"""主視窗 — 側邊欄專案列表 + 檔案樹 + 右鍵選單."""

from pathlib import Path

from PySide6.QtCore import Qt, QSortFilterProxyModel, QEvent
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeView, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QMenu,
    QAbstractItemView, QDialog, QLineEdit,
)

from database import (
    get_connection, init_db, create_project, list_projects,
    delete_project, get_node_abs_path,
    list_project_roots, add_project_root,
)
from fuzzy import fuzzy_score
from scanner import scan_directory
from presentation.tree_model import ProjectTreeModel
from domain.enums import (
    MODE_READ, MODE_VIRTUAL, MODE_REALTIME,
    MODE_LABELS, MODE_TOOLTIPS, MODE_COLORS,
)

# ── Dialog / Widget（已搬至 presentation/）──────────────────
from presentation.dialogs.project_dialogs import ProjectRootsDialog
from presentation.dialogs.settings_dialogs import ThemeDialog
from presentation.widgets.metadata_panel import MetadataPanel


class FuzzyFilterProxyModel(QSortFilterProxyModel):
    """樹視圖模糊篩選代理模型 — 遞迴過濾，父節點在子節點匹配時自動顯示."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pattern = ""
        self.setRecursiveFilteringEnabled(True)

    def set_pattern(self, pattern: str):
        self._pattern = pattern.strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if not self._pattern:
            return True
        idx = self.sourceModel().index(row, 0, parent)
        node = idx.internalPointer() if idx.isValid() else None
        if node is None:
            return False
        return fuzzy_score(self._pattern, node.name) >= 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Organizer")
        self.resize(1100, 700)

        self._conn = get_connection()
        init_db(self._conn)
        self._current_project_id: int | None = None
        self._tree_model: ProjectTreeModel | None = None
        self._proxy: FuzzyFilterProxyModel | None = None
        self._mode: str = MODE_VIRTUAL  # 預設虛擬模式

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
        self._project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._project_list.customContextMenuRequested.connect(
            self._show_project_context_menu
        )
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

        # 右側：篩選欄 + 檔案樹（包在 container 裡）
        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("篩選…")
        self._filter_input.setFixedHeight(26)
        self._filter_input.setVisible(False)
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        tree_layout.addWidget(self._filter_input)

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
        self._tree_view.installEventFilter(self)
        tree_layout.addWidget(self._tree_view)

        self._meta_panel = MetadataPanel(self._conn, parent=self)
        self._meta_panel.setVisible(False)

        splitter.addWidget(left)
        splitter.addWidget(tree_container)
        splitter.addWidget(self._meta_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.setCentralWidget(splitter)

        # 狀態列：模式切換按鈕組
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(2)
        self._mode_buttons: dict[str, QPushButton] = {}
        for mode_key in (MODE_READ, MODE_VIRTUAL, MODE_REALTIME):
            btn = QPushButton(MODE_LABELS[mode_key])
            btn.setCheckable(True)
            btn.setToolTip(MODE_TOOLTIPS[mode_key])
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                "QPushButton { padding: 1px 8px; border: 1px solid #585b70; "
                "border-radius: 3px; font-size: 12px; } "
                "QPushButton:checked { background: %s; color: #1e1e2e; "
                "font-weight: bold; }" % MODE_COLORS[mode_key]
            )
            btn.clicked.connect(
                lambda _=False, m=mode_key: self._set_mode(m)
            )
            mode_layout.addWidget(btn)
            self._mode_buttons[mode_key] = btn
        self._mode_buttons[self._mode].setChecked(True)
        self.statusBar().addPermanentWidget(mode_widget)


    # ── 內嵌模糊篩選 ─────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._tree_view and event.type() == QEvent.KeyPress:
            key = event.key()
            mods = event.modifiers()
            # Escape → 清除篩選
            if key == Qt.Key_Escape and self._filter_input.isVisible():
                self._filter_input.clear()
                return True
            # 可列印字元（無 Ctrl/Alt 修飾）→ 啟動篩選
            text = event.text()
            if (text and text.isprintable()
                    and not (mods & (Qt.ControlModifier | Qt.AltModifier))):
                self._filter_input.setVisible(True)
                self._filter_input.setFocus()
                self._filter_input.setText(self._filter_input.text() + text)
                return True
        return super().eventFilter(obj, event)

    def _on_filter_text_changed(self, text: str) -> None:
        if not self._proxy:
            return
        pattern = text.strip()
        if not pattern:
            # 清空 → 還原完整樹
            self._proxy.set_pattern("")
            self._filter_input.setVisible(False)
            self._tree_view.setFocus()
            # 還原拖放
            if self._mode != MODE_READ:
                self._tree_view.setDragEnabled(True)
                self._tree_view.setAcceptDrops(True)
                self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)
        else:
            self._proxy.set_pattern(pattern)
            self._tree_view.expandAll()
            # 篩選期間停用拖放
            self._tree_view.setDragEnabled(False)
            self._tree_view.setAcceptDrops(False)
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)

    def _node_from_index(self, index):
        """統一從 proxy 或 source index 取得 TreeNode."""
        if not index.isValid():
            return None
        if self._proxy and index.model() is self._proxy:
            index = self._proxy.mapToSource(index)
        return index.internalPointer() if index.isValid() else None

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("檔案(&F)")
        act_add = QAction("新增專案(&N)", self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self._add_project)
        file_menu.addAction(act_add)

        file_menu.addSeparator()

        act_quit = QAction("結束(&Q)", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        tools_menu = menu.addMenu("工具(&T)")
        act_theme = QAction("外觀主題(&T)…", self)
        act_theme.triggered.connect(self._open_theme_dialog)
        tools_menu.addAction(act_theme)

        view_menu = menu.addMenu("檢視(&V)")
        act_refresh = QAction("重新整理(&R)", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._rescan_project)
        view_menu.addAction(act_refresh)

        act_meta = QAction("Metadata 面板(&M)", self)
        act_meta.setShortcut(QKeySequence("F3"))
        act_meta.setCheckable(True)
        act_meta.triggered.connect(
            lambda checked: self._meta_panel.setVisible(checked)
        )
        view_menu.addAction(act_meta)
        view_menu.addSeparator()

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
            root_id = add_project_root(self._conn, pid, str(path), "proj")
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法建立專案：{e}")
            return

        self.statusBar().showMessage(f"掃描 {path} …")
        count = scan_directory(self._conn, pid, path, root_id=root_id)
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
            self._proxy = None
            self._current_project_id = None
            self._filter_input.clear()
            self._filter_input.setVisible(False)

    def _rescan_project(self) -> None:
        if not self._current_project_id:
            return
        roots = list_project_roots(self._conn, self._current_project_id)
        if not roots:
            # fallback：舊專案只有 projects.root_path
            row = self._conn.execute(
                "SELECT root_path FROM projects WHERE id=?",
                (self._current_project_id,),
            ).fetchone()
            if not row:
                return
            roots = [{"id": None, "root_path": row["root_path"]}]

        self.statusBar().showMessage("重新掃描中…")
        try:
            self._conn.execute(
                "DELETE FROM nodes WHERE project_id=?",
                (self._current_project_id,),
            )
            total = 0
            for r in roots:
                path = Path(r["root_path"])
                if not path.exists():
                    continue
                total += scan_directory(
                    self._conn, self._current_project_id, path,
                    root_id=r["id"],
                )
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            QMessageBox.warning(self, "掃描失敗", f"重新掃描時發生錯誤，已還原：\n{e}")
            return
        self.statusBar().showMessage(f"已掃描 {total} 個項目")
        if self._tree_model:
            self._tree_model.refresh()

    def _on_tree_selection_changed(self, current, previous) -> None:
        if not current.isValid():
            return
        node = self._node_from_index(current)
        if node and self._meta_panel.isVisible():
            self._meta_panel.load_node(node.db_id, self._current_project_id)



    def _show_project_context_menu(self, pos) -> None:
        item = self._project_list.itemAt(pos)
        if not item:
            return
        pid = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_roots = menu.addAction("管理根目錄…")
        act_roots.triggered.connect(
            lambda: self._open_roots_dialog(pid)
        )
        menu.addSeparator()
        act_remove = menu.addAction("移除專案")
        act_remove.triggered.connect(self._remove_project)
        menu.exec_(self._project_list.viewport().mapToGlobal(pos))

    def _open_theme_dialog(self) -> None:
        dlg = ThemeDialog(self._conn, self)
        dlg.exec_()


    # ── 模式切換 ──────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        """切換操作模式。"""
        self._mode = mode
        for k, btn in self._mode_buttons.items():
            btn.setChecked(k == mode)
        self._apply_mode()
        self.statusBar().showMessage(
            f"模式：{MODE_LABELS[mode].split(' ', 1)[1]}")

    def _apply_mode(self) -> None:
        """根據當前模式啟用/停用 UI 元件。"""
        is_read = self._mode == MODE_READ
        if is_read:
            self._tree_view.setDragEnabled(False)
            self._tree_view.setAcceptDrops(False)
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        else:
            self._tree_view.setDragEnabled(True)
            self._tree_view.setAcceptDrops(True)
            self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)


    def _open_roots_dialog(self, project_id: int) -> None:
        dlg = ProjectRootsDialog(self._conn, project_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self._rescan_project()


    def _on_project_selected(self, current: QListWidgetItem,
                              previous: QListWidgetItem) -> None:
        if not current:
            return
        pid = current.data(Qt.UserRole)
        self._current_project_id = pid
        self._tree_model = ProjectTreeModel(self._conn, pid)
        self._proxy = FuzzyFilterProxyModel(self)
        self._proxy.setSourceModel(self._tree_model)
        self._tree_view.setModel(self._proxy)
        self._tree_view.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )
        # 切換專案時清除篩選
        self._filter_input.clear()
        self._filter_input.setVisible(False)
        self._apply_mode()

    # ── 右鍵選單 ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        idx = self._tree_view.indexAt(pos)
        node = self._node_from_index(idx)
        if node is None:
            return

        menu = QMenu(self)

        if node.node_type == "file":
            act_open = menu.addAction("以系統預設開啟")
            act_open.triggered.connect(lambda: self._open_system(node))

        act_reveal = menu.addAction("在檔案管理器中顯示")
        act_reveal.triggered.connect(lambda: self._open_in_explorer(node))

        menu.exec_(self._tree_view.viewport().mapToGlobal(pos))

    def _open_system(self, node) -> None:
        full = self._resolve_node_path(node)
        if not full or not full.is_file():
            return
        import os
        os.startfile(str(full))

    def _resolve_node_path(self, node) -> Path | None:
        """統一路徑解析：優先透過 get_node_abs_path，fallback 到 projects.root_path。"""
        abs_path = get_node_abs_path(self._conn, node.db_id)
        if abs_path:
            return abs_path
        if not self._current_project_id:
            return None
        row = self._conn.execute(
            "SELECT root_path FROM projects WHERE id=?",
            (self._current_project_id,),
        ).fetchone()
        if not row:
            return None
        return Path(row["root_path"]) / node.rel_path

    def _open_in_explorer(self, node) -> None:
        full = self._resolve_node_path(node)
        if not full:
            return
        import subprocess, sys
        if sys.platform == "win32":
            if full.is_dir():
                subprocess.Popen(["explorer", str(full)])
            else:
                subprocess.Popen(["explorer", "/select,", str(full)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(full)])
        else:
            subprocess.Popen(["xdg-open", str(full.parent if full.is_file() else full)])
