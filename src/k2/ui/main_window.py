"""
主窗口模块 - 重构版本
"""
import sys
import os
import json

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QFileDialog, QTreeWidget, QTreeWidgetItem, QHeaderView, 
    QSizePolicy, QComboBox, QSlider
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QFontMetrics

# 导入自定义UI组件
from .styles import UNDERLINE_INPUT_STYLE, MUTED_LABEL_STYLE, MAIN_STYLESHEET

# 导入核心组件
from ..core.constants import DownloadState, DEFAULT_SETTINGS

# 导入工具函数
from ..utils.paths import APP_DATA_FILE, CRASH_LOG_FILE
from ..utils.i18n import _, set_language, SUPPORTED_LANGUAGES

# 导入组件和混入类
from .components import CreatorButtonsMixin, NamingPanelMixin, FilterPanelMixin, ProgressPanel
from .mixins import DetectionMixin, DownloadMixin


class DownloaderGUI(QWidget, CreatorButtonsMixin, NamingPanelMixin, 
                     FilterPanelMixin, DetectionMixin, DownloadMixin):
    """下载器主窗口"""

    def __init__(self):
        super().__init__()
        
        # 加载设置
        self.settings = self._load_settings()
        set_language(self.settings.get("language", "zh_CN"))
        
        self.setWindowTitle("")  # 仅显示图标，不显示标题文字
        self.resize(1000, 700)
        
        # 设置窗口图标
        self._set_window_icon()
        
        # 初始化各个混入类
        self.init_creator_buttons()
        self.init_naming_panel()
        self.init_filter_panel()
        self.init_detection()
        self.init_download()
        
        # 设置UI
        self.setup_main_ui()
        
        # 显示配置加载完成
        self.progress_panel.show_config_loaded()
        
        # 刷新作者按钮和命名按钮
        self._refresh_creator_buttons()
        self._create_naming_buttons(0)

        # 启动时清理残留文件
        self._cleanup_temp_files()

        # 创建默认配置文件（如果不存在）
        if not os.path.exists(APP_DATA_FILE):
            self._create_default_config()
    
    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            from ..utils.paths import K2_MODULE_DIR
            icon_path = os.path.join(K2_MODULE_DIR, "resources", "icons", "K2.png")
            
            if os.path.exists(icon_path):
                from PyQt6.QtGui import QPixmap, QIcon
                self.setWindowIcon(QIcon(QPixmap(icon_path)))
        except Exception:
            pass  # 图标加载失败不影响程序运行
    
    def _load_settings(self) -> dict:
        """加载设置"""
        if os.path.exists(APP_DATA_FILE):
            try:
                with open(APP_DATA_FILE, "r", encoding='utf-8') as f:
                    app_data = json.load(f)
                    return {**DEFAULT_SETTINGS, **app_data.get("settings", {})}
            except:
                return DEFAULT_SETTINGS.copy()
        else:
            return DEFAULT_SETTINGS.copy()
    
    def setup_main_ui(self):
        """设置主UI"""
        self.setStyleSheet(MAIN_STYLESHEET)
        
        page_layout = QHBoxLayout(self)
        
        # 左侧面板：帖子预览
        preview_panel = self._create_preview_panel()
        page_layout.addLayout(preview_panel, 2)
        
        # 中间面板：过滤设置
        filter_panel = self._create_filter_panel()
        page_layout.addLayout(filter_panel, 1)
        
        # 右侧面板：设置和下载
        right_panel = self._create_right_panel()
        page_layout.addLayout(right_panel, 2)
        
        # 初始化UI状态
        self._update_tag_filter_ui_state()
    
    def _create_preview_panel(self) -> QVBoxLayout:
        """创建左侧预览面板"""
        panel = QVBoxLayout()
        panel.addSpacing(10)
        
        # URL输入行
        url_layout = QHBoxLayout()
        self.url_title_label = QLabel(_("ui.url_label"))
        url_layout.addWidget(self.url_title_label)
        
        self.url_input = QLineEdit()
        self.url_input.setStyleSheet(UNDERLINE_INPUT_STYLE)
        url_layout.addWidget(self.url_input)
        
        self.detect_btn = QPushButton(_("ui.detect_button"))
        self.detect_btn.setObjectName("detectButton")
        self.detect_btn.clicked.connect(self.handle_detect_button_click)
        url_layout.addWidget(self.detect_btn)
        
        panel.addLayout(url_layout)
        
        # 作者快捷按钮容器
        creator_container = QWidget()
        creator_container.setFixedHeight(105)
        creator_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setup_creator_buttons_ui(creator_container)
        panel.addWidget(creator_container)
        panel.addSpacing(5)
        
        # 作者信息标签
        self.creator_info_label = QLabel("")
        self.creator_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.creator_info_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                border: none;
                color: #f8f9fa;
                font-size: 12px;
            }
        """)
        font_metrics = self.creator_info_label.fontMetrics()
        line_height = font_metrics.height()
        self.creator_info_label.setFixedHeight(line_height)
        self.creator_info_label.setWordWrap(False)
        self.creator_info_label.setText(_('creator_info.hover_tip'))
        self.creator_info_label.setVisible(False)
        panel.addWidget(self.creator_info_label)
        panel.addSpacing(5)
        
        # 文件树
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(2)
        
        header_item = QTreeWidgetItem()
        header_item.setText(0, _("ui.post_time_header"))
        header_item.setText(1, _("ui.post_files_header"))
        self.file_tree.setHeaderItem(header_item)
        
        header = self.file_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        self.file_tree.headerItem().setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        self.file_tree.headerItem().setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        
        self.file_tree.setSortingEnabled(False)
        self.file_tree.setAnimated(False)
        self.file_tree.setAutoScroll(False)
        self.file_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.file_tree.setRootIsDecorated(False)
        
        self.file_tree.itemExpanded.connect(self.on_post_item_expanded)
        self.file_tree.itemClicked.connect(self.on_tree_item_clicked)
        
        panel.addWidget(self.file_tree)
        self.file_tree.header().hide()
        
        # 分页控制
        pagination_layout = self._create_pagination_controls()
        panel.addLayout(pagination_layout)
        
        return panel
    
    def _create_pagination_controls(self) -> QHBoxLayout:
        """创建分页控制"""
        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 5, 0, 0)
        pagination_layout.setSpacing(10)
        
        self.prev_page_btn = QPushButton("◀")
        self.prev_page_btn.setObjectName("detectButton")
        self.prev_page_btn.setFixedWidth(40)
        self.prev_page_btn.clicked.connect(self.go_to_prev_page)
        self.prev_page_btn.setEnabled(False)
        pagination_layout.addWidget(self.prev_page_btn)
        
        pagination_layout.addStretch()
        
        page_input_layout = QHBoxLayout()
        page_input_layout.setSpacing(5)
        
        self.page_input = QLineEdit()
        self.page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_input.setStyleSheet(UNDERLINE_INPUT_STYLE + " font-size: 13px;")
        self.page_input.setText("1")
        font_metrics = QFontMetrics(self.page_input.font())
        initial_width = font_metrics.horizontalAdvance("1") + 20
        self.page_input.setFixedWidth(initial_width)
        self.page_input.returnPressed.connect(self.go_to_input_page)
        page_input_layout.addWidget(self.page_input)
        
        page_separator = QLabel("/")
        page_separator.setStyleSheet("font-size: 13px;")
        page_input_layout.addWidget(page_separator)
        
        self.total_pages_label = QLabel("1")
        self.total_pages_label.setStyleSheet("font-size: 13px;")
        page_input_layout.addWidget(self.total_pages_label)
        
        self.total_posts_label = QLabel("")
        self.total_posts_label.setStyleSheet("font-size: 13px; color: gray;")
        page_input_layout.addWidget(self.total_posts_label)
        
        pagination_layout.addLayout(page_input_layout)
        
        pagination_layout.addStretch()
        
        self.next_page_btn = QPushButton("▶")
        self.next_page_btn.setObjectName("detectButton")
        self.next_page_btn.setFixedWidth(40)
        self.next_page_btn.clicked.connect(self.go_to_next_page)
        self.next_page_btn.setEnabled(False)
        pagination_layout.addWidget(self.next_page_btn)
        
        return pagination_layout
    
    def _create_filter_panel(self) -> QVBoxLayout:
        """创建中间过滤面板"""
        panel = QVBoxLayout()
        panel.setContentsMargins(5, 10, 5, 0)
        panel.setSpacing(0)
        
        # 标签过滤UI
        self.create_tag_filter_ui(panel)
        
        # 帖子ID范围
        panel.addSpacing(10)
        
        self.post_range_label = QLabel(_("filters.post_range_title"))
        self.post_range_label.setStyleSheet("font-size: 12px; color: gray;")
        panel.addWidget(self.post_range_label)
        
        panel.addSpacing(5)
        
        post_range_layout = QHBoxLayout()
        post_range_layout.setSpacing(0)
        post_range_layout.addStretch(1)
        
        self.start_post_id_input = QLineEdit("")
        self.start_post_id_input.setStyleSheet(UNDERLINE_INPUT_STYLE)
        self.start_post_id_input.setPlaceholderText(_("filters.start_post_id"))
        self.start_post_id_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_metrics = QFontMetrics(self.start_post_id_input.font())
        char_width = font_metrics.averageCharWidth() * 16 + 10
        self.start_post_id_input.setMaximumWidth(char_width)
        post_range_layout.addWidget(self.start_post_id_input)
        
        post_range_layout.addStretch(1)
        
        self.range_separator = QLabel("-")
        self.range_separator.setStyleSheet("font-size: 12px;")
        self.range_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        post_range_layout.addWidget(self.range_separator)
        
        post_range_layout.addStretch(1)
        
        self.end_post_id_input = QLineEdit("")
        self.end_post_id_input.setStyleSheet(UNDERLINE_INPUT_STYLE)
        self.end_post_id_input.setPlaceholderText(_("filters.end_post_id"))
        self.end_post_id_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.end_post_id_input.setMaximumWidth(char_width)
        post_range_layout.addWidget(self.end_post_id_input)
        
        post_range_layout.addStretch(1)
        
        panel.addLayout(post_range_layout)
        
        panel.addSpacing(3)
        self.post_range_note = QLabel(_("filters.post_range_note"))
        self.post_range_note.setStyleSheet(MUTED_LABEL_STYLE + " font-size: 10px;")
        self.post_range_note.setWordWrap(True)
        panel.addWidget(self.post_range_note)
        
        panel.addStretch()
        
        # 扩展名过滤UI
        panel.addSpacing(10)
        ext_filter_options = self.create_extension_filter_ui(panel)
        self.filter_options.update(ext_filter_options)
        
        return panel
    
    def _create_right_panel(self) -> QVBoxLayout:
        """创建右侧面板"""
        panel = QVBoxLayout()
        panel.addSpacing(10)
        
        # 语言选择
        language_layout = QHBoxLayout()
        self.language_label = QLabel("Language:")
        language_layout.addWidget(self.language_label)
        language_layout.addStretch()
        
        self.language_combo = QComboBox()
        for lang_code, lang_name in SUPPORTED_LANGUAGES.items():
            self.language_combo.addItem(lang_name, lang_code)
        
        self.language_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        
        current_lang = self.settings.get("language", "zh_CN")
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == current_lang:
                self.language_combo.setCurrentIndex(i)
                break
        
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        language_layout.addWidget(self.language_combo)
        panel.addLayout(language_layout)
        
        panel.addSpacing(10)
        
        # 命名选项面板
        self.create_naming_options_panel(panel)
        
        # 下载路径
        panel.addSpacing(20)
        
        path_header_layout = QHBoxLayout()
        path_header_layout.setContentsMargins(0, 0, 0, 0)
        path_header_layout.setSpacing(5)
        
        self.path_label = QLabel(_("settings.download_path_label"))
        path_header_layout.addWidget(self.path_label)
        
        path_browse_btn = QPushButton("...")
        font_metrics = path_browse_btn.fontMetrics()
        text_width = font_metrics.boundingRect("...").width()
        path_browse_btn.setFixedWidth(text_width + 16)
        path_browse_btn.clicked.connect(lambda: self.choose_folder(self.default_path_input))
        path_header_layout.addWidget(path_browse_btn)
        
        self.default_path_input = QLineEdit(self.settings["default_download_path"])
        self.default_path_input.setStyleSheet(UNDERLINE_INPUT_STYLE)
        self.default_path_input.textChanged.connect(lambda text: self._save_setting("default_download_path", text))
        path_header_layout.addWidget(self.default_path_input)
        
        self.path_note = QLabel(_("settings.download_path_note"))
        self.path_note.setStyleSheet(MUTED_LABEL_STYLE + " font-size: 11px;")
        path_header_layout.addWidget(self.path_note)
        
        open_folder_btn = QPushButton("/")
        font_metrics = open_folder_btn.fontMetrics()
        text_width = font_metrics.boundingRect("/").width()
        open_folder_btn.setFixedWidth(text_width + 16)
        open_folder_btn.clicked.connect(self.open_download_folder)
        open_folder_btn.setToolTip("打开下载目录")
        path_header_layout.addWidget(open_folder_btn)
        
        panel.addLayout(path_header_layout)
        
        # 下载按钮
        panel.addSpacing(10)
        
        download_buttons_layout = QHBoxLayout()
        download_buttons_layout.setSpacing(5)
        
        self.download_control_btn = QPushButton(_("ui.download_button"))
        self.download_control_btn.setObjectName("downloadButton")
        self.download_control_btn.clicked.connect(self.on_download_control_button_clicked)
        download_buttons_layout.addWidget(self.download_control_btn)
        
        self.terminate_btn = QPushButton(_("ui.terminate_button"))
        self.terminate_btn.setObjectName("terminateButton")
        font_metrics = self.terminate_btn.fontMetrics()
        text_width = font_metrics.boundingRect(_("ui.terminate_button")).width()
        self.terminate_btn.setFixedWidth(text_width + 30)
        self.terminate_btn.clicked.connect(self.on_terminate_button_clicked)
        self.terminate_btn.setEnabled(False)
        download_buttons_layout.addWidget(self.terminate_btn)
        
        panel.addLayout(download_buttons_layout)
        
        panel.addSpacing(5)
        
        # 线程设置
        thread_layout = QHBoxLayout()
        self.thread_title_label = QLabel(_("settings.download_threads_label"))
        thread_layout.addWidget(self.thread_title_label)
        
        self.download_thread_label = QLabel(str(self.settings.get("concurrency", 5)))
        self.download_thread_label.setMinimumWidth(20)
        thread_layout.addWidget(self.download_thread_label)
        
        self.download_thread_slider = QSlider(Qt.Orientation.Horizontal)
        self.download_thread_slider.setRange(1, 20)
        self.download_thread_slider.setValue(self.settings.get("concurrency", 5))
        thread_layout.addWidget(self.download_thread_slider)
        
        self.download_thread_slider.valueChanged.connect(self._handle_download_concurrency_change)
        panel.addLayout(thread_layout)
        
        panel.addSpacing(10)
        
        panel.addStretch()
        
        # 进度条面板
        self.progress_panel = ProgressPanel()
        panel.addWidget(self.progress_panel)
        
        return panel
    
    def _handle_download_concurrency_change(self, value):
        """处理下载线程数变化"""
        self.download_thread_label.setText(str(value))
        self._save_setting('concurrency', value)
    
    def _on_language_changed(self):
        """处理语言更改"""
        current_index = self.language_combo.currentIndex()
        if current_index >= 0:
            new_language = self.language_combo.itemData(current_index)
            if new_language:
                self._save_setting("language", new_language)
                set_language(new_language)
                self._refresh_ui_texts()
    
    def _refresh_ui_texts(self):
        """刷新所有UI文本"""
        self.setWindowTitle("")  # 仅显示图标，不显示标题文字
        
        # URL输入区域
        self.url_title_label.setText(_("ui.url_label"))
        self.detect_btn.setText(_("ui.detect_button"))
        
        # 文件树标题
        self.file_tree.headerItem().setText(0, _("ui.post_time_header"))
        self.file_tree.headerItem().setText(1, _("ui.post_files_header"))
        
        header = self.file_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        
        self.file_tree.headerItem().setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
        self.file_tree.headerItem().setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        
        # 过滤面板
        self.refresh_filter_panel_texts()
        
        # 帖子范围
        self.post_range_label.setText(_("filters.post_range_title"))
        self.start_post_id_input.setPlaceholderText(_("filters.start_post_id"))
        self.end_post_id_input.setPlaceholderText(_("filters.end_post_id"))
        self.post_range_note.setText(_("filters.post_range_note"))
        
        # 下载按钮
        self.terminate_btn.setText(_("ui.terminate_button"))
        font_metrics = self.terminate_btn.fontMetrics()
        text_width = font_metrics.boundingRect(_("ui.terminate_button")).width()
        self.terminate_btn.setFixedWidth(text_width + 30)
        
        # 设置面板
        self.path_label.setText(_("settings.download_path_label"))
        self.path_note.setText(_("settings.download_path_note"))
        self.thread_title_label.setText(_("settings.download_threads_label"))
        
        # 下载控制
        self._update_download_control_btn()
        
        # 命名面板
        self.refresh_naming_panel_texts()
        
        # 进度条面板
        self.progress_panel.refresh_texts()
    
    def choose_folder(self, line_edit_widget: QLineEdit):
        """选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if folder:
            line_edit_widget.setText(folder)
    
    def open_download_folder(self):
        """打开下载目录"""
        import subprocess
        import platform
        
        dest_base = self.settings.get("default_download_path", "")
        if not dest_base:
            print("⚠️ 未设置下载路径")
            return

        download_folder = os.path.join(dest_base, "K2")
        
        if not os.path.exists(download_folder):
            os.makedirs(download_folder, exist_ok=True)
        
        try:
            if platform.system() == "Windows":
                os.startfile(download_folder)
            elif platform.system() == "Darwin":
                subprocess.run(["open", download_folder])
            else:
                subprocess.run(["xdg-open", download_folder])
        except Exception as e:
            print(f"⚠️ 打开文件夹失败: {e}")
    
    def _save_setting(self, key, value):
        """保存单个设置项"""
        self.settings[key] = value
        self.save_settings()
    
    def save_settings(self):
        """保存设置到配置文件"""
        try:
            if os.path.exists(APP_DATA_FILE):
                with open(APP_DATA_FILE, "r", encoding='utf-8') as f:
                    app_data = json.load(f)
            else:
                app_data = {"settings": {}, "creator_urls": [], "creator_info": {}, "version": "1.0.0"}
            
            app_data["settings"] = self.settings
            
            with open(APP_DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(app_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def _cleanup_temp_files(self):
        """清理残留的.part临时文件"""
        download_path = self.settings.get("default_download_path")
        if not download_path or not os.path.isdir(download_path):
            return
        
        downloads_folder = os.path.join(download_path, "K2")
        if not os.path.isdir(downloads_folder):
            return
        
        try:
            for root, _, files in os.walk(downloads_folder):
                for name in files:
                    if name.endswith(".part"):
                        file_path = os.path.join(root, name)
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass
        except Exception:
            pass
    
    def _create_default_config(self):
        """创建默认配置文件"""
        print("⚠️ 配置文件不存在，创建默认配置文件")
        default_data = {
            "settings": self.settings,
            "creator_urls": [],
            "creator_info": {},
            "version": "1.0.0"
        }
        try:
            with open(APP_DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"创建默认配置文件失败: {e}")

    def eventFilter(self, obj, event):
        """事件过滤器，处理作者按钮悬停"""
        if hasattr(obj, '_creator_service'):
            if event.type() == QEvent.Type.Enter:
                self._show_creator_info(obj)
            elif event.type() == QEvent.Type.Leave:
                self._hide_creator_info()
        
        return super().eventFilter(obj, event)
    
    def closeEvent(self, event):
        """处理窗口关闭事件"""
        try:
            if hasattr(self, 'detection_worker') and self.detection_worker and self.detection_worker.isRunning():
                self.detection_worker.terminate()
                self.detection_worker.wait(1000)
            
            if hasattr(self, 'tag_filter_coordinator') and self.tag_filter_coordinator and self.tag_filter_coordinator.isRunning():
                self.download_pause_event.set()
                if not self.tag_filter_coordinator.wait(2000):
                    self.tag_filter_coordinator.terminate()
                    self.tag_filter_coordinator.wait(1000)
        except Exception as e:
            pass  # 静默处理错误
        finally:
            event.accept()


def main():
    try:
        app = QApplication(sys.argv)
        gui = DownloaderGUI()
        gui.show()
        sys.exit(app.exec())
    except Exception:
        import traceback
        
        log_dir = os.path.dirname(CRASH_LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"--- CRASH LOG ---\n")
            traceback.print_exc(file=f)
        
        raise


if __name__ == '__main__':
    main()

