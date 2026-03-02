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
)

from database import (
    get_connection, init_db, create_project, list_projects,
    delete_project, delete_node,
    PROGRESS_LABELS, PROGRESS_STATES, set_project_progress,
    list_todos, add_todo, toggle_todo, delete_todo,
    get_timeline,
)
from rule_engine import list_rules, add_rule, update_rule, delete_rule
from duplicate_finder import find_duplicates
from batch_rename import build_previews, execute_renames
from git_utils import get_git_info, format_git_badge
from templates import (
    get_builtin_templates, list_templates, save_template,
    delete_template, scaffold, export_template, import_template,
    project_to_template,
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

        tools_menu.addSeparator()
        act_tmpl_mgr = QAction("管理自訂模板(&M)…", self)
        act_tmpl_mgr.triggered.connect(self._open_template_manager)
        tools_menu.addAction(act_tmpl_mgr)

        act_extract = QAction("從現有專案建立模板(&E)…", self)
        act_extract.triggered.connect(self._extract_template_from_project)
        tools_menu.addAction(act_extract)

        view_menu = menu.addMenu("檢視(&V)")
        act_timeline = QAction("時間軸(&T)…", self)
        act_timeline.triggered.connect(self._open_timeline)
        view_menu.addAction(act_timeline)
        view_menu.addSeparator()
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
        menu.exec_(self._project_list.viewport().mapToGlobal(pos))

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
        self._todo_panel.set_project(pid)
        self._refresh_git_status(pid)

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

    # ── 規則管理 ─────────────────────────────────────────

    def _open_rules_dialog(self) -> None:
        dlg = RulesDialog(self._conn, self)
        dlg.exec_()

    def _open_duplicate_dialog(self) -> None:
        dlg = DuplicateDialog(self._conn, self)
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
        row = self._conn.execute(
            "SELECT root_path FROM projects WHERE id=?",
            (self._current_project_id,),
        ).fetchone()
        if not row:
            return
        # 收集目前選取的節點，若無選取則取當前專案所有檔案
        files = []
        selected = self._tree_view.selectedIndexes()
        root_path = row["root_path"]
        if selected:
            for idx in selected:
                node = idx.internalPointer()
                if node and node.node_type == "file":
                    abs_path = str(Path(root_path) / node.rel_path)
                    files.append({"name": node.name, "abs_path": abs_path,
                                  "node_id": node.db_id})
        if not files:
            # 取當前專案所有檔案
            rows = self._conn.execute(
                "SELECT id, name, rel_path FROM nodes "
                "WHERE project_id=? AND node_type='file' ORDER BY name",
                (self._current_project_id,),
            ).fetchall()
            for r in rows:
                files.append({
                    "name": r["name"],
                    "abs_path": str(Path(root_path) / r["rel_path"]),
                    "node_id": r["id"],
                })
        dlg = BatchRenameDialog(files, self._conn,
                                self._current_project_id, self)
        if dlg.exec_() == QDialog.Accepted and self._tree_model:
            self._tree_model.refresh()


# ────────────────────────────────────────────────────────────────
# 規則管理對話框
# ────────────────────────────────────────────────────────────────

CATEGORIES = ["image", "video", "audio", "code", "document",
              "archive", "data", "font", "3d", "other"]


class RulesDialog(QDialog):
    """檢視、新增、刪除自訂分類規則."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("自訂分類規則")
        self.resize(720, 400)
        self._build_ui()
        self._load_rules()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["名稱", "模式", "類型", "比對目標", "分類", "啟用"]
        )
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("＋ 新增規則")
        btn_add.clicked.connect(self._add_rule)
        btn_del = QPushButton("－ 刪除規則")
        btn_del.clicked.connect(self._delete_rule)
        btn_toggle = QPushButton("啟用 / 停用")
        btn_toggle.clicked.connect(self._toggle_rule)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_toggle)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load_rules(self) -> None:
        self._rules = list_rules(self._conn)
        self._table.setRowCount(0)
        for rule in self._rules:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(rule.name))
            self._table.setItem(r, 1, QTableWidgetItem(rule.pattern))
            self._table.setItem(r, 2, QTableWidgetItem(rule.pattern_type))
            self._table.setItem(r, 3, QTableWidgetItem(rule.match_target))
            self._table.setItem(r, 4, QTableWidgetItem(rule.category))
            enabled_item = QTableWidgetItem("✔" if rule.enabled else "✘")
            enabled_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(r, 5, enabled_item)

    def _add_rule(self) -> None:
        dlg = RuleEditDialog(self._conn, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._load_rules()

    def _delete_rule(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        rule = self._rules[row]
        reply = QMessageBox.question(self, "確認", f"刪除規則「{rule.name}」？")
        if reply == QMessageBox.Yes:
            delete_rule(self._conn, rule.id)
            self._load_rules()

    def _toggle_rule(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        rule = self._rules[row]
        update_rule(self._conn, rule.id, enabled=0 if rule.enabled else 1)
        self._load_rules()


class RuleEditDialog(QDialog):
    """新增規則對話框."""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("新增分類規則")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._name = QLineEdit()
        self._name.setPlaceholderText("例：忽略暫存檔")
        layout.addRow("名稱：", self._name)

        self._pattern = QLineEdit()
        self._pattern.setPlaceholderText("例：*.tmp  或  ^test_.*\\.py$")
        layout.addRow("模式：", self._pattern)

        self._ptype = QComboBox()
        self._ptype.addItems(["glob", "regex"])
        layout.addRow("模式類型：", self._ptype)

        self._target = QComboBox()
        self._target.addItems(["name", "path"])
        layout.addRow("比對目標：", self._target)

        self._category = QComboBox()
        self._category.addItems(CATEGORIES)
        layout.addRow("分類：", self._category)

        self._priority = QSpinBox()
        self._priority.setRange(1, 999)
        self._priority.setValue(100)
        layout.addRow("優先度（小優先）：", self._priority)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self) -> None:
        name = self._name.text().strip()
        pattern = self._pattern.text().strip()
        if not name or not pattern:
            QMessageBox.warning(self, "缺少資料", "名稱與模式不可空白。")
            return
        add_rule(
            self._conn,
            name=name,
            pattern=pattern,
            pattern_type=self._ptype.currentText(),
            match_target=self._target.currentText(),
            category=self._category.currentText(),
            priority=self._priority.value(),
        )
        self.accept()


# ────────────────────────────────────────────────────────────────
# 重複檔案偵測對話框
# ────────────────────────────────────────────────────────────────

class DuplicateDialog(QDialog):
    """偵測並顯示重複檔案群組，支援在檔案管理器中開啟。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("重複檔案偵測")
        self.resize(860, 500)
        self._groups: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._btn_scan = QPushButton("🔍 開始掃描（所有專案）")
        self._btn_scan.clicked.connect(self._scan)
        self._lbl_status = QLabel("尚未掃描")
        top.addWidget(self._btn_scan)
        top.addWidget(self._lbl_status)
        top.addStretch()
        layout.addLayout(top)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["檔名", "大小", "專案", "相對路徑"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_open = QPushButton("在檔案管理器中開啟")
        btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(btn_open)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _scan(self) -> None:
        self._btn_scan.setEnabled(False)
        self._lbl_status.setText("掃描中…")
        self._table.setRowCount(0)
        groups = find_duplicates(self._conn)
        self._on_scan_done(groups)

    def _on_scan_done(self, groups) -> None:
        self._groups = groups
        self._table.setRowCount(0)
        for group in groups:
            # 群組分隔行（顯示 hash 與大小）
            sep_row = self._table.rowCount()
            self._table.insertRow(sep_row)
            size_str = self._fmt_size(group.file_size)
            sep_item = QTableWidgetItem(
                f"▶ {len(group.files)} 個重複  ({size_str} each)  MD5: {group.file_hash}"
            )
            sep_item.setBackground(Qt.darkGray)
            self._table.setItem(sep_row, 0, sep_item)
            self._table.setSpan(sep_row, 0, 1, 4)

            for f in group.files:
                r = self._table.rowCount()
                self._table.insertRow(r)
                name = Path(f["rel_path"]).name
                self._table.setItem(r, 0, QTableWidgetItem(name))
                self._table.setItem(r, 1, QTableWidgetItem(self._fmt_size(f["file_size"])))
                self._table.setItem(r, 2, QTableWidgetItem(f["project_name"]))
                item_path = QTableWidgetItem(f["rel_path"])
                item_path.setData(Qt.UserRole, f["abs_path"])
                self._table.setItem(r, 3, item_path)

        total = sum(len(g.files) - 1 for g in groups)
        self._lbl_status.setText(
            f"找到 {len(groups)} 組重複，共 {total} 個多餘複本"
            if groups else "未發現重複檔案"
        )
        self._btn_scan.setEnabled(True)

    def _open_selected(self) -> None:
        import subprocess, sys
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 3)
        if not item:
            return
        abs_path = item.data(Qt.UserRole)
        if not abs_path:
            return
        p = Path(abs_path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p.parent)])

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size >= 1_048_576:
            return f"{size / 1_048_576:.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size} B"


