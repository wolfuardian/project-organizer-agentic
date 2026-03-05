"""所有對話框."""

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
    BackupDialog, ExportReportDialog,
    ExternalToolsDialog, ToolEditDialog,
)

__all__ = [
    "RulesDialog", "RuleEditDialog", "DuplicateDialog", "BatchRenameDialog",
    "CATEGORIES",
    "ExtractTemplateDialog", "TemplateManagerDialog",
    "TemplateEditDialog", "TemplatePickerDialog",
    "QuickJumpDialog", "SearchDialog", "FilterDialog",
    "ProjectRelationsDialog", "TimelineDialog",
    "TagManagerDialog",
    "ProjectRootsDialog",
    "OperationHistoryDialog",
    "BackupDialog", "ExportReportDialog",
    "ExternalToolsDialog", "ToolEditDialog",
]
