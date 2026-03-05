"""主視窗 — 側邊欄專案列表 + 檔案樹 + 右鍵選單."""

from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QModelIndex, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeView, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QMenu,
    QAbstractItemView, QDialog,
)

from database import (
    get_connection, init_db, create_project, list_projects,
    delete_project, get_node_abs_path,
    list_project_roots, add_project_root,
)
from scanner import scan_directory
from presentation.tree_model import ProjectTreeModel, setup_tree_header
from domain.enums import (
    MODE_READ, MODE_VIRTUAL, MODE_REALTIME,
    MODE_LABELS, MODE_TOOLTIPS, MODE_COLORS,
)
from domain.models import Command
from domain.services.virtual_tree import VNodeStatus
from application.mode_controller import ModeController

# ── Dialog / Widget（已搬至 presentation/）──────────────────
from presentation.dialogs.project_dialogs import ProjectRootsDialog
from presentation.dialogs.settings_dialogs import ThemeDialog
from presentation.widgets.metadata_panel import MetadataPanel
from presentation.widgets.diff_panel import DiffPanel
from presentation.widgets.dual_panel import _TreePanel
from presentation.widgets.flat_search import FlatSearchWidget


class _ScanWorker(QThread):
    """背景掃描執行緒，避免阻塞 UI。"""
    finished = Signal(int)   # 掃描完成，回傳節點數
    progress = Signal(str)   # 文字進度訊息

    def __init__(self, conn_path: str, project_id: int,
                 roots: list, parent=None):
        super().__init__(parent)
        self._conn_path = conn_path
        self._project_id = project_id
        self._roots = roots

    @staticmethod
    def _format_bar(current: int, total: int) -> str:
        pct = current * 100 // total if total > 0 else 0
        filled = pct // 5  # 20 格
        bar = "\u2588" * filled + "\u2591" * (20 - filled)
        return f"[{bar}] {pct}%  {current}/{total}"

    def run(self) -> None:
        import sqlite3
        conn = sqlite3.connect(self._conn_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8000")
        conn.execute("PRAGMA temp_store=MEMORY")
        try:
            conn.execute(
                "DELETE FROM nodes WHERE project_id=?",
                (self._project_id,),
            )
            total = 0
            base = 0  # 多根目錄累計偏移
            for r in self._roots:
                path = Path(r["root_path"])
                if not path.exists():
                    continue

                def _on_progress(current, item_total, _base=base):
                    self.progress.emit(self._format_bar(
                        _base + current, _base + item_total))

                count = scan_directory(
                    conn, self._project_id, path,
                    root_id=r["id"],
                    on_progress=_on_progress,
                )
                base += count
                total += count
            conn.commit()
        except Exception:
            import traceback; traceback.print_exc()
            conn.rollback()
            total = -1
        finally:
            conn.close()
        self.finished.emit(total)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Organizer")
        self.resize(1100, 700)

        self._conn = get_connection()
        init_db(self._conn)
        self._current_project_id: int | None = None
        self._tree_model: ProjectTreeModel | None = None
        self._controller = ModeController()
        self._controller.set_mode(MODE_VIRTUAL)
        self._rel_path_to_db_id: dict[str, int] = {}
        self._last_snapshot: list[dict] = []
        self._scan_worker: _ScanWorker | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(50)  # 50ms 節流
        self._refresh_timer.timeout.connect(self._do_throttled_refresh)

        self._build_ui()
        self._build_menu_bar()
        self._load_project_list()

        self.statusBar().showMessage("就緒")

    def closeEvent(self, event) -> None:
        self._refresh_timer.stop()
        if self._scan_worker and self._scan_worker.isRunning():
            try:
                self._scan_worker.finished.disconnect()
            except RuntimeError:
                pass
            self._scan_worker.wait(3000)
        super().closeEvent(event)

    # ── UI 建構 ──────────────────────────────────────────

    def _build_ui(self) -> None:
        self._splitter = splitter = QSplitter(Qt.Horizontal)

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

        btn_rescan = QPushButton("重新掃描")
        btn_rescan.clicked.connect(self._rescan_project)
        left_layout.addWidget(btn_rescan)

        left.setMinimumWidth(140)
        left.setMaximumWidth(200)

        # 右側：側邊工具列 + 檔案樹 + 扁平搜尋
        tree_container = QWidget()
        tree_outer = QHBoxLayout(tree_container)
        tree_outer.setContentsMargins(0, 0, 0, 0)
        tree_outer.setSpacing(0)

        # ── 縱向細欄工具列 ──
        self._side_toolbar = QWidget()
        self._side_toolbar.setFixedWidth(28)
        tb_layout = QVBoxLayout(self._side_toolbar)
        tb_layout.setContentsMargins(2, 4, 2, 4)
        tb_layout.setSpacing(4)

        from presentation.file_icons import get_category_icon
        btn_mkdir = QPushButton()
        btn_mkdir.setIcon(get_category_icon("folder_add"))
        btn_mkdir.setToolTip("新增資料夾")
        btn_mkdir.setFixedSize(24, 24)
        btn_mkdir.setStyleSheet(
            "QPushButton { border: none; border-radius: 4px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )
        btn_mkdir.clicked.connect(self._do_mkdir)
        tb_layout.addWidget(btn_mkdir)
        tb_layout.addStretch()

        tree_outer.addWidget(self._side_toolbar)

        # ── 檔案樹 + 搜尋 ──
        tree_inner = QWidget()
        tree_layout = QVBoxLayout(tree_inner)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self._tree_view = QTreeView()
        self._tree_view.setHeaderHidden(False)
        self._tree_view.setDragEnabled(True)
        self._tree_view.setAcceptDrops(True)
        self._tree_view.setDropIndicatorShown(True)
        self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)
        self._tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree_view.customContextMenuRequested.connect(self._show_context_menu)
        self._tree_view.setAnimated(False)
        self._tree_view.setIndentation(20)
        self._tree_view.installEventFilter(self)
        tree_layout.addWidget(self._tree_view)

        self._flat_search = FlatSearchWidget(self)
        self._flat_search.setVisible(False)
        self._flat_search.selected.connect(self._on_flat_search_selected)
        self._flat_search.cancelled.connect(self._on_flat_search_cancelled)
        tree_layout.addWidget(self._flat_search)

        tree_outer.addWidget(tree_inner, 1)

        self._meta_panel = MetadataPanel(self._conn, parent=self)
        self._meta_panel.setVisible(False)

        # Panel B：第二面板（F6 切換，僅即時模式）
        self._panel_b = _TreePanel(self._conn, parent=self)
        self._panel_b.setVisible(False)

        splitter.addWidget(left)
        splitter.addWidget(tree_container)
        splitter.addWidget(self._panel_b)
        splitter.addWidget(self._meta_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setStretchFactor(3, 0)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([180, 1, 0, 0])

        self.setCentralWidget(splitter)

        # 虛擬模式操作按鈕（套用 / 放棄）— 先加入，排在左側
        self._virtual_bar = QWidget()
        vbar_layout = QHBoxLayout(self._virtual_bar)
        vbar_layout.setContentsMargins(0, 0, 0, 0)
        vbar_layout.setSpacing(4)

        self._lbl_pending = QLabel("0 項變更")
        vbar_layout.addWidget(self._lbl_pending)

        btn_apply = QPushButton("套用變更")
        btn_apply.setFixedHeight(22)
        btn_apply.setStyleSheet(
            "QPushButton { padding: 1px 8px; background: #a6e3a1; "
            "color: #1e1e2e; border-radius: 3px; font-size: 12px; }"
        )
        btn_apply.clicked.connect(self._virtual_apply)
        vbar_layout.addWidget(btn_apply)

        btn_discard = QPushButton("放棄並退出")
        btn_discard.setFixedHeight(22)
        btn_discard.setStyleSheet(
            "QPushButton { padding: 1px 8px; background: #f38ba8; "
            "color: #1e1e2e; border-radius: 3px; font-size: 12px; }"
        )
        btn_discard.clicked.connect(self._virtual_discard)
        vbar_layout.addWidget(btn_discard)

        self._virtual_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self._virtual_bar)

        # 狀態列：模式切換按鈕組 — 後加入，永遠在最右側
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
                "QPushButton { padding: 1px 8px; border: none; "
                "border-radius: 3px; font-size: 12px; } "
                "QPushButton:checked { background: %s; color: #1e1e2e; "
                "font-weight: bold; }" % MODE_COLORS[mode_key]
            )
            btn.clicked.connect(
                lambda _=False, m=mode_key: self._set_mode(m)
            )
            mode_layout.addWidget(btn)
            self._mode_buttons[mode_key] = btn
        self._mode_buttons[self._controller.mode].setChecked(True)
        self.statusBar().addPermanentWidget(mode_widget)


    # ── 扁平搜尋（取代舊版模糊篩選）───────────────────────

    def eventFilter(self, obj, event):
        if obj is self._tree_view and event.type() == QEvent.KeyPress:
            key = event.key()
            mods = event.modifiers()
            text = event.text()
            # 可列印字元（無 Ctrl/Alt 修飾）→ 啟動扁平搜尋
            if (text and text.isprintable()
                    and not (mods & (Qt.ControlModifier | Qt.AltModifier))):
                self._tree_view.setVisible(False)
                self._flat_search.activate(text)
                return True
        return super().eventFilter(obj, event)

    def _on_flat_search_selected(self, rel_path: str) -> None:
        """使用者在扁平搜尋中選取項目 → 導航至樹節點。"""
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._tree_view.setFocus()
        self._navigate_to_node(rel_path)

    def _on_flat_search_cancelled(self) -> None:
        """使用者按 Escape → 關閉扁平搜尋，回到樹。"""
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._tree_view.setFocus()

    def _navigate_to_node(self, rel_path: str) -> None:
        """在樹中定位並選取指定 rel_path 的節點。"""
        if not self._tree_model:
            return
        node = self._tree_model._node_map.get(self._rel_path_to_db_id.get(rel_path))
        if not node:
            return
        idx = self._tree_model.createIndex(node.row, 0, node)
        parent = node.parent
        while parent and parent is not self._tree_model._root:
            parent_idx = self._tree_model.createIndex(parent.row, 0, parent)
            self._tree_view.expand(parent_idx)
            parent = parent.parent
        self._tree_view.setCurrentIndex(idx)
        self._tree_view.scrollTo(idx)

    def _node_from_index(self, index):
        """統一從 index 取得 TreeNode。"""
        if not index.isValid():
            return None
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

        edit_menu = menu.addMenu("編輯(&E)")
        act_undo = QAction("復原(&U)", self)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(self._do_undo)
        edit_menu.addAction(act_undo)

        act_redo = QAction("重做(&R)", self)
        act_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        act_redo.triggered.connect(self._do_redo)
        edit_menu.addAction(act_redo)

        edit_menu.addSeparator()

        act_delete = QAction("刪除(&D)", self)
        act_delete.setShortcut(QKeySequence("Delete"))
        act_delete.triggered.connect(self._do_delete_selected)
        edit_menu.addAction(act_delete)

        act_rename = QAction("重命名(&N)", self)
        act_rename.setShortcut(QKeySequence("F2"))
        act_rename.triggered.connect(self._do_rename_selected)
        edit_menu.addAction(act_rename)

        act_mkdir = QAction("新增資料夾(&F)", self)
        act_mkdir.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act_mkdir.triggered.connect(self._do_mkdir)
        edit_menu.addAction(act_mkdir)

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
        act_meta.triggered.connect(self._toggle_meta_panel)
        view_menu.addAction(act_meta)

        act_panel_b = QAction("第二面板(&B)", self)
        act_panel_b.setShortcut(QKeySequence("F6"))
        act_panel_b.setCheckable(True)
        act_panel_b.triggered.connect(self._toggle_panel_b)
        view_menu.addAction(act_panel_b)
        self._act_panel_b = act_panel_b

        view_menu.addSeparator()

        act_collapse = QAction("全部收合(&C)", self)
        act_collapse.triggered.connect(self._tree_view.collapseAll)
        view_menu.addAction(act_collapse)

        act_expand = QAction("全部展開(&E)", self)
        act_expand.triggered.connect(self._tree_view.expandAll)
        view_menu.addAction(act_expand)

        # ── 模式選單 ──────────────────────────────────
        mode_menu = menu.addMenu("模式(&M)")

        act_preview = QAction("閱覽(&P)", self)
        act_preview.setShortcut(QKeySequence("Ctrl+1"))
        act_preview.triggered.connect(lambda: self._set_mode(MODE_READ))
        mode_menu.addAction(act_preview)

        act_virtual = QAction("虛擬(&V)", self)
        act_virtual.setShortcut(QKeySequence("Ctrl+2"))
        act_virtual.triggered.connect(lambda: self._set_mode(MODE_VIRTUAL))
        mode_menu.addAction(act_virtual)

        act_live = QAction("即時(&L)", self)
        act_live.setShortcut(QKeySequence("Ctrl+3"))
        act_live.triggered.connect(lambda: self._set_mode(MODE_REALTIME))
        mode_menu.addAction(act_live)

        mode_menu.addSeparator()

        act_apply = QAction("套用變更(&A)", self)
        act_apply.setShortcut(QKeySequence("Ctrl+Return"))
        act_apply.triggered.connect(self._virtual_apply)
        mode_menu.addAction(act_apply)

        act_discard = QAction("放棄並退出(&D)", self)
        act_discard.setShortcut(QKeySequence("Ctrl+Escape"))
        act_discard.triggered.connect(self._virtual_discard)
        mode_menu.addAction(act_discard)

    # ── 專案管理 ─────────────────────────────────────────

    def _load_project_list(self) -> None:
        self._project_list.clear()
        for row in list_projects(self._conn):
            item = QListWidgetItem(row["name"])
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

        if self._is_scanning():
            QMessageBox.warning(self, "提示", "掃描進行中，請稍後再試。")
            return
        self.statusBar().showMessage(f"掃描 {path} …")
        self._refresh_timer.stop()
        from infrastructure.database import DB_PATH
        new_pid = pid
        self._scan_worker = _ScanWorker(
            str(DB_PATH), pid,
            [{"id": root_id, "root_path": str(path)}], parent=self,
        )
        self._scan_worker.progress.connect(self.statusBar().showMessage)
        self._scan_worker.finished.connect(
            lambda count: self._on_add_scan_finished(count, new_pid)
        )
        self._scan_worker.start()

    def _on_add_scan_finished(self, count: int, pid: int) -> None:
        self._scan_worker = None
        if count < 0:
            QMessageBox.warning(self, "掃描失敗", "掃描時發生錯誤。")
            return
        self.statusBar().showMessage(f"已掃描 {count} 個項目")
        self._load_project_list()
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
            self._flat_search.deactivate()
            self._tree_view.setVisible(True)

    def _is_scanning(self) -> bool:
        return self._scan_worker is not None and self._scan_worker.isRunning()

    def _rescan_project(self) -> None:
        if not self._current_project_id:
            return
        if self._is_scanning():
            return  # 掃描中，不重複觸發
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
        self._refresh_timer.stop()  # 掃描中禁止節流 refresh
        from infrastructure.database import DB_PATH
        pid = self._current_project_id
        self._scan_worker = _ScanWorker(
            str(DB_PATH), pid,
            [dict(r) for r in roots], parent=self,
        )
        self._scan_worker.progress.connect(self.statusBar().showMessage)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _refresh_with_state(self) -> None:
        """refresh 樹模型並恢復展開狀態。"""
        if not self._tree_model:
            return
        # 儲存目前展開的路徑
        expanded = set()
        def _collect_expanded(parent_idx=QModelIndex()):
            for r in range(self._tree_model.rowCount(parent_idx)):
                idx = self._tree_model.index(r, 0, parent_idx)
                if self._tree_view.isExpanded(idx):
                    node = idx.internalPointer()
                    if node and node.rel_path:
                        expanded.add(node.rel_path)
                    elif node and node.is_root_group:
                        expanded.add(f"__root_group_{node.db_id}")
                    _collect_expanded(idx)
        _collect_expanded()

        self._tree_model.refresh()

        # 恢復展開狀態
        def _restore_expanded(parent_idx=QModelIndex()):
            for r in range(self._tree_model.rowCount(parent_idx)):
                idx = self._tree_model.index(r, 0, parent_idx)
                node = idx.internalPointer()
                if not node:
                    continue
                key = node.rel_path if node.rel_path else (
                    f"__root_group_{node.db_id}" if node.is_root_group else "")
                if key and key in expanded:
                    self._tree_view.expand(idx)
                    _restore_expanded(idx)
        _restore_expanded()

        # 更新扁平快取
        search_cache, self._last_snapshot = self._build_flat_lists()
        self._flat_search.set_flat_cache(search_cache)

    def _on_scan_finished(self, count: int) -> None:
        self._scan_worker = None
        if count < 0:
            QMessageBox.warning(self, "掃描失敗", "重新掃描時發生錯誤，已還原。")
            return
        self.statusBar().showMessage(f"已掃描 {count} 個項目")
        self._refresh_with_state()

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

    def _toggle_meta_panel(self, checked: bool) -> None:
        """F3 切換 Metadata 面板。"""
        self._meta_panel.setVisible(checked)
        self._splitter.update()

    def _toggle_panel_b(self, checked: bool) -> None:
        """F6 切換第二面板（僅即時模式可用）。"""
        if self._controller.mode != MODE_REALTIME and checked:
            QMessageBox.information(
                self, "第二面板", "第二面板僅在即時模式下可用。\n請先切換至即時模式（Ctrl+3）。"
            )
            self._act_panel_b.setChecked(False)
            return
        self._panel_b.setVisible(checked)
        self._splitter.update()
        if checked:
            self._panel_b.load_projects()


    # ── 模式切換 ──────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        """切換操作模式。"""
        # 離開虛擬模式時，若有未套用變更，詢問使用者
        if self._controller.mode == MODE_VIRTUAL and mode != MODE_VIRTUAL:
            if self._controller.virtual_active and self._controller.pending_commands():
                reply = QMessageBox.question(
                    self, "虛擬模式",
                    "目前有未套用的虛擬變更，要放棄嗎？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    for k, btn in self._mode_buttons.items():
                        btn.setChecked(k == self._controller.mode)
                    return
            self._controller.discard()
            self._clear_virtual_overlay()

        self._controller.set_mode(mode)
        for k, btn in self._mode_buttons.items():
            btn.setChecked(k == mode)
        self._apply_mode()
        self.statusBar().showMessage(f"模式：{MODE_LABELS[mode]}")

    def _apply_mode(self) -> None:
        """根據當前模式啟用/停用 UI 元件。"""
        is_read = self._controller.mode == MODE_READ
        is_virtual = self._controller.mode == MODE_VIRTUAL

        if is_read:
            self._tree_view.setDragEnabled(False)
            self._tree_view.setAcceptDrops(False)
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        else:
            self._tree_view.setDragEnabled(True)
            self._tree_view.setAcceptDrops(True)
            self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)

        # 虛擬模式：開始 VirtualService + 設定 drop 攔截
        if is_virtual and self._tree_model:
            if not self._controller.virtual_active:
                snapshot = getattr(self, "_last_snapshot", None) or self._build_flat_lists()[1]
                self._controller.begin_virtual(snapshot)
            self._tree_model.set_on_drop(self._on_virtual_drop)
        elif self._tree_model:
            self._tree_model.set_on_drop(
                self._on_live_drop if self._controller.mode == MODE_REALTIME else None
            )

        self._virtual_bar.setVisible(is_virtual)
        self._update_virtual_status()

        # 非即時模式時關閉第二面板
        if self._controller.mode != MODE_REALTIME and self._panel_b.isVisible():
            self._panel_b.setVisible(False)
            self._act_panel_b.setChecked(False)
            self._splitter.update()


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
        self._tree_view.setModel(self._tree_model)
        setup_tree_header(self._tree_view.header())
        self._tree_view.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )
        # 建立扁平快取（搜尋 + snapshot 共用一次遍歷）
        search_cache, self._last_snapshot = self._build_flat_lists()
        self._flat_search.set_flat_cache(search_cache)
        self._flat_search.deactivate()
        self._tree_view.setVisible(True)
        self._apply_mode()

    # ── 統一操作（透過 ModeController）─────────────────────

    def _build_flat_lists(self) -> tuple[list[dict], list[dict]]:
        """一次遍歷 tree model，同時建立搜尋快取和 snapshot。

        回傳 (search_cache, snapshot)。
        """
        search: list[dict] = []
        snapshot: list[dict] = []
        self._rel_path_to_db_id: dict[str, int] = {}
        if not self._tree_model:
            return search, snapshot
        stack = [self._tree_model._root]
        while stack:
            node = stack.pop()
            if node.db_id != 0:
                if node.rel_path:
                    search.append({"name": node.name, "rel_path": node.rel_path})
                    self._rel_path_to_db_id[node.rel_path] = node.db_id
                snapshot.append({
                    "path": node.rel_path,
                    "node_type": node.node_type,
                    "db_id": node.db_id,
                })
            if node.loaded:
                stack.extend(reversed(node.children))
        return search, snapshot

    def _on_virtual_drop(self, source_nodes, target_node) -> None:
        """虛擬模式 drop 攔截：批次 push move commands，只 resolve 一次。"""
        for src in source_nodes:
            dest = f"{target_node.rel_path}/{src.name}" if target_node.rel_path else src.name
            self._controller.execute(Command(op="move", source=src.rel_path, dest=dest))
        self._update_virtual_status()  # 所有命令 push 後才更新一次
        self.statusBar().showMessage(f"虛擬移動：{len(source_nodes)} 個項目")

    def _on_live_drop(self, source_nodes, target_node) -> None:
        """即時模式 drop 攔截：透過 controller 立即執行 move。"""
        for src in source_nodes:
            abs_src = self._resolve_node_path(src)
            abs_tgt = self._resolve_node_path(target_node)
            if abs_src and abs_tgt:
                dest = abs_tgt / src.name if abs_tgt.is_dir() else abs_tgt
                rec = self._controller.execute(
                    Command(op="move", source=str(abs_src), dest=str(dest))
                )
                if rec and not rec.success:
                    QMessageBox.warning(self, "移動失敗", rec.error or "未知錯誤")
                    return
        self._schedule_refresh()
        self.statusBar().showMessage(f"已移動 {len(source_nodes)} 個項目")

    def _update_virtual_status(self) -> None:
        """更新虛擬模式 UI：pending 計數 + 樹結構 + 著色。"""
        if not self._controller.virtual_active:
            self._lbl_pending.setText("0 項變更")
            self._clear_virtual_overlay()
            return
        cmds = self._controller.pending_commands()
        self._lbl_pending.setText(f"{len(cmds)} 項變更")
        resolved = self._controller.resolve_tree()
        if self._tree_model:
            self._tree_model.apply_virtual_tree(resolved)

    def _clear_virtual_overlay(self) -> None:
        if self._tree_model:
            self._tree_model.clear_virtual_tree()

    def _schedule_refresh(self) -> None:
        """節流 refresh：50ms 內的多次呼叫只觸發一次。掃描中不觸發。"""
        if self._is_scanning():
            return
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _do_throttled_refresh(self) -> None:
        if self._tree_model:
            self._refresh_with_state()

    def _after_mutation(self) -> None:
        """undo/redo/execute 後統一重整 UI。"""
        if self._controller.mode == MODE_VIRTUAL:
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME and self._tree_model:
            self._schedule_refresh()

    def _do_undo(self) -> None:
        if self._controller.mode == MODE_READ:
            return
        self._controller.undo()
        self._after_mutation()

    def _do_redo(self) -> None:
        if self._controller.mode == MODE_READ:
            return
        self._controller.redo()
        self._after_mutation()

    def _do_delete_selected(self) -> None:
        """刪除選取節點（所有模式共用）；專案清單有焦點時改為移除專案。"""
        if self._project_list.hasFocus():
            self._remove_project()
            return
        if self._controller.mode == MODE_READ:
            return
        indexes = self._tree_view.selectionModel().selectedIndexes()
        seen = set()
        for idx in indexes:
            node = self._node_from_index(idx)
            if node and node.rel_path and node.rel_path not in seen:
                seen.add(node.rel_path)
                if self._controller.mode == MODE_VIRTUAL:
                    self._controller.execute(Command(op="delete", source=node.rel_path))
                elif self._controller.mode == MODE_REALTIME:
                    abs_path = self._resolve_node_path(node)
                    if abs_path:
                        rec = self._controller.execute(
                            Command(op="delete", source=str(abs_path))
                        )
                        if rec and not rec.success:
                            QMessageBox.warning(self, "刪除失敗", rec.error or "未知錯誤")
        if seen:
            if self._controller.mode == MODE_VIRTUAL:
                self._update_virtual_status()
            elif self._controller.mode == MODE_REALTIME:
                self._schedule_refresh()
            self.statusBar().showMessage(f"已刪除 {len(seen)} 個項目")

    def _do_rename_selected(self) -> None:
        """重命名選取節點（所有模式共用）。"""
        if self._controller.mode == MODE_READ:
            return
        idx = self._tree_view.currentIndex()
        node = self._node_from_index(idx)
        if not node or not node.rel_path:
            return
        new_name, ok = QInputDialog.getText(self, "重命名", "新名稱：", text=node.name)
        if not ok or not new_name.strip() or new_name.strip() == node.name:
            return
        if self._controller.mode == MODE_VIRTUAL:
            parent_path = "/".join(node.rel_path.split("/")[:-1])
            new_path = f"{parent_path}/{new_name.strip()}" if parent_path else new_name.strip()
            self._controller.execute(Command(op="rename", source=node.rel_path, dest=new_path))
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME:
            abs_path = self._resolve_node_path(node)
            if abs_path:
                new_dest = abs_path.parent / new_name.strip()
                rec = self._controller.execute(
                    Command(op="rename", source=str(abs_path), dest=str(new_dest))
                )
                if rec and not rec.success:
                    QMessageBox.warning(self, "重命名失敗", rec.error or "未知錯誤")
                else:
                    self._schedule_refresh()

    def _resolve_parent_node(self, node):
        """取得適合作為 parent 的資料夾節點：若選中檔案則回傳其父資料夾。"""
        if not node:
            return None
        if node.node_type in ("folder", "virtual"):
            return node
        return node.parent if node.parent else None

    def _do_mkdir(self) -> None:
        """新增資料夾（所有模式共用），放入選中的資料夾內。"""
        if self._controller.mode == MODE_READ:
            return
        idx = self._tree_view.currentIndex()
        node = self._node_from_index(idx)
        parent = self._resolve_parent_node(node)
        name, ok = QInputDialog.getText(self, "新增資料夾", "資料夾名稱：")
        if not ok or not name.strip():
            return
        if self._controller.mode == MODE_VIRTUAL:
            parent_path = parent.rel_path if parent and parent.rel_path else ""
            new_path = f"{parent_path}/{name.strip()}" if parent_path else name.strip()
            self._controller.execute(Command(op="mkdir", source=new_path))
            self._update_virtual_status()
        elif self._controller.mode == MODE_REALTIME:
            parent_abs = self._resolve_node_path(parent) if parent else None
            if parent_abs and parent_abs.is_dir():
                target = parent_abs / name.strip()
            else:
                # 在專案根目錄建立
                row = self._conn.execute(
                    "SELECT root_path FROM projects WHERE id=?",
                    (self._current_project_id,),
                ).fetchone()
                if not row:
                    return
                target = Path(row["root_path"]) / name.strip()
            rec = self._controller.execute(Command(op="mkdir", source=str(target)))
            if rec and not rec.success:
                QMessageBox.warning(self, "建立失敗", rec.error or "未知錯誤")
            else:
                self._schedule_refresh()

    def _virtual_apply(self) -> None:
        """虛擬模式：開啟 DiffPanel 確認後套用所有變更。"""
        if not self._controller.virtual_active:
            return
        cmds = self._controller.pending_commands()
        if not cmds:
            QMessageBox.information(self, "虛擬模式", "沒有待套用的變更。")
            return
        dlg = DiffPanel(cmds, self)
        if dlg.exec_() != QDialog.Accepted:
            return

        def executor(cmd: Command) -> bool:
            self.statusBar().showMessage(f"執行：{cmd.op} {cmd.source}")
            return True

        self._controller.apply(executor)
        self._clear_virtual_overlay()
        self._virtual_bar.setVisible(False)
        if self._tree_model:
            self._tree_model.set_on_drop(None)
        self._refresh_with_state()
        self.statusBar().showMessage("變更已套用")

    def _virtual_discard(self) -> None:
        """虛擬模式：放棄所有變更並退回預覽模式。"""
        cmds = self._controller.pending_commands()
        if self._controller.virtual_active and cmds:
            reply = QMessageBox.question(
                self, "放棄變更",
                f"確定要放棄 {len(cmds)} 項虛擬變更？",
            )
            if reply != QMessageBox.Yes:
                return
        self._controller.discard()
        self._clear_virtual_overlay()
        self._set_mode(MODE_READ)

    # ── 右鍵選單 ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        idx = self._tree_view.indexAt(pos)
        node = self._node_from_index(idx)
        if node is None:
            return

        menu = QMenu(self)

        # 編輯操作（虛擬 / 即時模式）
        if self._controller.mode != MODE_READ:
            suffix = "（虛擬）" if self._controller.mode == MODE_VIRTUAL else ""
            act_del = menu.addAction(f"刪除{suffix}")
            act_del.triggered.connect(self._do_delete_selected)
            act_ren = menu.addAction(f"重命名{suffix}")
            act_ren.triggered.connect(self._do_rename_selected)
            if node.node_type in ("folder", "virtual"):
                act_mkdir = menu.addAction(f"新增資料夾{suffix}")
                act_mkdir.triggered.connect(self._do_mkdir)
            menu.addSeparator()

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
