"""
自定义UI控件
"""
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtCore import Qt


class NumericSortTreeWidgetItem(QTreeWidgetItem):
    """支持数字和时间排序的TreeWidgetItem"""
    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        
        # 对于第0列（时间）和第1列（文件数），使用存储的数值进行排序
        if column in [0, 1]:
            self_value = self.data(column, Qt.ItemDataRole.UserRole + 1)
            other_value = other.data(column, Qt.ItemDataRole.UserRole + 1)
            
            if self_value is not None and other_value is not None:
                return self_value < other_value
        
        # 其他列使用默认的字符串排序
        return super().__lt__(other)