# ────────────────────────────────────────────────────────────────
# 批次重新命名對話框
# ────────────────────────────────────────────────────────────────

class BatchRenameDialog(QDialog):
    """批次重新命名：樣板、前後綴、序號、regex 替換，含即時預覽。"""

    def __init__(self, files: list, conn, project_id: int, parent=None):
        super().__init__(parent)
        self._files = files
        self._conn = conn
        self._project_id = project_id
        self.setWindowTitle(f"批次重新命名（{len(files)} 個檔案）")
        self.resize(800, 540)
        self._build_ui()
        self._refresh_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._template = QLineEdit("{stem}{ext}")
        self._template.setPlaceholderText("{stem}  {ext}  {n}  {n:03}")
        self._template.textChanged.connect(self._refresh_preview)
        form.addRow("樣板：", self._template)

        self._prefix = QLineEdit()
        self._prefix.textChanged.connect(self._refresh_preview)
        form.addRow("前綴：", self._prefix)

        self._suffix = QLineEdit()
        self._suffix.textChanged.connect(self._refresh_preview)
        form.addRow("後綴：", self._suffix)

        row_n = QHBoxLayout()
        self._start = QSpinBox(); self._start.setRange(0, 9999); self._start.setValue(1)
        self._step  = QSpinBox(); self._step.setRange(1, 100);   self._step.setValue(1)
        self._start.valueChanged.connect(self._refresh_preview)
        self._step.valueChanged.connect(self._refresh_preview)
        row_n.addWidget(QLabel("起始序號："))
        row_n.addWidget(self._start)
        row_n.addWidget(QLabel("  間距："))
        row_n.addWidget(self._step)
        row_n.addStretch()
        form.addRow(row_n)

        self._regex_find = QLineEdit()
        self._regex_find.setPlaceholderText("Regex 搜尋（留空不套用）")
        self._regex_find.textChanged.connect(self._refresh_preview)
        form.addRow("Regex 搜尋：", self._regex_find)

        self._regex_replace = QLineEdit()
        self._regex_replace.textChanged.connect(self._refresh_preview)
        form.addRow("Regex 替換：", self._regex_replace)

        layout.addLayout(form)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["原始名稱", "新名稱（預覽）"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self._table)

        self._lbl_info = QLabel("")
        layout.addWidget(self._lbl_info)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("執行重新命名")
        btns.accepted.connect(self._execute)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _refresh_preview(self) -> None:
        from PySide6.QtGui import QColor
        previews = build_previews(
            self._files,
            template=self._template.text() or "{stem}{ext}",
            prefix=self._prefix.text(),
            suffix=self._suffix.text(),
            regex_find=self._regex_find.text(),
            regex_replace=self._regex_replace.text(),
            start=self._start.value(),
            step=self._step.value(),
        )
        self._previews = previews
        self._table.setRowCount(0)
        changes = 0
        for pv in previews:
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(pv.original))
            new_item = QTableWidgetItem(pv.new_name)
            if pv.conflict:
                new_item.setForeground(QColor("#f38ba8"))  # 紅色警示
            elif pv.new_name != pv.original:
                new_item.setForeground(QColor("#a6e3a1"))  # 綠色
                changes += 1
            self._table.setItem(r, 1, new_item)
        conflicts = sum(1 for p in previews if p.conflict)
        self._lbl_info.setText(
            f"將重新命名 {changes} 個檔案" +
            (f"　⚠ {conflicts} 個衝突（紅色標示，將略過）" if conflicts else "")
        )

    def _execute(self) -> None:
        if not hasattr(self, "_previews"):
            return
        reply = QMessageBox.question(
            self, "確認", f"確定要重新命名這些檔案？此操作無法自動還原。"
        )
        if reply != QMessageBox.Yes:
            return
        success, errors = execute_renames(self._previews)
        # 同步更新資料庫中的節點名稱
        for pv in self._previews:
            if not pv.conflict and pv.new_name != pv.original:
                self._conn.execute(
                    "UPDATE nodes SET name=?, rel_path=REPLACE(rel_path, ?, ?) "
                    "WHERE project_id=? AND name=?",
                    (pv.new_name, pv.original, pv.new_name,
                     self._project_id, pv.original),
                )
        self._conn.commit()
        msg = f"完成：{success} 個檔案已重新命名。"
        if errors:
            msg += f"\n\n錯誤（{len(errors)} 個）：\n" + "\n".join(errors[:10])
        QMessageBox.information(self, "完成", msg)
        self.accept()


