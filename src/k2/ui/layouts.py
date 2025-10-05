"""
自定义布局类
"""
from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import Qt, QRect, QSize, QPoint


class BaseFlowLayout(QLayout):
    """流式布局基类，提供公共功能"""
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.item_list.append(item)
        # 清除缓存
        if hasattr(self, '_height_cache_key'):
            delattr(self, '_height_cache_key')

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True  # 启用高度随宽度动态计算

    def heightForWidth(self, width):
        """根据给定宽度计算所需高度"""
        if not self.item_list or width <= 0:
            return 50
        
        # 缓存计算结果，避免重复计算
        cache_key = (width, len(self.item_list))
        if hasattr(self, '_height_cache') and self._height_cache_key == cache_key:
            return self._height_cache_value
        
        height = self._do_layout(QRect(0, 0, width, 0), True)
        
        # 缓存结果
        self._height_cache_key = cache_key
        self._height_cache_value = height
        
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        """返回推荐尺寸"""
        return self.minimumSize()

    def minimumSize(self):
        """计算最小尺寸"""
        if not self.item_list:
            return QSize(200, 50)
        
        # 限制遍历数量，避免大量元素时性能问题
        sample_size = min(len(self.item_list), 50)
        
        # 计算所需最小宽度（采样最宽的元素）
        min_width = 200
        for i in range(sample_size):
            widget = self.item_list[i].widget()
            if widget:
                min_width = max(min_width, widget.sizeHint().width())
        
        # 估算最小高度（避免遍历所有元素）
        spacing = self.spacing() if self.spacing() > 0 else 5
        avg_height = 35  # 假设平均高度
        
        if sample_size > 0:
            # 计算前几个元素的平均高度
            total_height = 0
            count = 0
            for i in range(sample_size):
                widget = self.item_list[i].widget()
                if widget:
                    total_height += widget.sizeHint().height()
                    count += 1
            if count > 0:
                avg_height = total_height / count
        
        # 估算总高度：元素数量 * 平均高度（这只是估算，不需要精确）
        estimated_height = int(len(self.item_list) * (avg_height + spacing) / 4)  # 假设4列
        
        return QSize(min_width, max(estimated_height, 50))

    def _calculate_rows(self, rect):
        """计算每行包含的元素（公共逻辑）"""
        spacing = self.spacing() if self.spacing() > 0 else 5
        rows = []
        current_row = []
        current_width = 0
        
        # 硬性宽度限制：为布局边距和滚动条预留足够空间
        # 减去左右边距 + 滚动条宽度 + 安全边距
        hard_width_limit = rect.width()  # 不预留空间，使用全部宽度
        
        for item in self.item_list:
            widget = item.widget()
            if not widget:
                continue
                
            item_width = widget.sizeHint().width()
            
            # 计算添加此按钮后的总宽度
            if current_row:
                new_width = current_width + spacing + item_width
            else:
                new_width = item_width
            
            # 硬性检查：如果添加此按钮会超过限制，必须换行
            if current_row and new_width > hard_width_limit:
                rows.append(current_row)
                current_row = [item]
                current_width = item_width
            else:
                current_row.append(item)
                current_width = new_width
        
        if current_row:
            rows.append(current_row)
        
        return rows, spacing

    def _do_layout(self, rect, test_only):
        """布局逻辑，由子类实现"""
        raise NotImplementedError("Subclasses must implement _do_layout")


