"""主視窗 — 側邊欄專案列表 + 檔案樹 + 右鍵選單."""

from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeView, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QFileDialog, QInputDialog, QMessageBox, QMenu, QHeaderView,
    QAbstractItemView, QStatusBar, QDialog, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QSpinBox, QTextEdit, QSizePolicy, QFrame,
    QTreeWidget, QTreeWidgetItem, QScrollArea,
)

from database import (
    get_connection, init_db, create_project, list_projects,
    delete_project, delete_node,
    PROGRESS_LABELS, PROGRESS_STATES, set_project_progress,
    list_todos, add_todo, toggle_todo, delete_todo,
    get_timeline,
    list_tags, all_tags_flat, create_tag, update_tag, delete_tag,
    get_node_tags, add_node_tag, remove_node_tag,
    update_node_note, get_node, get_node_abs_path,
    RELATION_LABELS, list_relations, add_relation, delete_relation,
    search_nodes, filter_nodes,
    list_tools, list_all_tools, add_tool, update_tool, delete_tool,
    list_project_roots, add_project_root, remove_project_root,
    update_project_root, PROJECT_ROOT_ROLES,
    create_session, get_active_session, finalize_session, cancel_session,
    add_file_operation, update_file_operation_status, list_file_operations,
)
from rule_engine import list_rules, add_rule, update_rule, delete_rule
from duplicate_finder import find_duplicates
from batch_rename import build_previews, execute_renames
from fuzzy import fuzzy_filter
from git_utils import get_git_info, format_git_badge
from templates import (
    get_builtin_templates, list_templates, save_template,
    delete_template, scaffold, export_template, import_template,
    project_to_template,
)
from scanner import scan_directory
from presentation.tree_model import ProjectTreeModel
from report_exporter import export_markdown, export_html, save_report
from backup import (
    create_backup, list_backups, restore_backup, delete_backup,
    get_setting, set_setting,
)
from themes import apply_theme, theme_names
from session_manager import SessionManager
from domain.enums import (
    MODE_READ, MODE_VIRTUAL, MODE_REALTIME,
    MODE_LABELS, MODE_TOOLTIPS, MODE_COLORS,
)

