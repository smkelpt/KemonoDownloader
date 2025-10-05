"""命名选项面板组件"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QGroupBox, QScrollArea, QWidget, QSizePolicy
)
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtCore import Qt

from ...utils.i18n import _
from ..styles import UNDERLINE_INPUT_STYLE, MUTED_LABEL_STYLE
from ..layouts import FlowLayout


class NamingPanelMixin:
    """命名选项面板功能混入类"""
    
    def init_naming_panel(self):
        """初始化命名面板相关变量"""
        self.naming_buttons = []
        
        self.naming_options_by_tab_zh = {
            0: ["作者名", "作者ID", "平台"],
            1: ["帖子标题", "帖子ID"],
            2: ["平台", "作者ID", "作者名", "帖子ID", "帖子标题", "原始名", "扩展名"]
        }
        
        self.naming_options_by_tab_en = {
            0: ["Creator", "ID", "Platform"],
            1: ["Title", "Post ID"],
            2: ["Platform", "ID", "Creator", "Post ID", "Title", "Name", "Ext"]
        }
        
        self.button_text_to_variable = {
            "作者名": "{creator_name}",
            "作者ID": "{creator_id}",
            "平台": "{service}",
            "帖子标题": "{post_title}",
            "帖子ID": "{post_id}",
            "原始名": "{file_name_original}",
            "扩展名": "{file_ext}",
            "Creator": "{creator_name}",
            "ID": "{creator_id}",
            "Platform": "{service}",
            "Title": "{post_title}",
            "Post ID": "{post_id}",
            "Name": "{file_name_original}",
            "Ext": "{file_ext}"
        }
    
    def create_naming_options_panel(self, parent_layout: QVBoxLayout):
        """创建命名选项面板UI"""
        self.naming_title = QLabel(_("ui.naming_options_title"))
        font = self.naming_title.font()
        font.setBold(True)
        self.naming_title.setFont(font)
        parent_layout.addWidget(self.naming_title)
        
        parent_layout.addSpacing(5)
        
        # 标签页按钮行
        tab_header_layout = QHBoxLayout()
        tab_header_layout.setContentsMargins(0, 0, 0, 0)
        tab_header_layout.addStretch(1)
        
        self.naming_tab_buttons = []
        tab_configs = [
            (_("tabs.creator_folder"), "creator_folder", "creator_folder_name_template", 
             ['creator_name', 'creator_id', 'service']),
            (_("tabs.post_folder"), "post_folder", "post_folder_name_template", 
             ['post_title', 'post_id']),
            (_("tabs.file"), "file", "file_name_template", 
             ['service', 'creator_id', 'creator_name', 'post_id', 'post_title', 
              'file_name_original', 'file_ext'])
        ]
        
        for i, (title, tab_id, setting_key, variables) in enumerate(tab_configs):
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.setObjectName("namingTabButton")
            
            font_metrics = btn.fontMetrics()
            bold_font = btn.font()
            bold_font.setBold(True)
            bold_font_metrics = QFontMetrics(bold_font)
            bold_width = bold_font_metrics.boundingRect(title).width()
            button_width = max(80, bold_width + 25)
            btn.setFixedWidth(button_width)
            
            btn.clicked.connect(lambda checked, idx=i: self._switch_naming_tab(idx))
            self.naming_tab_buttons.append(btn)
            tab_header_layout.addWidget(btn)
        
        tab_header_layout.addStretch(1)
        parent_layout.addLayout(tab_header_layout)
        
        parent_layout.addSpacing(5)
        
        self.naming_tabs_config = tab_configs
        self.naming_inputs = {}
        
        parent_layout.addSpacing(5)
        
        # 命名按钮区域
        naming_buttons_frame = QGroupBox()
        naming_buttons_frame.setFixedHeight(70)
        naming_buttons_frame.setStyleSheet("""
            QGroupBox {
                border: none;
                background: transparent;
                margin: 0px;
                padding: 0px;
            }
        """)
        
        self.naming_buttons_scroll = QScrollArea()
        self.naming_buttons_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; margin: 0px; padding: 0px; }")
        self.naming_buttons_scroll.setWidgetResizable(True)
        self.naming_buttons_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.naming_buttons_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.naming_buttons_container = QWidget()
        self.naming_buttons_container.setMinimumHeight(70)
        self.naming_buttons_container.setMaximumHeight(70)
        self.naming_buttons_container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.naming_buttons_layout = FlowLayout(self.naming_buttons_container, margin=8, spacing=6)
        self.naming_buttons_container.setLayout(self.naming_buttons_layout)
        self.naming_buttons_scroll.setWidget(self.naming_buttons_container)
        
        naming_frame_layout = QVBoxLayout(naming_buttons_frame)
        naming_frame_layout.setContentsMargins(0, 0, 0, 0)
        naming_frame_layout.setSpacing(0)
        naming_frame_layout.addWidget(self.naming_buttons_scroll)
        
        parent_layout.addWidget(naming_buttons_frame)
        
        parent_layout.addSpacing(10)
        
        # 输入框和预览区域
        self.input_preview_widget = QWidget()
        input_preview_layout = QVBoxLayout(self.input_preview_widget)
        input_preview_layout.setContentsMargins(0, 0, 0, 0)
        input_preview_layout.setSpacing(5)
        
        self.naming_tab_input_widgets = []
        
        for i, (title, tab_id, setting_key, variables) in enumerate(tab_configs):
            input_widget = self._create_naming_input_widget(setting_key)
            input_widget.setVisible(i == 0)
            self.naming_tab_input_widgets.append(input_widget)
            input_preview_layout.addWidget(input_widget)
        
        parent_layout.addWidget(self.input_preview_widget)
        
        self.current_naming_tab = 0
        self.naming_tab_buttons[0].setChecked(True)
    
    def _create_naming_input_widget(self, setting_key: str):
        """创建命名标签页的输入框和预览区域"""
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)
        
        line_edit = QLineEdit(self.settings.get(setting_key, ""))
        line_edit.setStyleSheet(UNDERLINE_INPUT_STYLE)
        line_edit.textChanged.connect(lambda text, key=setting_key: self._save_setting(key, text))
        input_layout.addWidget(line_edit)
        
        preview_label = QLabel()
        preview_label.setWordWrap(True)
        preview_label.setStyleSheet(MUTED_LABEL_STYLE)
        input_layout.addWidget(preview_label)
        
        def update_preview():
            dummy_data = {
                'service': 'Patreon', 'creator_id': '1234567', 'creator_name': 'smk',
                'post_id': '12345678', 'post_title': 'Hi', 'file_name_original': 'name', 
                'file_ext': '.jpg'
            }
            template = line_edit.text()
            preview_text = template
            for key, value in dummy_data.items():
                preview_text = preview_text.replace(f"{{{key}}}", str(value) if value is not None else "")
            preview_label.setText(_("preview.preview_label", text=preview_text))
        
        line_edit.textChanged.connect(update_preview)
        update_preview()
        
        self.naming_inputs[setting_key] = line_edit
        
        return input_widget
    
    def _switch_naming_tab(self, tab_index: int):
        """切换命名标签页显示"""
        for i, btn in enumerate(self.naming_tab_buttons):
            btn.setChecked(i == tab_index)
        
        for i, input_widget in enumerate(self.naming_tab_input_widgets):
            input_widget.setVisible(i == tab_index)
        
        self.current_naming_tab = tab_index
        self._create_naming_buttons(tab_index)
    
    def _create_naming_buttons(self, tab_index=0):
        """创建快捷命名按钮"""
        for button in self.naming_buttons:
            button.setParent(None)
            button.deleteLater()
        self.naming_buttons.clear()
        
        while self.naming_buttons_layout.count():
            item = self.naming_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        current_lang = self.settings.get("language", "zh_CN")
        if current_lang == "en_US":
            options = self.naming_options_by_tab_en.get(tab_index, [])
        else:
            options = self.naming_options_by_tab_zh.get(tab_index, [])
        
        for option in options:
            button = QPushButton(option)
            button.setObjectName("namingButton")
            
            button.setMinimumHeight(30)
            button.setMaximumHeight(35)
            
            font_metrics = button.fontMetrics()
            text_width = font_metrics.boundingRect(option).width()
            if hasattr(font_metrics, 'horizontalAdvance'):
                text_width = font_metrics.horizontalAdvance(option)
            button_width = text_width + 20
            button.setFixedWidth(button_width)
            
            button.clicked.connect(lambda checked, text=option: self._on_naming_button_clicked(text))
            
            self.naming_buttons.append(button)
            self.naming_buttons_layout.addWidget(button)
    
    def _on_naming_button_clicked(self, button_text: str):
        """处理命名按钮点击事件"""
        variable = self.button_text_to_variable.get(button_text, button_text)
        
        if hasattr(self, 'current_naming_tab') and hasattr(self, 'naming_tabs_config'):
            tab_index = self.current_naming_tab
            if 0 <= tab_index < len(self.naming_tabs_config):
                setting_key = self.naming_tabs_config[tab_index][2]
                
                if setting_key in self.naming_inputs:
                    input_field = self.naming_inputs[setting_key]
                    current_text = input_field.text()
                    
                    cursor_pos = input_field.cursorPosition()
                    new_text = current_text[:cursor_pos] + variable + current_text[cursor_pos:]
                    input_field.setText(new_text)
                    
                    input_field.setCursorPosition(cursor_pos + len(variable))
    
    def refresh_naming_panel_texts(self):
        """刷新命名面板的UI文本"""
        if hasattr(self, 'naming_title'):
            self.naming_title.setText(_("ui.naming_options_title"))
        
        if hasattr(self, 'naming_tab_buttons'):
            tab_titles = [_("tabs.creator_folder"), _("tabs.post_folder"), _("tabs.file")]
            for i, btn in enumerate(self.naming_tab_buttons):
                if i < len(tab_titles):
                    btn.setText(tab_titles[i])
                    font_metrics = btn.fontMetrics()
                    bold_font = btn.font()
                    bold_font.setBold(True)
                    bold_font_metrics = QFontMetrics(bold_font)
                    bold_width = bold_font_metrics.boundingRect(tab_titles[i]).width()
                    button_width = max(80, bold_width + 25)
                    btn.setFixedWidth(button_width)
        
        if hasattr(self, 'naming_tabs_config') and hasattr(self, 'naming_tab_input_widgets'):
            for i, (title, tab_id, setting_key, variables) in enumerate(self.naming_tabs_config):
                old_widget = self.naming_tab_input_widgets[i]
                old_widget.setParent(None)
                old_widget.deleteLater()
                
                new_widget = self._create_naming_input_widget(setting_key)
                new_widget.setVisible(i == self.current_naming_tab)
                self.naming_tab_input_widgets[i] = new_widget
                
                self.input_preview_widget.layout().addWidget(new_widget)
        
        if hasattr(self, 'current_naming_tab'):
            self._create_naming_buttons(self.current_naming_tab)

