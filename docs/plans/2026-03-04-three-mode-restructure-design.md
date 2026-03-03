# 三模式架構重構設計

> 日期：2026-03-04
> 狀態：已核准，待實作
> 方案：漸進式重構（方案 A）

## 核心定位

檔案整理工具，不是專案管理工具。核心流程：

> 瀏覽檔案結構 → 在虛擬模式中規劃操作 → 確認後批次套用 → 或在即時模式中直接操作

---

## §1 模式語意

### 預覽 (Preview)

純唯讀。樹狀反映真實檔案系統。不能拖放、不能刪除、不能重命名。用途：瀏覽結構、看大小/時間、搜尋/篩選。

### 虛擬 (Virtual)

體感操作與即時模式完全一致：拖放搬移、右鍵刪除、重命名 — 樹狀立即反映結果。差別在於所有變更只存在於記憶體中，檔案系統完全不受影響。

**Undo / Redo（標準業界行為）：**

- Ctrl+Z：撤回一筆，可連續撤回直到第零步
- Ctrl+Shift+Z：重做一筆，可連續重做到最新紀錄
- 撤回後若執行新操作 → 清空該位置之後的所有紀錄（redo 歷史被丟棄）

**兩個退出路徑：**

- 「套用變更」→ 跳出 diff 檢視所有差異 → 確認：批次執行到真實檔案系統，切回預覽模式 → 取消：關閉 diff，留在虛擬模式繼續編輯
- 「放棄並退出」→ 清空所有虛擬變更，切回預覽模式

### 即時 (Live)

操作方式與虛擬模式相同，但每個動作立即生效於檔案系統。刪除走回收桶。Ctrl+Z / Ctrl+Shift+Z 同樣適用（undo = 真實還原檔案，redo = 重新執行）。支援雙面板（可跨專案拖放）。無需確認對話框。

### 模式切換規則

- 預覽 ↔ 即時：自由切換
- 預覽 → 虛擬：建立空的虛擬狀態
- 虛擬 → 預覽/即時：若有未套用的變更，詢問「放棄？」
- 即時 → 虛擬：自由切換

---

## §2 UI 佈局與砍除清單

### 移除

- TodoPanel
- 專案狀態/進度/徽章顯示
- ProjectRelationsDialog
- TimelineDialog
- 模板系統（TemplateManager/Picker/Extract）
- ReportDialog
- 標籤系統（TagManager + node_tags）
- RulesDialog、DuplicateDialog、BatchRenameDialog
- ExternalToolsDialog
- Git 狀態整合
- BackupDialog
- DB 虛擬節點排序（sort_order 拖放）

### 保留

- MetadataPanel（最右側，F3 切換）
- 主題切換（ThemeDialog）
- 搜尋/篩選（重做為扁平清單）
- 快速跳轉 Ctrl+P（重做為扁平清單）
- 多根目錄管理（ProjectRootsDialog，簡化）

### 佈局

```
┌──────────────────────────────────────────────────────────────┐
│  選單列（精簡）                                                │
├────────┬──────────────────┬──────────────────┬───────────────┤
│ 專案    │                  │                  │               │
│ 選擇器  │  左面板（主樹狀）  │  右面板（雙面板）  │  Metadata     │
│ (窄欄)  │                  │  即時模式才出現    │  Panel        │
│        │  檔名|大小|時間    │  可選不同專案      │  (F3 切換)    │
│        │                  │                  │               │
├────────┴──────────────────┴──────────────────┴───────────────┤
│ 狀態列：[模式 ×3]  [虛擬：套用變更 | 放棄並退出]  [指令數]       │
└──────────────────────────────────────────────────────────────┘
```

專案選擇器從 260px QListWidget 改為窄側欄，只顯示名稱和路徑。

---

## §3 指令佇列（CommandQueue）— 虛擬模式核心

### CommandQueue

```
commands: list[Command]     # 所有已執行的指令
cursor: int                 # 目前位置（0 = 第零步）

push(command)   → 砍掉 cursor 之後的紀錄，append，cursor += 1
undo()          → cursor -= 1
redo()          → cursor += 1
can_undo: bool  → cursor > 0
can_redo: bool  → cursor < len(commands)
pending()       → commands[:cursor]（待套用的有效指令）
clear()         → 全部清空
```

### Command

```python
@dataclass
class Command:
    op: str          # "move" | "delete" | "copy" | "rename" | "mkdir"
    source: str      # 來源絕對路徑
    dest: str | None # 目標（delete/mkdir 時為 None）
    timestamp: float
```

### VirtualTree

把真實樹狀 + pending commands 合成「套用後的樣子」給 TreeModel 顯示。

每個節點標記狀態：unchanged / moved / deleted / added / renamed。用不同視覺樣式呈現（刪除線、新增色、灰色等）。

### Diff 檢視