# ── Dialog / Widget（已搬至 presentation/）──────────────────
from presentation.dialogs.organization_dialogs import (
    RulesDialog, RuleEditDialog, DuplicateDialog, BatchRenameDialog,
    CATEGORIES,
)
from presentation.dialogs.template_dialogs import (
    ExtractTemplateDialog, TemplateManagerDialog,
    TemplateEditDialog, TemplatePickerDialog,
)
from presentation.dialogs.search_dialogs import (
    QuickJumpDialog, SearchDialog, FilterDialog,
)
from presentation.dialogs.relation_dialogs import (
    ProjectRelationsDialog, TimelineDialog,
)
from presentation.dialogs.tag_dialogs import TagManagerDialog
from presentation.dialogs.project_dialogs import ProjectRootsDialog
from presentation.dialogs.session_dialogs import OperationHistoryDialog
from presentation.dialogs.settings_dialogs import (
    ThemeDialog, BackupDialog, ExportReportDialog,
    ExternalToolsDialog, ToolEditDialog,
)
from presentation.widgets.todo_panel import TodoPanel
from presentation.widgets.metadata_panel import MetadataPanel
from presentation.widgets.timeline_widget import TimelineWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Organizer")
        self.resize(1100, 700)

        self._conn = get_connection()
        init_db(self._conn)
        self._current_project_id: int | None = None
        self._tree_model: ProjectTreeModel | None = None
        self._session: SessionManager | None = None
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

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        left_layout.addWidget(sep)

        self._todo_panel = TodoPanel(self._conn, parent=left)
        left_layout.addWidget(self._todo_panel)

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

        self._meta_panel = MetadataPanel(self._conn, parent=self)
        self._meta_panel.setVisible(False)

        splitter.addWidget(left)
        splitter.addWidget(self._tree_view)
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

        # 狀態列：工作階段指示器
        self._session_label = QLabel("")
        self._session_label.setStyleSheet(
            "background: #e64553; color: white; padding: 2px 8px; "
            "border-radius: 3px; font-weight: bold;"
        )
        self._session_label.setVisible(False)
        self.statusBar().addPermanentWidget(self._session_label)

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("檔案(&F)")
        act_new_win = QAction("開啟新視窗(&W)", self)
        act_new_win.setShortcut(QKeySequence("Ctrl+Shift+W"))
        act_new_win.triggered.connect(self._open_new_window)
        file_menu.addAction(act_new_win)
        file_menu.addSeparator()

        act_add = QAction("新增專案(&N)", self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self._add_project)
        file_menu.addAction(act_add)

        act_tmpl = QAction("從模板新增專案(&T)…", self)
        act_tmpl.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act_tmpl.triggered.connect(self._add_project_from_template)
        file_menu.addAction(act_tmpl)

        file_menu.addSeparator()

        act_quit = QAction("結束(&Q)", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        tools_menu = menu.addMenu("工具(&T)")
        act_rules = QAction("分類規則(&R)…", self)
        act_rules.triggered.connect(self._open_rules_dialog)
        tools_menu.addAction(act_rules)

        act_dup = QAction("重複檔案偵測(&D)…", self)
        act_dup.triggered.connect(self._open_duplicate_dialog)
        tools_menu.addAction(act_dup)

        act_rename = QAction("批次重新命名(&B)…", self)
        act_rename.triggered.connect(self._open_batch_rename_dialog)
        tools_menu.addAction(act_rename)

        act_tag_mgr = QAction("管理標籤(&G)…", self)
        act_tag_mgr.triggered.connect(self._open_tag_manager)
        tools_menu.addAction(act_tag_mgr)

        tools_menu.addSeparator()
        act_tmpl_mgr = QAction("管理自訂模板(&M)…", self)
        act_tmpl_mgr.triggered.connect(self._open_template_manager)
        tools_menu.addAction(act_tmpl_mgr)

        act_extract = QAction("從現有專案建立模板(&E)…", self)
        act_extract.triggered.connect(self._extract_template_from_project)
        tools_menu.addAction(act_extract)

        tools_menu.addSeparator()
        act_ext_tools = QAction("設定外部工具(&X)…", self)
        act_ext_tools.triggered.connect(self._open_external_tools_dialog)
        tools_menu.addAction(act_ext_tools)

        tools_menu.addSeparator()
        act_export = QAction("匯出報告(&O)…", self)
        act_export.triggered.connect(self._open_export_report_dialog)
        tools_menu.addAction(act_export)

        act_backup = QAction("備份與還原(&U)…", self)
        act_backup.triggered.connect(self._open_backup_dialog)
        tools_menu.addAction(act_backup)

        tools_menu.addSeparator()
        act_theme = QAction("外觀主題(&T)…", self)
        act_theme.triggered.connect(self._open_theme_dialog)
        tools_menu.addAction(act_theme)

        # ── 工作階段選單 ──
        session_menu = menu.addMenu("工作階段(&S)")
        self._act_start_session = QAction("開始整理…", self)
        self._act_start_session.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._act_start_session.triggered.connect(self._start_session)
        session_menu.addAction(self._act_start_session)

        self._act_session_history = QAction("操作歷史…", self)
        self._act_session_history.setShortcut(QKeySequence("Ctrl+H"))
        self._act_session_history.triggered.connect(self._open_history_dialog)
        self._act_session_history.setEnabled(False)
        session_menu.addAction(self._act_session_history)

        self._act_undo_last = QAction("復原上一步", self)
        self._act_undo_last.setShortcut(QKeySequence("Ctrl+Z"))
        self._act_undo_last.triggered.connect(self._undo_last_op)
        self._act_undo_last.setEnabled(False)
        session_menu.addAction(self._act_undo_last)

        session_menu.addSeparator()

        self._act_finalize = QAction("確認完成", self)
        self._act_finalize.triggered.connect(self._finalize_session)
        self._act_finalize.setEnabled(False)
        session_menu.addAction(self._act_finalize)

        self._act_cancel_session = QAction("取消工作階段", self)
        self._act_cancel_session.triggered.connect(self._cancel_session)
        self._act_cancel_session.setEnabled(False)
        session_menu.addAction(self._act_cancel_session)

        view_menu = menu.addMenu("檢視(&V)")
        act_search = QAction("全域搜尋(&F)…", self)
        act_search.setShortcut(QKeySequence("Ctrl+F"))
        act_search.triggered.connect(self._open_search)
        view_menu.addAction(act_search)

        act_filter = QAction("進階過濾器(&L)…", self)
        act_filter.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_filter.triggered.connect(self._open_filter)
        view_menu.addAction(act_filter)

        act_jump = QAction("快速跳轉(&J)…", self)
        act_jump.setShortcut(QKeySequence("Ctrl+P"))
        act_jump.triggered.connect(self._open_quick_jump)
        view_menu.addAction(act_jump)

        act_timeline = QAction("時間軸(&T)…", self)
        act_timeline.triggered.connect(self._open_timeline)
        view_menu.addAction(act_timeline)
        view_menu.addSeparator()
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
            progress = row["progress"] if row["progress"] else "not_started"
            badge = PROGRESS_LABELS.get(progress, "")
            item = QListWidgetItem(f"📁 {row['name']}  {badge}")
            item.setData(Qt.UserRole, row["id"])
            item.setData(Qt.UserRole + 1, progress)
            # Tooltip：路徑 + git 狀態（延遲查詢，不卡 UI）
            tooltip = row["root_path"]
            git_info = get_git_info(Path(row["root_path"]))
            if git_info:
                tooltip += f"\n{format_git_badge(git_info)}"
            item.setToolTip(tooltip)
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

    def _open_new_window(self) -> None:
        win = MainWindow()
        win.show()
        # 保持參考避免被 GC 回收
        if not hasattr(self, "_extra_windows"):
            self._extra_windows = []
        self._extra_windows.append(win)

    def _add_project_from_template(self) -> None:
        all_templates = get_builtin_templates() + list_templates(
            self._conn, include_builtin=False
        )
        dlg = TemplatePickerDialog(all_templates, self._conn, self)
        if dlg.exec_() == QDialog.Accepted and dlg.created_project_id:
            self._load_project_list()
            for i in range(self._project_list.count()):
                item = self._project_list.item(i)
                if item.data(Qt.UserRole) == dlg.created_project_id:
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
        node = current.internalPointer()
        if node and self._meta_panel.isVisible():
            self._meta_panel.load_node(node.db_id, self._current_project_id)

    def _refresh_git_status(self, project_id: int) -> None:
        row = self._conn.execute(
            "SELECT root_path, name FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if not row:
            return
        info = get_git_info(Path(row["root_path"]))
        if info:
            badge = format_git_badge(info)
            self.statusBar().showMessage(f"專案：{row['name']}    {badge}")
        else:
            self.statusBar().showMessage(f"已載入專案：{row['name']}（非 git 目錄）")

    def _open_search(self) -> None:
        dlg = SearchDialog(self._conn, self)
        dlg.exec_()

    def _open_filter(self) -> None:
        dlg = FilterDialog(self._conn, self)
        dlg.exec_()

    def _open_quick_jump(self) -> None:
        dlg = QuickJumpDialog(self._conn, self)
        dlg.exec_()

    def _open_timeline(self) -> None:
        dlg = TimelineDialog(self._conn, self)
        dlg.exec_()

    def _show_project_context_menu(self, pos) -> None:
        item = self._project_list.itemAt(pos)
        if not item:
            return
        pid = item.data(Qt.UserRole)
        current_progress = item.data(Qt.UserRole + 1) or "not_started"
        menu = QMenu(self)
        progress_menu = menu.addMenu("設定進度")
        for state in PROGRESS_STATES:
            act = progress_menu.addAction(PROGRESS_LABELS[state])
            act.setCheckable(True)
            act.setChecked(state == current_progress)
            act.triggered.connect(
                lambda checked, s=state, p=pid: self._set_progress(p, s)
            )
        menu.addSeparator()
        act_roots = menu.addAction("管理根目錄…")
        act_roots.triggered.connect(
            lambda: self._open_roots_dialog(pid)
        )
        act_rel = menu.addAction("管理關聯…")
        act_rel.triggered.connect(
            lambda: self._open_relations_dialog(pid)
        )
        menu.exec_(self._project_list.viewport().mapToGlobal(pos))

    def _open_external_tools_dialog(self) -> None:
        dlg = ExternalToolsDialog(self._conn, self)
        dlg.exec_()

    def _open_backup_dialog(self) -> None:
        dlg = BackupDialog(self._conn, self)
        dlg.exec_()

    def _open_theme_dialog(self) -> None:
        dlg = ThemeDialog(self._conn, self)
        dlg.exec_()

    def _open_export_report_dialog(self) -> None:
        if self._current_project_id is None:
            QMessageBox.information(self, "提示", "請先選擇一個專案。")
            return
        dlg = ExportReportDialog(self._conn, self._current_project_id, self)
        dlg.exec_()

    # ── 工作階段操作 ────────────────────────────────────

    # ── 模式切換 ──────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        """切換操作模式。"""
        # 若從 Realtime 切走且有 active session，先確認
        if (self._mode == MODE_REALTIME and mode != MODE_REALTIME
                and self._session and self._session.active):
            reply = QMessageBox.question(
                self, "切換模式",
                "目前有進行中的工作階段。\n"
                "切換到非即時模式會暫停工作階段操作，但不會取消。\n\n繼續切換？",
            )
            if reply != QMessageBox.Yes:
                # 把按鈕狀態恢復
                self._mode_buttons[self._mode].setChecked(True)
                self._mode_buttons[mode].setChecked(False)
                return

        self._mode = mode
        # 更新按鈕 checked 狀態（確保互斥）
        for k, btn in self._mode_buttons.items():
            btn.setChecked(k == mode)
        self._apply_mode()
        self._update_session_ui()
        self.statusBar().showMessage(
            f"模式：{MODE_LABELS[mode].split(' ', 1)[1]}")

    def _apply_mode(self) -> None:
        """根據當前模式啟用/停用 UI 元件。"""
        is_read = self._mode == MODE_READ
        is_realtime = self._mode == MODE_REALTIME

        # TreeView 拖放
        if is_read:
            self._tree_view.setDragEnabled(False)
            self._tree_view.setAcceptDrops(False)
            self._tree_view.setDragDropMode(QAbstractItemView.NoDragDrop)
        else:
            self._tree_view.setDragEnabled(True)
            self._tree_view.setAcceptDrops(True)
            self._tree_view.setDragDropMode(QAbstractItemView.InternalMove)

        # 工作階段選單
        self._act_start_session.setEnabled(
            is_realtime and self._current_project_id is not None
            and not (self._session and self._session.active)
        )

    def _update_session_ui(self) -> None:
        """更新 session 相關 UI 狀態。"""
        is_realtime = self._mode == MODE_REALTIME
        active = self._session is not None and self._session.active
        self._act_start_session.setEnabled(
            is_realtime and not active
            and self._current_project_id is not None
        )
        self._act_session_history.setEnabled(is_realtime and active)
        self._act_undo_last.setEnabled(is_realtime and active)
        self._act_finalize.setEnabled(is_realtime and active)
        self._act_cancel_session.setEnabled(is_realtime and active)

        if active and is_realtime:
            count = self._session.operation_count()
            self._session_label.setText(f"  🔴 整理中 — {count} 項操作  ")
            self._session_label.setVisible(True)
        else:
            self._session_label.setVisible(False)

    def _start_session(self) -> None:
        if not self._current_project_id:
            QMessageBox.information(self, "提示", "請先選擇一個專案。")
            return
        desc, ok = QInputDialog.getText(
            self, "開始整理", "工作階段描述（可留空）：",
        )
        if not ok:
            return
        self._session = SessionManager(self._conn, self._current_project_id)
        if self._session.active:
            reply = QMessageBox.question(
                self, "已有工作階段",
                "此專案已有進行中的工作階段，要繼續使用嗎？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.No:
                return
        else:
            self._session.start(desc.strip() if ok else "")
        self._update_session_ui()
        self.statusBar().showMessage("工作階段已開始")

    def _undo_last_op(self) -> None:
        if not self._session or not self._session.active:
            return
        ok = self._session.undo_last()
        if ok:
            self.statusBar().showMessage("已復原上一步操作")
            if self._tree_model:
                self._rescan_project()
        else:
            self.statusBar().showMessage("沒有可復原的操作")
        self._update_session_ui()

    def _finalize_session(self) -> None:
        if not self._session or not self._session.active:
            return
        reply = QMessageBox.question(
            self, "確認完成",
            "確認完成此工作階段？\n所有已執行的操作將不可再復原。\n\n"
            "是否同時清空回收桶？",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Cancel:
            return
        self._session.finalize(do_clean_trash=(reply == QMessageBox.Yes))
        self._session = None
        self._update_session_ui()
        self.statusBar().showMessage("工作階段已確認完成")

    def _cancel_session(self) -> None:
        if not self._session or not self._session.active:
            return
        reply = QMessageBox.question(
            self, "取消工作階段",
            "確定要取消？所有已執行的操作都會被復原。",
        )
        if reply != QMessageBox.Yes:
            return
        count = self._session.cancel()
        self._session = None
        self._update_session_ui()
        self.statusBar().showMessage(f"工作階段已取消，復原了 {count} 項操作")
        if self._tree_model:
            self._rescan_project()

    def _open_history_dialog(self) -> None:
        if not self._session or not self._session.active:
            return
        dlg = OperationHistoryDialog(self._session, self)
        dlg.exec_()
        self._update_session_ui()

    def _open_roots_dialog(self, project_id: int) -> None:
        dlg = ProjectRootsDialog(self._conn, project_id, self)
        if dlg.exec_() == QDialog.Accepted:
            self._rescan_project()

    def _open_relations_dialog(self, project_id: int) -> None:
        dlg = ProjectRelationsDialog(self._conn, project_id, self)
        dlg.exec_()

    def _set_progress(self, project_id: int, progress: str) -> None:
        set_project_progress(self._conn, project_id, progress)
        self._load_project_list()
        # 保持原本選取的專案
        for i in range(self._project_list.count()):
            if self._project_list.item(i).data(Qt.UserRole) == project_id:
                self._project_list.setCurrentRow(i)
                break

    def _on_project_selected(self, current: QListWidgetItem,
                              previous: QListWidgetItem) -> None:
        if not current:
            return
        pid = current.data(Qt.UserRole)
        self._current_project_id = pid
        self._tree_model = ProjectTreeModel(self._conn, pid)
        self._tree_view.setModel(self._tree_model)
        self._tree_view.selectionModel().currentChanged.connect(
            self._on_tree_selection_changed
        )
        self._todo_panel.set_project(pid)
        self._refresh_git_status(pid)
        # 檢查是否有 active session
        self._session = SessionManager(self._conn, pid)
        if not self._session.active:
            self._session = None
        self._apply_mode()
        self._update_session_ui()

    # ── 右鍵選單 ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        index = self._tree_view.indexAt(pos)
        menu = QMenu(self)
        is_read = self._mode == MODE_READ
        is_realtime = self._mode == MODE_REALTIME

        if index.isValid():
            node = index.internalPointer()

            # 「開啟」系列：所有模式都可用
            act_open = menu.addAction("在檔案管理器中開啟")
            act_open.triggered.connect(lambda: self._open_in_explorer(node))

            tools = list_tools(self._conn)
            if tools and self._current_project_id:
                resolved = self._resolve_node_path(node)
                if resolved:
                    abs_path = str(resolved)
                    with_menu = menu.addMenu("以…開啟")
                    for tool in tools:
                        act_tool = with_menu.addAction(tool["name"])
                        act_tool.triggered.connect(
                            lambda _=False, t=tool, p=abs_path:
                                self._launch_tool(t, p)
                        )

            # 標籤 / 移除 / 虛擬資料夾：Virtual 和 Realtime 可用
            if not is_read:
                menu.addSeparator()

                tag_menu = menu.addMenu("🏷 標籤")
                all_tags = all_tags_flat(self._conn)
                node_tag_ids = {
                    r["id"] for r in get_node_tags(self._conn, node.db_id)
                }
                if all_tags:
                    for tag in all_tags:
                        act_tag = tag_menu.addAction(tag["name"])
                        act_tag.setCheckable(True)
                        act_tag.setChecked(tag["id"] in node_tag_ids)
                        act_tag.triggered.connect(
                            lambda checked, tid=tag["id"], nid=node.db_id:
                                add_node_tag(self._conn, nid, tid)
                                if checked else
                                remove_node_tag(self._conn, nid, tid)
                        )
                else:
                    tag_menu.addAction("（尚未建立任何標籤）").setEnabled(False)

                menu.addSeparator()

                act_del = menu.addAction("從樹中移除")
                act_del.triggered.connect(lambda: self._delete_tree_node(node))

            # Session 檔案操作：僅 Realtime 模式 + session active
            if is_realtime and self._session and self._session.active:
                menu.addSeparator()
                resolved = self._resolve_node_path(node)
                if resolved:
                    act_move = menu.addAction("📦 移動到…")
                    act_move.triggered.connect(
                        lambda _=False, p=str(resolved), n=node:
                            self._session_move(p, n))

                    act_del_s = menu.addAction("🗑 刪除（移至回收桶）")
                    act_del_s.triggered.connect(
                        lambda _=False, p=str(resolved), n=node:
                            self._session_delete(p, n))

                    act_copy = menu.addAction("📋 複製到…")
                    act_copy.triggered.connect(
                        lambda _=False, p=str(resolved), n=node:
                            self._session_copy(p, n))

                    if node.node_type in ("folder", "virtual"):
                        act_merge = menu.addAction("🔀 合併到…")
                        act_merge.triggered.connect(
                            lambda _=False, p=str(resolved), n=node:
                                self._session_merge(p, n))

        # 新增虛擬資料夾：非 Read 模式
        if not is_read:
            act_new_folder = menu.addAction("新增虛擬資料夾")
            act_new_folder.triggered.connect(
                lambda: self._add_virtual_folder(index if index.isValid() else QModelIndex())
            )

        menu.exec_(self._tree_view.viewport().mapToGlobal(pos))

    def _launch_tool(self, tool, abs_path: str) -> None:
        import subprocess
        p = Path(abs_path)
        tmpl = tool["args_tmpl"] or "{path}"
        arg = tmpl.replace("{path}", str(p)).replace("{dir}", str(
            p.parent if p.is_file() else p
        ))
        try:
            subprocess.Popen([tool["exe_path"]] + arg.split())
        except FileNotFoundError:
            QMessageBox.warning(
                self, "錯誤", f"找不到工具：{tool['exe_path']}"
            )

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

    def _delete_tree_node(self, node) -> None:
        reply = QMessageBox.question(
            self, "確認", f"從樹中移除「{node.name}」？（不影響實際檔案）",
        )
        if reply == QMessageBox.Yes:
            delete_node(self._conn, node.db_id)
            if self._tree_model:
                self._tree_model.refresh()

    # ── Session 檔案操作（右鍵選單觸發）──────────────────

    def _session_move(self, source: str, node) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇目標資料夾")
        if not folder:
            return
        dest = str(Path(folder) / Path(source).name)
        # dry-run 預覽
        rec = self._session.execute_move(source, dest, node.db_id, dry_run=True)
        if not self._confirm_preview("移動", rec):
            return
        rec = self._session.execute_move(source, dest, node.db_id)
        self._handle_op_result("移動", rec)

    def _session_delete(self, source: str, node) -> None:
        rec = self._session.execute_delete(source, node.db_id, dry_run=True)
        if not self._confirm_preview("刪除", rec):
            return
        rec = self._session.execute_delete(source, node.db_id)
        self._handle_op_result("刪除", rec)

    def _session_copy(self, source: str, node) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇目標資料夾")
        if not folder:
            return
        dest = str(Path(folder) / Path(source).name)
        rec = self._session.execute_copy(source, dest, node.db_id, dry_run=True)
        if not self._confirm_preview("複製", rec):
            return
        rec = self._session.execute_copy(source, dest, node.db_id)
        self._handle_op_result("複製", rec)

    def _session_merge(self, source: str, node) -> None:
        folder = QFileDialog.getExistingDirectory(self, "選擇要合併到的資料夾")
        if not folder:
            return
        result = self._session.execute_merge(source, folder, dry_run=True)
        msg = (f"將移動 {len(result.moved)} 個檔案\n"
               f"略過衝突 {len(result.skipped)} 個")
        reply = QMessageBox.question(
            self, "合併預覽", msg + "\n\n確定執行？",
        )
        if reply != QMessageBox.Yes:
            return
        result = self._session.execute_merge(source, folder)
        moved_ok = sum(1 for r in result.moved if r.success)
        self.statusBar().showMessage(
            f"合併完成：移動 {moved_ok} 個，略過 {len(result.skipped)} 個")
        self._update_session_ui()
        if self._tree_model:
            self._rescan_project()

    def _confirm_preview(self, action: str, rec) -> bool:
        """dry-run 預覽確認。"""
        if not rec.success:
            QMessageBox.warning(self, "無法執行", rec.error or "未知錯誤")
            return False
        msg = f"操作：{action}\n來源：{rec.source}"
        if rec.dest:
            msg += f"\n目標：{rec.dest}"
        reply = QMessageBox.question(self, f"{action}預覽", msg + "\n\n確定執行？")
        return reply == QMessageBox.Yes

    def _handle_op_result(self, action: str, rec) -> None:
        """處理操作結果。"""
        if rec.success:
            self.statusBar().showMessage(f"{action}成功")
            self._update_session_ui()
            if self._tree_model:
                self._rescan_project()
        else:
            QMessageBox.warning(self, f"{action}失敗", rec.error or "未知錯誤")

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

    # ── 規則管理 ─────────────────────────────────────────

    def _open_rules_dialog(self) -> None:
        dlg = RulesDialog(self._conn, self)
        dlg.exec_()

    def _open_duplicate_dialog(self) -> None:
        dlg = DuplicateDialog(self._conn, self)
        dlg.exec_()

    def _open_tag_manager(self) -> None:
        dlg = TagManagerDialog(self._conn, self)
        dlg.exec_()

    def _open_template_manager(self) -> None:
        dlg = TemplateManagerDialog(self._conn, self)
        dlg.exec_()

    def _extract_template_from_project(self) -> None:
        # 若有選取中的專案，預填其根路徑
        default_dir = ""
        if self._current_project_id:
            row = self._conn.execute(
                "SELECT root_path FROM projects WHERE id=?",
                (self._current_project_id,),
            ).fetchone()
            if row:
                default_dir = row["root_path"]

        dlg = ExtractTemplateDialog(self._conn, default_dir, self)
        dlg.exec_()

    def _open_batch_rename_dialog(self) -> None:
        if not self._current_project_id:
            QMessageBox.information(self, "提示", "請先選擇一個專案。")
            return
        # 收集目前選取的節點，若無選取則取當前專案所有檔案
        files = []
        selected = self._tree_view.selectedIndexes()
        if selected:
            for idx in selected:
                node = idx.internalPointer()
                if node and node.node_type == "file":
                    resolved = self._resolve_node_path(node)
                    if resolved:
                        files.append({"name": node.name,
                                      "abs_path": str(resolved),
                                      "node_id": node.db_id})
        if not files:
            rows = self._conn.execute(
                "SELECT id, name FROM nodes "
                "WHERE project_id=? AND node_type='file' ORDER BY name",
                (self._current_project_id,),
            ).fetchall()
            for r in rows:
                abs_p = get_node_abs_path(self._conn, r["id"])
                if abs_p:
                    files.append({
                        "name": r["name"],
                        "abs_path": str(abs_p),
                        "node_id": r["id"],
                    })
        dlg = BatchRenameDialog(files, self._conn,
                                self._current_project_id, self)
        if dlg.exec_() == QDialog.Accepted and self._tree_model:
            self._tree_model.refresh()