# ────────────────────────────────────────────────────────────────
# 從現有專案反推模板對話框
# ────────────────────────────────────────────────────────────────

class ExtractTemplateDialog(QDialog):
    """選擇目錄，反推成模板後存入 DB 或匯出 JSON。"""

    def __init__(self, conn, default_dir: str = "", parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("從現有專案建立模板")
        self.resize(560, 360)
        self._build_ui(default_dir)

    def _build_ui(self, default_dir: str) -> None:
        layout = QFormLayout(self)

        row_dir = QHBoxLayout()
        self._dir_edit = QLineEdit(default_dir)
        btn_browse = QPushButton("…")
        btn_browse.setMaximumWidth(32)
        btn_browse.clicked.connect(self._browse)
        row_dir.addWidget(self._dir_edit)
        row_dir.addWidget(btn_browse)
        layout.addRow("來源目錄：", row_dir)

        self._name = QLineEdit()
        if default_dir:
            self._name.setText(Path(default_dir).name)
        layout.addRow("模板名稱：", self._name)

        self._desc = QLineEdit()
        layout.addRow("說明：", self._desc)

        self._cat = QComboBox()
        self._cat.addItems(["general", "python", "web", "rust", "unity",
                             "nodejs", "other"])
        layout.addRow("類別：", self._cat)

        self._depth = QSpinBox()
        self._depth.setRange(1, 8)
        self._depth.setValue(4)
        layout.addRow("最大深度：", self._depth)

        btns = QDialogButtonBox()
        btn_save = btns.addButton("儲存為自訂模板", QDialogButtonBox.AcceptRole)
        btn_export = btns.addButton("匯出 JSON", QDialogButtonBox.ActionRole)
        btn_cancel = btns.addButton(QDialogButtonBox.Cancel)
        btn_save.clicked.connect(self._save_to_db)
        btn_export.clicked.connect(self._export_json)
        btn_cancel.clicked.connect(self.reject)
        layout.addRow(btns)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇來源目錄")
        if d:
            self._dir_edit.setText(d)
            if not self._name.text():
                self._name.setText(Path(d).name)

    def _extract(self):
        src = self._dir_edit.text().strip()
        name = self._name.text().strip()
        if not src or not name:
            QMessageBox.warning(self, "缺少資料", "請填寫來源目錄與模板名稱。")
            return None
        root = Path(src)
        if not root.is_dir():
            QMessageBox.warning(self, "錯誤", f"目錄不存在：{src}")
            return None
        return project_to_template(
            root=root, name=name,
            description=self._desc.text().strip(),
            category=self._cat.currentText(),
            max_depth=self._depth.value(),
        )

    def _save_to_db(self) -> None:
        tmpl = self._extract()
        if tmpl is None:
            return
        save_template(self._conn, tmpl)
        QMessageBox.information(
            self, "完成", f"已儲存模板「{tmpl.name}」（{len(tmpl.entries)} 個項目）"
        )
        self.accept()

    def _export_json(self) -> None:
        tmpl = self._extract()
        if tmpl is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出模板", f"{tmpl.name}.json", "JSON (*.json)"
        )
        if path:
            Path(path).write_text(export_template(tmpl), encoding="utf-8")
            QMessageBox.information(self, "完成", f"已匯出至 {path}")


