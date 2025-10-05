"""检测功能混入"""
import os
import math
from PyQt6.QtWidgets import QTreeWidgetItem, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

from ...core.workers import DetectionWorker
from ...utils.i18n import _
from ..widgets import NumericSortTreeWidgetItem


class DetectionMixin:
    """检测功能混入类"""
    
    def init_detection(self):
        """初始化检测相关变量"""
        self.is_detecting = False
        self.detected_files_data = None
        self.detection_worker = None
        
        # 分页相关
        self.current_page = 1
        self.posts_per_page = 50
        self.total_pages = 1
    
    def handle_detect_button_click(self):
        """处理检测按钮点击事件"""
        if self.is_detecting:
            self.cancel_detection()
        else:
            self.start_detection()
    
    def cancel_detection(self):
        """取消当前的检测操作"""
        if hasattr(self, 'detection_worker') and self.detection_worker and self.detection_worker.isRunning():
            self.detection_worker.terminate()
            self.detection_worker.wait()
        
        self.is_detecting = False
        self.detect_btn.setText("检测")
        self.detect_btn.setEnabled(True)
        self.update_download_button()
    
    def start_detection(self):
        """开始检测"""
        url = self.url_input.text().strip()
        if not url:
            return
        
        # 自动清理日志
        current_url = getattr(self, '_last_detection_url', None)
        if current_url != url:
            self._last_detection_url = url
            
            # 切换URL时重置下载状态
            if self.download_state.value != 0:  # IDLE = 0
                if hasattr(self, 'tag_filter_coordinator') and self.tag_filter_coordinator and self.tag_filter_coordinator.isRunning():
                    self.download_pause_event.set()
                    if not self.tag_filter_coordinator.wait(2000):
                        self.tag_filter_coordinator.terminate()
                        self.tag_filter_coordinator.wait()
                
                from ...core.constants import DownloadState
                self.set_download_state(DownloadState.IDLE)
        
        self.detect_btn.setText(_("ui.cancel_button"))
        self.detect_btn.setEnabled(True)
        self.download_control_btn.setEnabled(False)
        self.terminate_btn.setEnabled(True)
        
        self.file_tree.clear()
        self.file_tree.header().hide()
        
        if self.all_tags is not None:
            self.all_tags.clear()
        self.selected_tags.clear()
        self._clear_tag_buttons()
        self._update_rule_preview()
        self.is_detecting = True
        self.detected_files_data = []
        
        extensions = set()
        source_filters = {"file", "attachments", "content"}
        
        self.detection_worker = DetectionWorker(url, extensions, source_filters)
        self.detection_worker.finished.connect(self.on_detection_finished)
        self.detection_worker.error.connect(self.on_detection_error)
        self.detection_worker.progress_update.connect(self.on_detection_progress_update)
        self.detection_worker.creator_info_detected.connect(self.on_creator_info_detected)
        self.detection_worker.start()
        
        # 显示检测进度
        self.progress_panel.show_detecting(0, 0)
    
    def on_detection_progress_update(self, loaded_count: int, total_count: int):
        """处理检测进度更新"""
        self.progress_panel.show_detecting(loaded_count, total_count)
        QApplication.processEvents()
    
    def on_detection_finished(self, service: str, creator_id: str, domain_config: dict):
        """检测完成处理"""
        self.is_detecting = False
        self.detect_btn.setText(_("ui.detect_button"))
        self.detect_btn.setEnabled(True)
        self.terminate_btn.setEnabled(False)
        
        all_data = self.detection_worker.all_data
        creator_tags = self.detection_worker.creator_tags
        creator_tags_with_counts = self.detection_worker.creator_tags_with_counts
        
        # 显示检测完成的满进度条
        total_posts = len(all_data)
        if total_posts > 0:
            self.progress_panel.show_detecting(total_posts, total_posts)
        posts_with_files = sum(1 for post in all_data if post.get('files'))
        posts_without_files = total_posts - posts_with_files
        
        if not all_data:
            self.update_download_button()
            return
        
        all_posts_for_ui = all_data
        is_single_post = len(all_posts_for_ui) > 0 and len(all_posts_for_ui) == 1
        
        if is_single_post:
            self.file_tree.headerItem().setText(0, _("ui.posts_header"))
            self.file_tree.setColumnHidden(1, True)
        else:
            self.file_tree.headerItem().setText(0, _("ui.post_time_header"))
            self.file_tree.headerItem().setText(1, _("ui.post_files_header"))
            self.file_tree.setColumnHidden(1, False)
        
        if not all_posts_for_ui:
            self.detect_btn.setEnabled(True)
            self.update_download_button()
            return
        
        try:
            self.file_tree.setUpdatesEnabled(False)
            self.file_tree.setSortingEnabled(False)
            self.file_tree.clear()
            
            self.detected_files_data = all_posts_for_ui
            
            # 收集文件扩展名
            self.detected_extensions.clear()
            for post_data in all_posts_for_ui:
                files = post_data.get('files', [])
                for file_info in files:
                    file_name = file_info.get('name', '')
                    if file_name:
                        file_ext = os.path.splitext(file_name)[1].lower()
                        if not file_ext:
                            file_url = file_info.get('url', '')
                            url_path_ext = os.path.splitext(file_url.split('?')[0])[1]
                            if url_path_ext:
                                file_ext = url_path_ext.lower()
                        
                        if file_ext:
                            self.detected_extensions.add(file_ext)
            
            self._update_extension_buttons_availability()
            
            # 清理worker数据
            self.detection_worker.all_data = []
            self.detection_worker.creator_tags = set()
            self.detection_worker.creator_tags_with_counts = {}
            
            # 标签处理
            if self.all_tags is None:
                self.all_tags = set()
            if creator_tags:
                self.all_tags.update(creator_tags)
            
            if self.creator_tags_with_counts is None:
                self.creator_tags_with_counts = {}
            else:
                self.creator_tags_with_counts.clear()
            
            if creator_tags_with_counts:
                self.creator_tags_with_counts.update(creator_tags_with_counts)
            
            # 显示数据
            if is_single_post and len(all_posts_for_ui) == 1:
                post_data = all_posts_for_ui[0]
                post_info = post_data["post_info"]
                files = post_data["files"]
                
                for file_info in files:
                    file_url = file_info['url']
                    file_name = file_info['name']
                    
                    file_item = QTreeWidgetItem(self.file_tree, [file_name, ""])
                    file_item.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    file_item.setCheckState(0, Qt.CheckState.Checked)
                    
                    file_item.setData(0, Qt.ItemDataRole.UserRole, {
                        'file_url': file_url,
                        'file_name': file_name,
                        'post_info': post_info
                    })
            else:
                total_posts = len(all_posts_for_ui)
                
                self.total_pages = math.ceil(total_posts / self.posts_per_page) if total_posts > 0 else 1
                self.current_page = 1
                
                self._display_posts_page()
        
        finally:
            self.file_tree.setUpdatesEnabled(True)
            self.file_tree.setSortingEnabled(False)
        
        self.detect_btn.setEnabled(True)
        self.update_download_button()
        self._apply_filters()
        
        self._update_tag_buttons_ui()
        
        # 保持检测完成状态，不隐藏进度条
    
    def _display_posts_page(self):
        """显示当前页的帖子"""
        if not self.detected_files_data:
            self.file_tree.header().hide()
            return
        
        self.file_tree.header().show()
        
        self.file_tree.setUpdatesEnabled(False)
        self.file_tree.clear()
        
        try:
            start_idx = (self.current_page - 1) * self.posts_per_page
            end_idx = min(start_idx + self.posts_per_page, len(self.detected_files_data))
            current_page_posts = self.detected_files_data[start_idx:end_idx]
            
            for post_data in current_page_posts:
                post_info = post_data["post_info"]
                files = post_data["files"]
                
                post_title = post_info.get('post_title', 'Untitled')
                files_count = str(len(files))
                
                post_item = NumericSortTreeWidgetItem(self.file_tree, [post_title, files_count])
                
                post_item.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                post_item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
                
                if not files:
                    post_item.setForeground(0, QBrush(QColor(150, 150, 150)))
                    post_item.setForeground(1, QBrush(QColor(150, 150, 150)))
                
                post_item.setData(0, Qt.ItemDataRole.UserRole, {'post_info': post_info, 'files': files, 'children_loaded': False})
                
                if files:
                    placeholder = QTreeWidgetItem(post_item, ["加载中..."])
            
            self._update_pagination_controls()
            
        finally:
            self.file_tree.setUpdatesEnabled(True)
    
    def _update_pagination_controls(self):
        """更新翻页按钮和页码显示"""
        from PyQt6.QtGui import QFontMetrics
        
        total_posts = len(self.detected_files_data) if self.detected_files_data else 0
        
        self.page_input.setText(str(self.current_page))
        self.total_pages_label.setText(str(self.total_pages))
        self.total_posts_label.setText(f"({_('ui.total_posts', count=total_posts)})")
        
        font_metrics = QFontMetrics(self.page_input.font())
        max_page_text = str(self.total_pages)
        text_width = font_metrics.horizontalAdvance(max_page_text)
        self.page_input.setFixedWidth(text_width + 20)
        
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < self.total_pages)
    
    def go_to_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self._display_posts_page()
    
    def go_to_next_page(self):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._display_posts_page()
    
    def go_to_input_page(self):
        """跳转到输入的页码"""
        try:
            page = int(self.page_input.text())
            if 1 <= page <= self.total_pages:
                self.current_page = page
                self._display_posts_page()
            else:
                self.page_input.setText(str(self.current_page))
        except ValueError:
            self.page_input.setText(str(self.current_page))
    
    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """处理树项点击事件"""
        if not item.parent():
            if item.isExpanded():
                item.setExpanded(False)
            else:
                item.setExpanded(True)
    
    def on_post_item_expanded(self, item: QTreeWidgetItem):
        """懒加载文件项"""
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data or item_data.get('children_loaded'):
            return
        
        self.file_tree.setUpdatesEnabled(False)
        try:
            item.takeChild(0)
            
            files = item_data['files']
            allowed_exts = self.get_selected_extensions(self.filter_options)
            
            for file_info in files:
                file_name = file_info['name']
                file_url = file_info['url']
                
                child_item = QTreeWidgetItem(item, [file_name])
                child_item.setData(0, Qt.ItemDataRole.UserRole, {"url": file_url, "name": file_name})
                child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
                file_ext = os.path.splitext(file_name)[1].lower()
                if self.is_ext_match(file_ext, allowed_exts):
                    child_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    child_item.setCheckState(0, Qt.CheckState.Unchecked)
            
            item_data['children_loaded'] = True
            item.setData(0, Qt.ItemDataRole.UserRole, item_data)
        finally:
            self.file_tree.setUpdatesEnabled(True)
    
    def on_detection_error(self, message: str):
        """处理检测错误"""
        self.is_detecting = False
        self.detect_btn.setText(_("ui.detect_button"))
        self.detect_btn.setEnabled(True)
        self.terminate_btn.setEnabled(False)
        self._update_tag_buttons_ui()
        self.update_download_button()
        
        # 隐藏进度条
        self.progress_panel.show_idle()

