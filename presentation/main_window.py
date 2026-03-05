"""主視窗 — 組合所有 mixin，負責 UI 骨架建構。"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QTreeView, QListWidget,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QAbstractItemView, QMessageBox,
)

from database import get_connection, init_db
from presentation.tree_model import ProjectTreeModel
from domain.enums import (
    MODE_READ, MODE_VIRTUAL, MODE_REALTIME,
    MODE_LABELS, MODE_TOOLTIPS, MODE_COLORS,
)
from application.mode_controller import ModeController

from presentation.widgets.metadata_panel import MetadataPanel
from presentation.widgets.dual_panel import _TreePanel
from presentation.widgets.flat_search import FlatSearchWidget
from presentation.widgets.folder_panel import FolderPanel

# ── Mixin imports ──────────────────────────────────────
from presentation.mixins.project_mixin import ProjectMixin, _ScanWorker
from presentation.mixins.tree_ops_mixin import TreeOpsMixin
from presentation.mixins.virtual_mode_mixin import VirtualModeMixin
from presentation.mixins.mode_mixin import ModeMixin
from presentation.mixins.context_menu_mixin import ContextMenuMixin
from presentation.mixins.navigation_mixin import NavigationMixin


class MainWindow(
    ProjectMixin,
    TreeOpsMixin,
    VirtualModeMixin,
    ModeMixin,
    ContextMenuMixin,
    NavigationMixin,
    QMainWindow,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Organizer")
        self.resize(1100, 700)
        import sys
        if "--maximized" in sys.argv:
            self.showMaximized()

        self._conn = get_connection()
        init_db(self._conn)
        self._current_project_id: int | None = None
        self._current_root_id: int | None = None
        self._tree_model: ProjectTreeModel | None = None
        self._controller = ModeController()
        self._controller.set_mode(MODE_VIRTUAL)
        self._rel_path_to_db_id: dict[str, int] = {}
        self._last_snapshot: list[dict] = []
        self._scan_worker: _ScanWorker | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(50)
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
        left_layout.setContentsMargins(0, 4, 0, 0)
        left_layout.setSpacing(0)

        left_layout.addWidget(QLabel("專案"))

        self._project_list = QListWidget()
        self._project_list.currentItemChanged.connect(self._on_project_selected)
        self._project_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._project_list.customContextMenuRequested.connect(
            self._show_project_context_menu
        )
        left_layout.addWidget(self._project_list)

        btn_add = QPushButton("＋  新增專案")
        btn_add.setFixedHeight(32)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-top: 1px solid #2e2e36;
                border-radius: 0;
                color: #a0a0af;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 0.08em;
                padding: 0;
            }
            QPushButton:hover {
                color: #d4a054;
                border-top: 1px solid #d4a054;
                background-color: rgba(212, 160, 84, 0.06);
            }
            QPushButton:pressed {
                color: #e0c08a;
                background-color: rgba(212, 160, 84, 0.12);
            }
        """)
        btn_add.clicked.connect(self._add_project)
        left_layout.addWidget(btn_add)

        left.setMinimumWidth(140)
        left.setMaximumWidth(200)

        # ── 專案面板收合長條按鈕（放在第一層右側） ──
        from presentation.file_icons import get_category_icon
        from PySide6.QtWidgets import QSizePolicy
        self._btn_toggle_left = QPushButton()
        self._btn_toggle_left.setIcon(get_category_icon("chevron_left"))
        self._btn_toggle_left.setToolTip("顯示/隱藏專案面板")
        self._btn_toggle_left.setFixedWidth(14)
        self._btn_toggle_left.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding,
        )
        self._btn_toggle_left.setStyleSheet(
            "QPushButton { border: none; border-radius: 0px; padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,0.06); }"
        )
        self._btn_toggle_left.clicked.connect(self._toggle_left_panel)

        # 用水平容器包住專案清單 + 收合按鈕
        left_wrapper = QWidget()
        left_wrapper_layout = QHBoxLayout(left_wrapper)
        left_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        left_wrapper_layout.setSpacing(0)
        left_wrapper_layout.addWidget(left)
        left_wrapper_layout.addWidget(self._btn_toggle_left)
        left_wrapper.setFixedWidth(194)

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

        _tb_btn_style = (
            "QPushButton { border: none; border-radius: 4px; font-size: 14px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.1); }"
        )

        btn_mkdir = QPushButton()
        btn_mkdir.setIcon(get_category_icon("folder_add"))
        btn_mkdir.setToolTip("新增資料夾")
        btn_mkdir.setFixedSize(24, 24)
        btn_mkdir.setStyleSheet(_tb_btn_style)
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

        # ── 中間面板：專案資料夾 ──
        self._folder_panel = FolderPanel(self._conn, parent=self)
        self._folder_panel.folder_selected.connect(self._on_folder_selected)
        self._folder_panel.scan_requested.connect(self._on_folder_scan_requested)
        self._folder_panel.setFixedWidth(180)

        self._left_panel = left
        self._left_wrapper = left_wrapper

        # L1, L2 固定寬度 → 不放進 splitter；splitter 只管動態面板
        splitter.addWidget(tree_container)
        splitter.addWidget(self._panel_b)
        splitter.addWidget(self._meta_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setCollapsible(0, False)
        splitter.setSizes([1, 0, 0])

        # 外層水平佈局：L1(固定) | L2(固定) | splitter(彈性)
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(left_wrapper)
        central_layout.addWidget(self._folder_panel)
        central_layout.addWidget(splitter, 1)

        self.setCentralWidget(central)

        # 虛擬模式操作按鈕（套用 / 放棄）
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

    # ── 選單列 ───────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("檔案(&F)")
        act_add = QAction("新增專案(&N)", self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self._add_project)
        file_menu.addAction(act_add)

        act_restart = QAction("重新啟動(&R)", self)
        act_restart.setShortcut(QKeySequence("Ctrl+Shift+R"))
        act_restart.triggered.connect(self._restart_app)
        file_menu.addAction(act_restart)

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

        view_menu = menu.addMenu("檢視(&V)")
        act_refresh = QAction("重新整理(&R)", self)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self._rescan_project)
        view_menu.addAction(act_refresh)

        act_toggle_left = QAction("專案面板(&P)", self)
        act_toggle_left.setShortcut(QKeySequence("Ctrl+`"))
        act_toggle_left.setCheckable(True)
        act_toggle_left.setChecked(True)
        act_toggle_left.triggered.connect(self._toggle_left_panel)
        view_menu.addAction(act_toggle_left)

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

        # ── 模式選單 ──
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

    # ── 面板切換（行數少，留在主檔案）─────────────────────

    def _on_tree_selection_changed(self, current, previous) -> None:
        if not current.isValid():
            return
        node = self._node_from_index(current)
        if node and self._meta_panel.isVisible():
            self._meta_panel.load_node(node.db_id, self._current_project_id)

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

    def _toggle_left_panel(self) -> None:
        """切換左側專案面板的顯示/隱藏。"""
        from presentation.file_icons import get_category_icon
        visible = not self._left_panel.isVisible()
        self._left_panel.setVisible(visible)
        icon_name = "chevron_left" if visible else "chevron_right"
        self._btn_toggle_left.setIcon(get_category_icon(icon_name))
        if visible:
            self._left_wrapper.setFixedWidth(194)
        else:
            self._left_wrapper.setFixedWidth(14)

    def _restart_app(self) -> None:
        """關閉目前視窗並重新啟動整個應用程式（最大化）。"""
        import os, sys
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()
        args = [sys.executable] + sys.argv
        if "--maximized" not in args:
            args.append("--maximized")
        os.execv(sys.executable, args)