# ────────────────────────────────────────────────────────────────
# 自訂模板管理對話框
# ────────────────────────────────────────────────────────────────

class TemplateManagerDialog(QDialog):
    """管理使用者自訂模板：新增、匯出、匯入、刪除。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("管理自訂模板")
        self.resize(680, 420)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("＋ 新增", self._new_template),
            ("匯出 JSON", self._export),
            ("匯入 JSON", self._import),
            ("－ 刪除", self._delete),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(120)
        layout.addWidget(self._preview)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _load(self) -> None:
        self._templates = list_templates(self._conn, include_builtin=False)
        self._list.clear()
        for t in self._templates:
            self._list.addItem(f"[{t.category}] {t.name}")

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            self._preview.clear()
            return
        t = self._templates[row]
        lines = [f"{t.name}  ({t.category})", t.description, ""]
        for e in t.entries:
            lines.append(("📁 " if e.is_dir else "📄 ") + e.path)
        self._preview.setPlainText("\n".join(lines))

    def _new_template(self) -> None:
        dlg = TemplateEditDialog(self._conn, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._load()

    def _export(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        tmpl = self._templates[row]
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出模板", f"{tmpl.name}.json", "JSON (*.json)"
        )
        if path:
            Path(path).write_text(export_template(tmpl), encoding="utf-8")
            QMessageBox.information(self, "完成", f"已匯出至 {path}")

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "匯入模板", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            json_str = Path(path).read_text(encoding="utf-8")
            tmpl = import_template(json_str)
        except Exception as e:
            QMessageBox.warning(self, "匯入失敗", str(e))
            return
        save_template(self._conn, tmpl)
        self._load()
        QMessageBox.information(self, "完成", f"已匯入模板「{tmpl.name}」")

    def _delete(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        tmpl = self._templates[row]
        reply = QMessageBox.question(self, "確認", f"刪除模板「{tmpl.name}」？")
        if reply == QMessageBox.Yes:
            delete_template(self._conn, tmpl.id)
            self._load()


class TemplateEditDialog(QDialog):
    """新增自訂模板對話框（手動輸入路徑清單）。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("新增自訂模板")
        self.resize(560, 440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self._name = QLineEdit()
        layout.addRow("名稱：", self._name)

        self._desc = QLineEdit()
        layout.addRow("說明：", self._desc)

        self._cat = QComboBox()
        self._cat.addItems(["general", "python", "web", "rust", "unity",
                             "nodejs", "other"])
        layout.addRow("類別：", self._cat)

        self._entries = QTextEdit()
        self._entries.setPlaceholderText(
            "每行一個路徑，目錄結尾加 /\n"
            "例：\n"
            "src/\n"
            "src/main.py\n"
            "README.md"
        )
        layout.addRow("目錄/檔案清單：", self._entries)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self) -> None:
        from templates import ProjectTemplate, TemplateEntry
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "缺少資料", "名稱不可空白。")
            return
        entries = []
        for line in self._entries.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            is_dir = line.endswith("/")
            path = line.rstrip("/")
            entries.append(TemplateEntry(path=path, is_dir=is_dir))
        tmpl = ProjectTemplate(
            name=name,
            description=self._desc.text().strip(),
            category=self._cat.currentText(),
            entries=entries,
        )
        save_template(self._conn, tmpl)
        self.accept()