按「套用變更」時，從 pending() 產生摘要清單。確認 → 逐一呼叫 file_operations 引擎執行。取消 → 關閉 diff，留在虛擬模式。

### DDD 歸屬

```
domain/services/command_queue.py   → CommandQueue
domain/services/virtual_tree.py    → VirtualTree
domain/models.py                   → Command dataclass
application/virtual_service.py     → 協調佇列 + 虛擬樹 + 套用
presentation/widgets/diff_panel.py → Diff 檢視 UI
```

---

## §4 即時模式 + 雙面板

### LiveHistory

結構與 CommandQueue 相同（list + cursor），但每筆紀錄包含執行結果（trash_key 等還原資訊）。undo = 真實還原檔案，redo = 真實重新執行。

### ModeController — 統一介面

```python
class ModeController:
    def execute(self, command):
        if mode == PREVIEW: return
        elif mode == VIRTUAL:
            command_queue.push(command)
            refresh_virtual_tree()
        elif mode == LIVE:
            record = execute_real(command)
            live_history.push(record)
            refresh_tree()

    def undo(self):
        if mode == VIRTUAL: command_queue.undo(); refresh_virtual_tree()
        elif mode == LIVE: live_history.undo(); refresh_tree()

    def redo(self):
        if mode == VIRTUAL: command_queue.redo(); refresh_virtual_tree()
        elif mode == LIVE: live_history.redo(); refresh_tree()
```

presentation 層統一呼叫 controller，不需要知道目前是哪種模式。

### 雙面板

- 僅即時模式可開啟（虛擬模式的指令佇列綁定單一專案）
- 面板 B 有獨立的專案選擇器
- A→B、B→A 雙向拖放
- 快捷鍵 F6 切換

### 右鍵選單

預覽模式：以系統預設開啟 / 在檔案管理器中顯示。

虛擬/即時模式：以系統預設開啟 / 在檔案管理器中顯示 / 剪下 / 複製 / 貼上 / 重新命名 / 刪除 / 新增資料夾。

### DDD 歸屬

```
domain/services/live_history.py    → LiveHistory
application/mode_controller.py     → ModeController
presentation/widgets/dual_panel.py → 雙面板容器
```

---

## §5 樹狀欄位 + 扁平清單搜尋

### 樹狀三欄

名稱 / 大小（B/KB/MB/GB，資料夾不顯示）/ 修改時間（相對格式：剛剛、3 天前、1 年前）。

點擊欄位標題可排序。TreeModel 的 columnCount 從 1 改為 3。

### 扁平清單搜尋

打字時 TreeView 隱藏，扁平清單顯示。按 fuzzy_score 排序。顯示：檔名 + 大小 + 相對路徑。

- Enter → 在樹狀中定位該檔案
- Escape → 關閉搜尋
- 方向鍵 → 移動選取

效能策略：掃描時預建扁平快取，搜尋時直接對快取跑 fuzzy_filter，不走 TreeModel。

匹配字元高亮：新增 fuzzy_score_positions() 回傳匹配位置，透過 QStyledItemDelegate 繪製。

### DDD 歸屬

```
domain/services/fuzzy_match.py          → 新增 fuzzy_score_positions()
presentation/tree_model.py              → columnCount=3
presentation/widgets/flat_search.py     → 扁平清單搜尋
presentation/widgets/highlight_delegate.py → 匹配字元高亮
```

---

## §6 選單列 + 快捷鍵

### 選單列

```
檔案：新增專案路徑 / 管理專案根目錄 / 結束
編輯：復原 / 重做 / 剪下 / 複製 / 貼上 / 重新命名 / 刪除 / 新增資料夾
檢視：重新整理 / Metadata 面板 / 雙面板 / 全部展開 / 全部收合 / 主題
模式：預覽 / 虛擬 / 即時 / 套用變更 / 放棄並退出虛擬模式
```

### 快捷鍵

```
Ctrl+1/2/3       切換模式
F3               Metadata 面板
F5               重新整理
F6               雙面板
Ctrl+Z           復原
Ctrl+Shift+Z     重做
Ctrl+X/C/V       剪下/複製/貼上
F2               重新命名
Delete           刪除
Ctrl+Shift+N     新增資料夾
Ctrl+Enter       套用變更（虛擬模式）
Ctrl+N           新增專案路徑
Ctrl+Q           結束
打字             觸發搜尋
Escape           關閉搜尋/diff
```

---

## 漸進式重構順序

```
Phase 1 → 砍 UI 贅肉（移除上述所有砍掉的元件和選單項）
Phase 2 → 樹狀三欄（大小/相對時間）+ 專案選擇器瘦身
Phase 3 → 指令佇列 + 虛擬模式重做 + diff 面板
Phase 4 → 即時模式重做 + ModeController + LiveHistory
Phase 5 → 雙面板
Phase 6 → 扁平清單搜尋 + 匹配高亮
```

每個 Phase 完成後程式都可以跑起來使用。
