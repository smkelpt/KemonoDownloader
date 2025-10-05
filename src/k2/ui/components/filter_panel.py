"""过滤面板组件（标签过滤 + 扩展名过滤）"""
import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QWidget, QSizePolicy, QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt

from ...utils.i18n import _
from ..styles import (
    UNDERLINE_INPUT_STYLE, MUTED_LABEL_STYLE,
    EXT_BUTTON_DISABLED_STYLE, EXT_BUTTON_ENABLED_STYLE,
    EXT_BUTTON_DISABLED_FILTER_STYLE
)
from ..layouts import FlowLayout


class FilterPanelMixin:
    """过滤面板功能混入类"""
    
    def init_filter_panel(self):
        """初始化过滤面板相关变量"""
        self.all_tags = None
        self.selected_tags = set()
        self.creator_tags_with_counts = None
        self.filter_options = {}
        self.detected_extensions = set()
    
    def create_tag_filter_ui(self, parent_layout: QVBoxLayout):
        """创建标签过滤UI"""
        # 标签功能开关
        tag_header_layout = QHBoxLayout()
        tag_header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tag_filter_enabled_checkbox = QPushButton(_("filters.tag_filter_title"))
        self.tag_filter_enabled_checkbox.setObjectName("tagFilterToggleButton")
        self.tag_filter_enabled_checkbox.setCheckable(True)
        self.tag_filter_enabled_checkbox.setChecked(False)
        self.tag_filter_enabled_checkbox.setToolTip("是否启用标签过滤功能")
        self.tag_filter_enabled_checkbox.toggled.connect(self._on_filter_enabled_changed)
        tag_header_layout.addWidget(self.tag_filter_enabled_checkbox)
        tag_header_layout.addStretch()
        
        parent_layout.addLayout(tag_header_layout)
        parent_layout.addSpacing(5)
        
        # 规则预览
        self.tag_rule_preview = QLabel(_("filters.current_rule_disabled"))
        self.tag_rule_preview.setWordWrap(True)
        self.tag_rule_preview.setStyleSheet(MUTED_LABEL_STYLE)
        self.tag_rule_preview.setMinimumHeight(40)
        self.tag_rule_preview.setMaximumHeight(40)
        self.tag_rule_preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        parent_layout.addWidget(self.tag_rule_preview)
        
        parent_layout.addSpacing(5)
        
        # 搜索输入框
        self.tag_filter_input = QLineEdit()
        self.tag_filter_input.setStyleSheet(UNDERLINE_INPUT_STYLE)
        self.tag_filter_input.setPlaceholderText(_("filters.search_placeholder"))
        self.tag_filter_input.textChanged.connect(self._on_tag_search_changed)
        parent_layout.addWidget(self.tag_filter_input)
        
        parent_layout.addSpacing(5)
        
        # 标签按钮容器
        self.tag_buttons_container = QWidget()
        self.tag_buttons_container.setFixedHeight(140)
        self.tag_buttons_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        
        self.tag_buttons_layout = FlowLayout(self.tag_buttons_container, margin=8, spacing=6)
        self.tag_buttons_container.setLayout(self.tag_buttons_layout)
        
        parent_layout.addWidget(self.tag_buttons_container)
    
    def create_extension_filter_ui(self, parent_layout: QVBoxLayout):
        """创建扩展名过滤UI"""
        ext_categories_data = {
            "row1": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
            "row2": [".mp4", ".mov", ".avi", ".mkv", ".ts"],
            "row3": [".zip", ".rar", ".7z", ".tar", ".001"],
        }
        
        center_container = QHBoxLayout()
        center_container.addStretch()
        
        ext_grid_layout = QVBoxLayout()
        ext_grid_layout.setContentsMargins(0, 0, 0, 0)
        ext_grid_layout.setSpacing(3)
        ext_buttons = {}
        
        temp_btn = QPushButton("JPEG")
        temp_btn.setObjectName("detectButton")
        font_metrics = temp_btn.fontMetrics()
        jpeg_width = font_metrics.boundingRect("JPEG").width()
        unified_button_width = jpeg_width + 32
        
        for row_key, extensions in ext_categories_data.items():
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            
            for ext in extensions:
                btn_text = ext[1:].upper()
                btn = QPushButton(btn_text)
                btn.setObjectName("detectButton")
                btn.setMinimumHeight(20)
                btn.setFixedWidth(unified_button_width)
                
                btn.clicked.connect(lambda checked, extension=ext: self._toggle_extension_filter(extension))
                ext_buttons[f"dl_{ext}"] = btn
                row_layout.addWidget(btn)
            
            ext_grid_layout.addLayout(row_layout)
        
        center_container.addLayout(ext_grid_layout)
        center_container.addStretch()
        
        parent_layout.addLayout(center_container)
        
        for ext_key, btn in ext_buttons.items():
            btn.setEnabled(False)
            btn.setStyleSheet(EXT_BUTTON_DISABLED_STYLE)
        
        return {
            "ext_boxes": ext_buttons,
            "ext_categories_data": ext_categories_data,
            "prefix": "dl"
        }
    
    def _on_filter_enabled_changed(self, enabled):
        """标签过滤功能开关状态改变"""
        self._update_tag_filter_ui_state()
        self._update_rule_preview()
        self._apply_filters()
    
    def _update_tag_filter_ui_state(self):
        """更新标签过滤UI的可用性"""
        enabled = self.tag_filter_enabled_checkbox.isChecked()
        self.tag_filter_input.setEnabled(enabled)
        self.tag_buttons_container.setEnabled(enabled)
    
    def _clear_tag_buttons(self):
        """清除所有动态生成的标签按钮"""
        while self.tag_buttons_layout.count():
            item = self.tag_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _update_tag_buttons_ui(self, search_text: str = ""):
        """动态创建并显示标签按钮"""
        self._clear_tag_buttons()
        
        if self.all_tags is None:
            self.all_tags = set()
        
        if not self.all_tags:
            return
        
        tag_counts = self.creator_tags_with_counts if self.creator_tags_with_counts else {}
        
        if search_text:
            search_lower = search_text.lower()
            filtered_tags = [tag for tag in self.all_tags if search_lower in tag.lower()]
            
            filtered_with_counts = [(tag, tag_counts.get(tag, 0)) for tag in filtered_tags]
            filtered_with_counts.sort(key=lambda x: (-x[1], x[0]))
            tags_to_display = [tag for tag, count in filtered_with_counts]
        else:
            tags_with_counts = [(tag, tag_counts.get(tag, 0)) for tag in self.all_tags]
            tags_with_counts.sort(key=lambda x: (-x[1], x[0]))
            tags_to_display = [tag for tag, count in tags_with_counts]
        
        max_total_chars = 96
        total_chars = 0
        
        for tag in tags_to_display:
            tag_length = len(tag)
            
            if total_chars + tag_length > max_total_chars:
                break
                
            is_selected = tag in self.selected_tags
            
            button = QPushButton(tag)
            button.setObjectName("tagButton")
            button.setCheckable(True)
            button.setChecked(is_selected)
            
            button.setMinimumHeight(30)
            button.setMaximumHeight(35)
            
            font_metrics = button.fontMetrics()
            text_width = font_metrics.boundingRect(tag).width()
            if hasattr(font_metrics, 'horizontalAdvance'):
                text_width = font_metrics.horizontalAdvance(tag)
            button_width = text_width + 20
            button.setFixedWidth(button_width)
            
            button.clicked.connect(lambda checked, t=tag: self._on_tag_button_clicked(t))
            
            button.style().unpolish(button)
            button.style().polish(button)
            
            self.tag_buttons_layout.addWidget(button)
            total_chars += tag_length
    
    def _on_tag_search_changed(self, text: str):
        """标签搜索框变化"""
        search_text = text.strip()
        self._update_tag_buttons_ui(search_text)
    
    def _on_tag_button_clicked(self, tag: str):
        """标签按钮被点击"""
        if tag in self.selected_tags:
            self.selected_tags.remove(tag)
        else:
            self.selected_tags.add(tag)
        
        for i in range(self.tag_buttons_layout.count()):
            item = self.tag_buttons_layout.itemAt(i)
            if item and item.widget():
                button = item.widget()
                button_tag = button.text()
                if button_tag == tag:
                    button.setChecked(tag in self.selected_tags)
                    break
        
        self._update_rule_preview()
        self._apply_filters()
    
    def _update_rule_preview(self):
        """更新规则预览文本"""
        if not self.tag_filter_enabled_checkbox.isChecked():
            self.tag_rule_preview.setText(_("filters.current_rule_disabled"))
            return
            
        if not self.selected_tags:
            self.tag_rule_preview.setText(_("filters.current_rule_no_tags"))
            return
        
        tags_text = "、".join(sorted(self.selected_tags))
        self.tag_rule_preview.setText(_("filters.current_rule_include", tags=tags_text))
    
    def _update_extension_buttons_availability(self):
        """更新扩展名按钮的启用/禁用状态"""
        if not hasattr(self, 'filter_options') or 'ext_boxes' not in self.filter_options:
            return
        
        saved_extensions = self.settings.get("filter_extensions", [])
        
        for ext_key, btn in self.filter_options["ext_boxes"].items():
            ext = ext_key.split('_', 1)[1]
            
            if ext in self.detected_extensions:
                btn.setEnabled(True)
                
                if ext in saved_extensions:
                    btn.setStyleSheet(EXT_BUTTON_ENABLED_STYLE)
                else:
                    btn.setStyleSheet(EXT_BUTTON_DISABLED_FILTER_STYLE)
            else:
                btn.setEnabled(False)
                btn.setStyleSheet(EXT_BUTTON_DISABLED_STYLE)
    
    def _toggle_extension_filter(self, extension: str):
        """切换扩展名过滤状态"""
        btn = self.filter_options["ext_boxes"][f"dl_{extension}"]
        
        if not btn.isEnabled():
            return
        
        saved_extensions = self.settings.get("filter_extensions", [])
        
        if extension in saved_extensions:
            saved_extensions.remove(extension)
            btn.setStyleSheet(EXT_BUTTON_DISABLED_FILTER_STYLE)
        else:
            saved_extensions.append(extension)
            btn.setStyleSheet(EXT_BUTTON_ENABLED_STYLE)
        
        self._save_setting("filter_extensions", saved_extensions)
        self._apply_filters()
    
    def get_selected_extensions(self, ext_categories_info: dict) -> set[str]:
        """获取选中的扩展名集合"""
        saved_extensions = self.settings.get("filter_extensions", [])
        return set(saved_extensions)
    
    def is_ext_match(self, file_ext: str, allowed_exts: set[str]) -> bool:
        """判断文件扩展名是否匹配过滤器"""
        if file_ext in allowed_exts:
            return True
        
        if ".001" in allowed_exts and file_ext.startswith(".") and len(file_ext) == 4:
            if file_ext[1:].isdigit():
                return True
        
        return False
    
    def _apply_filters(self):
        """根据扩展名过滤器更新文件树的勾选状态"""
        if getattr(self, 'is_detecting', False):
            return
        
        allowed_exts = self.get_selected_extensions(self.filter_options)
        
        iterator = QTreeWidgetItemIterator(self.file_tree)
        while iterator.value():
            item = iterator.value()
            if not item.parent():
                item.setHidden(False)
                
                for i in range(item.childCount()):
                    child = item.child(i)
                    file_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if not file_data or "name" not in file_data:
                        continue
                    file_ext = os.path.splitext(file_data["name"])[1].lower()
                    
                    child.setHidden(False)
                    child.setCheckState(0, Qt.CheckState.Checked if self.is_ext_match(file_ext, allowed_exts) else Qt.CheckState.Unchecked)
            
            iterator += 1
    
    def refresh_filter_panel_texts(self):
        """刷新过滤面板的UI文本"""
        self.tag_filter_enabled_checkbox.setText(_("filters.tag_filter_title"))
        self.tag_filter_input.setPlaceholderText(_("filters.search_placeholder"))
        self._update_rule_preview()