# ────────────────────────────────────────────────────────────────
# 模板選擇 & 建立專案對話框
# ────────────────────────────────────────────────────────────────

class TemplatePickerDialog(QDialog):
    """從模板清單選擇，指定目標目錄，scaffold 並建立專案。"""

    def __init__(self, templates, conn, parent=None):
        super().__init__(parent)
        self._templates = templates
        self._conn = conn
        self.created_project_id: int | None = None
        self.setWindowTitle("從模板新增專案")
        self.resize(680, 440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        # 左：模板清單
        left = QVBoxLayout()
        left.addWidget(QLabel("選擇模板："))
        self._list = QListWidget()
        for tmpl in self._templates:
            tag = "⭐" if tmpl.is_builtin else "🔧"
            item = QListWidgetItem(f"{tag} {tmpl.name}")
            item.setToolTip(tmpl.description)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_select)
        left.addWidget(self._list)
        layout.addLayout(left, 1)

        # 右：詳情 + 設定
        right = QVBoxLayout()
        self._lbl_desc = QLabel("（選擇模板以查看說明）")
        self._lbl_desc.setWordWrap(True)
        right.addWidget(self._lbl_desc)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(160)
        right.addWidget(self._preview)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        form.addRow("專案名稱：", self._name_edit)
        row_dir = QHBoxLayout()
        self._dir_edit = QLineEdit()
        btn_browse = QPushButton("…")
        btn_browse.setMaximumWidth(32)
        btn_browse.clicked.connect(self._browse_dir)
        row_dir.addWidget(self._dir_edit)
        row_dir.addWidget(btn_browse)
        form.addRow("目標目錄：", row_dir)
        right.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("建立專案")
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        right.addWidget(btns)

        layout.addLayout(right, 2)

        if self._templates:
            self._list.setCurrentRow(0)

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._templates):
            return
        tmpl = self._templates[row]
        self._lbl_desc.setText(f"[{tmpl.category}]  {tmpl.description}")
        lines = []
        for e in tmpl.entries:
            prefix = "📁" if e.is_dir else "📄"
            lines.append(f"{prefix} {e.path}")
        self._preview.setPlainText("\n".join(lines))

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "選擇父目錄")
        if d:
            self._dir_edit.setText(d)

    def _create(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "請選擇一個模板。")
            return
        tmpl = self._templates[row]
        name = self._name_edit.text().strip() or tmpl.name
        parent_dir = self._dir_edit.text().strip()
        if not parent_dir:
            QMessageBox.warning(self, "提示", "請指定目標目錄。")
            return
        target = Path(parent_dir) / name
        if target.exists():
            reply = QMessageBox.question(
                self, "目錄已存在",
                f"目錄 {target} 已存在，仍要繼續嗎？（不會刪除現有檔案）",
            )
            if reply != QMessageBox.Yes:
                return

        created, errors = scaffold(tmpl, target)
        if errors:
            QMessageBox.warning(self, "建立警告",
                                f"部分項目建立失敗：\n" + "\n".join(errors[:5]))

        from database import create_project
        from scanner import scan_directory
        try:
            pid = create_project(self._conn, name, str(target))
        except Exception as e:
            QMessageBox.warning(self, "錯誤", f"無法建立專案記錄：{e}")
            return

        count = scan_directory(self._conn, pid, target)
        self._conn.commit()
        self.created_project_id = pid
        QMessageBox.information(
            self, "完成",
            f"已建立專案「{name}」\n目錄：{target}\n建立 {created} 個項目，掃描 {count} 個節點。",
        )
        self.accept()