class FlowLayout(BaseFlowLayout):
    """自动换行的流式布局，元素居中对齐"""
    
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent, margin, spacing)
    
    def _do_layout(self, rect, test_only):
        if not self.item_list:
            return 0
        
        rows, spacing = self._calculate_rows(rect)
        
        # 计算总内容高度，用于垂直居中
        total_height = 0
        if rows:
            for row in rows:
                if row:
                    row_height = max(item.widget().sizeHint().height() for item in row if item.widget())
                    total_height += row_height
            if len(rows) > 1:
                total_height += spacing * (len(rows) - 1)
        
        # 始终进行垂直居中
        y_offset = max(0, (rect.height() - total_height) // 2)
        y = rect.y() + y_offset
        
        # 布局每一行
        for row in rows:
            if not row:
                continue
                
            # 计算这一行的总宽度
            row_width = sum(item.widget().sizeHint().width() for item in row)
            row_width += spacing * (len(row) - 1) if len(row) > 1 else 0
            
            # 居中对齐
            start_x = rect.x() + (rect.width() - row_width) // 2
            
            # 布局这一行的元素
            x = start_x
            line_height = 0
            
            for i, item in enumerate(row):
                widget = item.widget()
                item_width = widget.sizeHint().width()
                item_height = widget.sizeHint().height()
                
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), widget.sizeHint()))
                
                # 只在非最后一个元素后添加间距
                if i < len(row) - 1:
                    x += item_width + spacing
                else:
                    x += item_width
                line_height = max(line_height, item_height)
            
            y += line_height + spacing
        
        # 返回总布局高度（去掉最后一行后的多余间距）
        total_layout_height = y - rect.y()
        if rows:
            total_layout_height -= spacing  # 移除最后一行后的多余间距
        return total_layout_height


class JustifyFlowLayout(BaseFlowLayout):
    """自动换行的流式布局，两端对齐（均匀拉伸）"""
    
    def hasHeightForWidth(self):
        """禁用动态高度计算，避免 QScrollArea 中的递归问题"""
        return False
    
    def sizeHint(self):
        """返回推荐尺寸"""
        return QSize(200, 100)
    
    def minimumSize(self):
        """返回最小尺寸"""
        return QSize(200, 50)
    
    def _do_layout(self, rect, test_only):
        if not self.item_list:
            return 0
        
        # 定义统一的可用宽度（必须与 _calculate_rows 一致）
        spacing = self.spacing() if self.spacing() > 0 else 5
        available_width = rect.width()  # 与基类 _calculate_rows 保持一致，使用全部宽度
        
        # 手动计算行分布（确保与布局使用相同的宽度）
        rows = []
        current_row = []
        current_width = 0
        
        for item in self.item_list:
            widget = item.widget()
            if not widget:
                continue
                
            item_width = widget.sizeHint().width()
            
            if current_row:
                new_width = current_width + spacing + item_width
            else:
                new_width = item_width
            
            # 如果超过可用宽度，换行
            if current_row and new_width > available_width:
                rows.append(current_row)
                current_row = [item]
                current_width = item_width
            else:
                current_row.append(item)
                current_width = new_width
        
        if current_row:
            rows.append(current_row)
        
        y = rect.y()
        
        # 布局每一行 - 每行都拉伸到相同的 available_width
        for row in rows:
            if not row:
                continue
            
            # 计算这一行的自然宽度
            row_natural_width = sum(item.widget().sizeHint().width() for item in row if item.widget())
            row_spacing_width = spacing * (len(row) - 1) if len(row) > 1 else 0
            
            # 计算额外宽度并平均分配到每个按钮
            extra_width = available_width - row_natural_width - row_spacing_width
            if extra_width > 0 and len(row) > 0:
                width_per_button = extra_width // len(row)
                remaining = extra_width % len(row)
            else:
                width_per_button = 0
                remaining = 0
            
            # 设置这一行的按钮
            x = rect.x()
            row_height = 0
            
            for i, item in enumerate(row):
                widget = item.widget()
                if not widget:
                    continue
                
                # 计算最终宽度
                w = widget.sizeHint().width() + width_per_button
                if i < remaining:
                    w += 1
                h = widget.sizeHint().height()
                
                if not test_only:
                    item.setGeometry(QRect(x, y, w, h))
                
                x += w + spacing
                row_height = max(row_height, h)
            
            y += row_height + spacing
        
        # 返回总高度
        total_height = y - rect.y()
        if rows:
            total_height -= spacing
        
        return total_height

