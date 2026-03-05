from presentation.file_icons import get_category_icon
for c in ['folder','virtual','image','video','audio','code','document',
          'archive','data','font','3d','other','folder_add','drive']:
    icon = get_category_icon(c)
    assert not icon.isNull(), f"{c} icon is null"
print("all 14 icons ok")

from presentation.tree_model import ProjectTreeModel
print("tree_model import ok")