# ────────────────────────────────────────────────────────────────
# 時間軸視圖
# ────────────────────────────────────────────────────────────────

_PROGRESS_COLORS = {
    "not_started": "#6c7086",
    "in_progress": "#89b4fa",
    "paused":      "#f9e2af",
    "completed":   "#a6e3a1",
}


class TimelineWidget(QWidget):
    """自繪時間軸：每個專案一條橫列，顏色代表進度。"""

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self._rows = rows
        self.setMinimumHeight(max(120, len(rows) * 48 + 40))

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QColor, QFont, QPen
        from PySide6.QtCore import QRectF
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        W = self.width()
        row_h = 44
        margin_left = 160
        margin_right = 20
        track_y = 28

        if not self._rows:
            painter.drawText(20, 40, "尚無專案資料")
            return

        # 時間範圍
        from datetime import datetime
        def _dt(s: str) -> datetime:
            return datetime.fromisoformat(s[:19])

        times = [_dt(r["created_at"]) for r in self._rows]
        t_min, t_max = min(times), max(times)
        span = max((t_max - t_min).total_seconds(), 1)

        def _x(dt: datetime) -> float:
            frac = (dt - t_min).total_seconds() / span
            return margin_left + frac * (W - margin_left - margin_right)

        # 主軸線
        axis_y = track_y + len(self._rows) * row_h // 2
        painter.setPen(QPen(QColor("#45475a"), 2))
        painter.drawLine(margin_left, axis_y, W - margin_right, axis_y)

        for i, row in enumerate(self._rows):
            y = track_y + i * row_h
            cx = _x(_dt(row["created_at"]))
            progress = row["progress"] or "not_started"
            color = QColor(_PROGRESS_COLORS.get(progress, "#6c7086"))

            # 專案名稱（左側）
            painter.setPen(QColor("#cdd6f4"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            name = row["name"]
            if len(name) > 18:
                name = name[:17] + "…"
            painter.drawText(4, y + 16, name)

            # 進度標籤
            badge = PROGRESS_LABELS.get(progress, progress)
            painter.setPen(color)
            font2 = QFont(font)
            font2.setPointSize(8)
            painter.setFont(font2)
            painter.drawText(4, y + 30, badge)

            # 節點圓圈
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#1e1e2e"), 1))
            painter.drawEllipse(int(cx) - 7, y + 6, 14, 14)

            # todo 進度條（節點右側）
            total = row["todo_total"] or 0
            done  = row["todo_done"] or 0
            if total:
                bar_x = int(cx) + 10
                bar_w = min(60, W - bar_x - margin_right)
                bar_h = 6
                bar_y = y + 12
                painter.setBrush(QColor("#313244"))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 3, 3)
                fill_w = int(bar_w * done / total)
                painter.setBrush(QColor("#a6e3a1"))
                painter.drawRoundedRect(bar_x, bar_y, fill_w, bar_h, 3, 3)
                painter.setPen(QColor("#a6adc8"))
                painter.setFont(font2)
                painter.drawText(bar_x + bar_w + 4, bar_y + bar_h,
                                 f"{done}/{total}")


class TimelineDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.setWindowTitle("專案時間軸")
        self.resize(760, 460)
        rows = get_timeline(conn)
        layout = QVBoxLayout(self)
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = TimelineWidget(rows)
        scroll.setWidget(widget)
        layout.addWidget(scroll)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


# ────────────────────────────────────────────────────────────────
# TODO 面板（嵌入左側欄）
# ────────────────────────────────────────────────────────────────

class TodoPanel(QWidget):
    """顯示當前專案的 TODO 清單，支援新增、勾選、刪除。"""

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._project_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("TODO"))
        hdr.addStretch()
        btn_add = QPushButton("＋")
        btn_add.setMaximumWidth(28)
        btn_add.setToolTip("新增 TODO")
        btn_add.clicked.connect(self._add_item)
        hdr.addWidget(btn_add)
        layout.addLayout(hdr)

        self._list = QListWidget()
        self._list.setMaximumHeight(140)
        self._list.itemChanged.connect(self._on_check_changed)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self._list)

    def set_project(self, project_id: int | None) -> None:
        self._project_id = project_id
        self._refresh()

    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._project_id is None:
            self._list.blockSignals(False)
            return
        for row in list_todos(self._conn, self._project_id):
            item = QListWidgetItem(row["title"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if row["done"] else Qt.Unchecked)
            item.setData(Qt.UserRole, row["id"])
            if row["done"]:
                from PySide6.QtGui import QColor
                item.setForeground(QColor("#6c7086"))
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_check_changed(self, item: QListWidgetItem) -> None:
        todo_id = item.data(Qt.UserRole)
        if todo_id is not None:
            toggle_todo(self._conn, todo_id)
            self._refresh()

    def _add_item(self) -> None:
        if self._project_id is None:
            return
        title, ok = QInputDialog.getText(self, "新增 TODO", "內容：")
        if ok and title.strip():
            add_todo(self._conn, self._project_id, title.strip())
            self._refresh()

    def _ctx_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_del = menu.addAction("刪除")
        act_del.triggered.connect(lambda: self._delete_item(item))
        menu.exec_(self._list.viewport().mapToGlobal(pos))

    def _delete_item(self, item: QListWidgetItem) -> None:
        todo_id = item.data(Qt.UserRole)
        if todo_id is not None:
            delete_todo(self._conn, todo_id)
            self._refresh()
