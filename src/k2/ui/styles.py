"""
UI样式常量
"""

# 输入框下划线样式
UNDERLINE_INPUT_STYLE = "QLineEdit { border: none; border-bottom: 1px solid #ddd; background-color: transparent; border-radius: 0px; }"

# 灰色斜体标签样式
MUTED_LABEL_STYLE = "QLabel { color: #666; font-style: italic; }"

# 扩展名按钮样式
EXT_BUTTON_DISABLED_STYLE = """
    QPushButton {
        color: gray;
        text-decoration: none;
        font-weight: normal;
    }
"""

EXT_BUTTON_ENABLED_STYLE = """
    QPushButton {
        text-decoration: none;
        font-weight: normal;
    }
"""

EXT_BUTTON_DISABLED_FILTER_STYLE = """
    QPushButton {
        color: red;
        text-decoration: line-through;
        font-weight: normal;
    }
"""

# 主应用样式表
MAIN_STYLESHEET = """
    /* 检测按钮特殊样式 - 无边框，半透明背景，浅白色文本 */
    QPushButton#detectButton {
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: bold;
    }
    QPushButton#detectButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton#detectButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton#detectButton:disabled {
        background-color: rgba(128, 128, 128, 0.1);
        color: #999;
    }
    
    /* 标签过滤开关按钮 - 与检测按钮形状一致，选中时蓝色高亮 */
    QPushButton#tagFilterToggleButton {
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #999;
        font-weight: bold;
    }
    QPushButton#tagFilterToggleButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #bbb;
        font-weight: 600;
    }
    QPushButton#tagFilterToggleButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #bbb;
        font-weight: 600;
    }
    QPushButton#tagFilterToggleButton:checked {
        background-color: #0078d4;
        color: #ffffff;
        font-weight: bold;
    }
    QPushButton#tagFilterToggleButton:checked:hover {
        background-color: #106ebe;
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton#tagFilterToggleButton:disabled {
        background-color: rgba(128, 128, 128, 0.1);
        color: #999;
    }
    
    /* 作者按钮特殊样式 - 不加粗，宽度根据文本自适应 */
    QPushButton#creatorButton {
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: normal;
    }
    
    /* 命名按钮样式 - 与检测按钮一致但不加粗 */
    QPushButton#namingButton {
        border: none;
        border-radius: 4px;
        padding: 6px 8px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: normal;
    }
    QPushButton#namingButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
    }
    QPushButton#namingButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
    }
    
    /* 标签按钮样式 - 与命名按钮相同的基础样式 */
    QPushButton#tagButton {
        border: none;
        border-radius: 4px;
        padding: 6px 8px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: normal;
    }
    QPushButton#tagButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
    }
    QPushButton#tagButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
    }
    /* 选中时蓝色高亮，不改变文字粗细 */
    QPushButton#tagButton:checked {
        background-color: #0078d4;
        color: #ffffff;
        font-weight: normal;
    }
    QPushButton#tagButton:checked:hover {
        background-color: #106ebe;
        color: #ffffff;
    }
    /* 禁用+选中时浅灰色高亮 */
    QPushButton#tagButton:checked:disabled {
        background-color: rgba(108, 117, 125, 0.25);
        color: #aaaaaa;
        font-weight: normal;
    }
    QPushButton#tagButton:disabled {
        background-color: rgba(108, 117, 125, 0.08);
        color: #666666;
    }
    
    QPushButton#creatorButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
    }
    QPushButton#creatorButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
    }
    
    /* 固定状态的作者按钮样式 - 使用emoji标识 */
    QPushButton#creatorButtonPinned {
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: normal;
    }
    QPushButton#creatorButtonPinned:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
    }
    QPushButton#creatorButtonPinned:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
    }
    
    
    /* 下载按钮特殊样式 - 无边框，半透明背景 */
    QPushButton#downloadButton {
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        background-color: rgba(40, 167, 69, 0.15);
        color: #28a745;
        font-weight: normal;
    }
    QPushButton#downloadButton:hover {
        background-color: rgba(40, 167, 69, 0.25);
        color: #1e7e34;
    }
    QPushButton#downloadButton:pressed {
        background-color: rgba(40, 167, 69, 0.35);
        color: #155724;
    }
    QPushButton#downloadButton:disabled {
        background-color: rgba(128, 128, 128, 0.1);
        color: #999;
    }
    
    /* 终止按钮特殊样式 - 与检测按钮形状完全一致，只是颜色为红色 */
    QPushButton#terminateButton {
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        background-color: rgba(220, 53, 69, 0.12);
        color: #dc3545;
        font-weight: bold;
    }
    QPushButton#terminateButton:hover {
        background-color: rgba(220, 53, 69, 0.22);
        color: #c82333;
        font-weight: 600;
    }
    QPushButton#terminateButton:pressed {
        background-color: rgba(220, 53, 69, 0.32);
        color: #c82333;
        font-weight: 600;
    }
    QPushButton#terminateButton:disabled {
        background-color: rgba(128, 128, 128, 0.1);
        color: #999;
    }
    
    /* 模板快捷按钮特殊样式 - 无边框，半透明背景，浅白色文本 */
    QPushButton#templateButton {
        border: none;
        border-radius: 3px;
        padding: 4px 8px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: 500;
    }
    QPushButton#templateButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton#templateButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
        font-weight: 600;
    }
    
    /* 命名标签按钮特殊样式 - 选中时与下载按钮一致的绿色填充 */
    QPushButton#namingTabButton {
        border-radius: 0px;
        border: 0.5px solid #ddd;
        padding: 4px 8px;
        background-color: transparent;
    }
    QPushButton#namingTabButton:hover {
        background-color: rgba(224, 224, 224, 0.3);
        border-color: #999;
    }
    QPushButton#namingTabButton:pressed {
        background-color: rgba(208, 208, 208, 0.5);
        border-color: #666;
    }
    QPushButton#namingTabButton:checked {
        background-color: rgba(40, 167, 69, 0.15);
        border-color: #28a745;
        color: #28a745;
        font-weight: bold;
    }
    QPushButton#namingTabButton:checked:hover {
        background-color: rgba(40, 167, 69, 0.25);
        border-color: #1e7e34;
        color: #1e7e34;
    }
    
    
    
    /* 输入框样式 - 取消圆角 */
    QLineEdit {
        border-radius: 0px;
        border: 1px solid #ccc;
        padding: 2px 4px;
        background-color: white;
    }
    QLineEdit:focus {
        border-color: #0078d4;
        outline: none;
    }
    QLineEdit:disabled {
        background-color: #f5f5f5;
        color: #999;
    }
    
    /* 去掉帖子预览框和日志框的背景色 */
    QTreeWidget {
        background-color: transparent;
        border: none;
    }
    
    /* 帖子预览框表头样式 - 使用作者按钮的填充色，透明度减少10% */
    QHeaderView::section {
        background-color: rgba(108, 117, 125, 0.02);
    }
    
    QTextEdit {
        background-color: transparent;
        border: none;
    }
    
    
    /* 标签快捷按钮样式 - 与检测按钮样式一致 */
    QScrollArea QPushButton {
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: 500;
    }
    QScrollArea QPushButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #ffffff;
        font-weight: 600;
    }
    QScrollArea QPushButton:pressed {
        background-color: rgba(108, 117, 125, 0.32);
        color: #ffffff;
        font-weight: 600;
    }
    
    /* 右侧面板组件的边距控制 */
    QSlider {
        margin: 0px;
        padding: 0px;
    }
    
    
    /* 命名选项标签按钮样式 - 与检测按钮统一 */
    QPushButton#namingTabButton {
        border: none;
        background-color: transparent;
        padding: 5px 10px;
        color: #f8f9fa;
        font-weight: normal;
    }
    QPushButton#namingTabButton:checked {
        background-color: rgba(108, 117, 125, 0.12);
        color: #f8f9fa;
        font-weight: bold;
    }
    QPushButton#namingTabButton:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #f8f9fa;
    }
    QPushButton#namingTabButton:checked:hover {
        background-color: rgba(108, 117, 125, 0.22);
        color: #f8f9fa;
    }
    
"""

