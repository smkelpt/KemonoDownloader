"""下载功能混入"""
import os
import threading
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

from ...core.constants import DownloadState
from ...core.workers import TagFilterDownloadCoordinator
from ...utils.i18n import _


class DownloadMixin:
    """下载功能混入类"""
    
    def init_download(self):
        """初始化下载相关变量"""
        self.download_pause_event = threading.Event()
        self.download_state = DownloadState.IDLE
        self.tag_filter_coordinator = None
        self.current_downloaded_count = 0  # 当前已下载文件数
    
    def set_download_state(self, new_state: DownloadState):
        """安全地设置下载状态并更新UI"""
        if self.download_state != new_state:
            self.download_state = new_state
            self._update_download_control_btn()
    
    def _update_download_control_btn(self):
        """更新下载控制按钮的文本和状态"""
        if self.download_state == DownloadState.IDLE:
            self.download_control_btn.setText(_("ui.download_button"))
            self.download_control_btn.setEnabled(True)
            self.detect_btn.setEnabled(True)
            self.terminate_btn.setEnabled(False)
        elif self.download_state == DownloadState.DOWNLOADING:
            self.download_control_btn.setText(_("ui.pause_button"))
            self.download_control_btn.setEnabled(True)
            self.detect_btn.setEnabled(False)
            self.terminate_btn.setEnabled(True)
        elif self.download_state == DownloadState.PAUSED:
            self.download_control_btn.setText(_("ui.continue_button"))
            self.download_control_btn.setEnabled(True)
            self.detect_btn.setEnabled(True)
            self.terminate_btn.setEnabled(True)
    
    def on_download_control_button_clicked(self):
        """根据当前下载状态处理下载控制按钮的点击事件"""
        if self.download_state == DownloadState.IDLE:
            self.start_download()
        elif self.download_state == DownloadState.DOWNLOADING:
            self.pause_download()
        elif self.download_state == DownloadState.PAUSED:
            self.resume_download()
    
    def start_download(self):
        """开始下载"""
        dest_base = self.settings["default_download_path"]
        if not dest_base:
            return
        
        download_root = os.path.join(dest_base, "K2")
        os.makedirs(download_root, exist_ok=True)
        
        if not self.detected_files_data:
            return
        
        tag_filter_enabled = self.tag_filter_enabled_checkbox.isChecked()
        selected_tags = self.selected_tags.copy()
        allowed_exts = self.get_selected_extensions(self.filter_options)
        
        start_post_id = self.start_post_id_input.text().strip()
        end_post_id = self.end_post_id_input.text().strip()
        
        download_settings = {
            "download_root": download_root,
            "creator_folder_name_template": self.settings["creator_folder_name_template"],
            "post_folder_name_template": self.settings["post_folder_name_template"],
            "file_name_template": self.settings["file_name_template"],
            "threads": self.settings.get("concurrency", 5)
        }
        
        self.download_pause_event.clear()
        self.set_download_state(DownloadState.DOWNLOADING)
        
        # 重置计数器并显示下载进度
        self.current_downloaded_count = 0
        self.progress_panel.show_downloading(0, None, None, 0)
        
        self.tag_filter_coordinator = TagFilterDownloadCoordinator(
            self.detected_files_data,
            tag_filter_enabled,
            selected_tags,
            allowed_exts,
            download_settings,
            self.download_pause_event,
            self.creator_tags_with_counts,
            start_post_id,
            end_post_id
        )
        
        self.tag_filter_coordinator.file_completed.connect(self._on_file_completed)
        self.tag_filter_coordinator.stats_update.connect(self._on_stats_update)
        self.tag_filter_coordinator.finished.connect(self.on_worker_finished)
        self.tag_filter_coordinator.error.connect(self.on_download_error)
        self.tag_filter_coordinator.download_summary.connect(self._on_download_summary)
        self.tag_filter_coordinator.file_progress.connect(self._on_file_progress)
        self.tag_filter_coordinator.start()
    
    def _on_file_completed(self, url: str):
        """处理单个文件完成"""
        pass
    
    def _on_file_progress(self, downloaded_bytes: int, total_bytes: int, retry_count: int):
        """处理文件下载进度"""
        # 使用当前已下载文件数
        self.progress_panel.show_downloading(
            self.current_downloaded_count,
            None,
            (downloaded_bytes, total_bytes),
            retry_count
        )
        QApplication.processEvents()
    
    def _on_stats_update(self, downloaded_files: int, processed_posts: int):
        """处理下载统计更新"""
        self.current_downloaded_count = downloaded_files
        progress_text = _("messages.download_progress", downloaded=downloaded_files, processed=processed_posts)
        # 更新进度条（不带当前文件进度，因为小文件下载很快）
        self.progress_panel.show_downloading(downloaded_files, None, None, 0)
        QApplication.processEvents()
    
    def pause_download(self):
        """暂停下载"""
        try:
            if (hasattr(self, 'tag_filter_coordinator') and self.tag_filter_coordinator 
                and self.tag_filter_coordinator.isRunning()):
                
                self.download_pause_event.set()
                print("⏸️ 暂停信号已发送，正在停止所有下载...")
                self.download_control_btn.setText("暂停中...")
                self.download_control_btn.setEnabled(False)
                
                QTimer.singleShot(100, self._finalize_pause)
            else:
                self.set_download_state(DownloadState.IDLE)
        except Exception as e:
            print(f"⚠️ 暂停下载错误: {e}")
            self.set_download_state(DownloadState.IDLE)
    
    def _finalize_pause(self):
        """完成暂停操作"""
        try:
            if hasattr(self, 'tag_filter_coordinator') and self.tag_filter_coordinator and self.tag_filter_coordinator.isRunning():
                if not self.tag_filter_coordinator.wait(3000):
                    print("⚠️ 等待超时，强制终止下载协调器")
                    self.tag_filter_coordinator.terminate()
                    self.tag_filter_coordinator.wait()
            
            self.set_download_state(DownloadState.PAUSED)
            self.progress_panel.show_paused()
            print("✅ 下载已暂停")
        except Exception as e:
            print(f"⚠️ 完成暂停操作错误: {e}")
            self.set_download_state(DownloadState.IDLE)
            self.progress_panel.show_idle()
    
    def resume_download(self):
        """继续下载"""
        self.start_download()
    
    def on_terminate_button_clicked(self):
        """终止按钮点击处理"""
        try:
            # 终止检测任务
            if hasattr(self, 'detection_worker') and self.detection_worker and self.detection_worker.isRunning():
                print("🛑 正在终止检测任务...")
                self.detection_worker.terminate()
                self.detection_worker.wait()
                self.is_detecting = False
                self.detect_btn.setText(_("ui.detect_button"))
                self.detect_btn.setEnabled(True)
                self.terminate_btn.setEnabled(False)
                self.progress_panel.show_terminated()
                print("✅ 检测任务已终止")
                return
            
            # 终止下载任务（包括暂停状态）
            if hasattr(self, 'tag_filter_coordinator') and self.tag_filter_coordinator:
                # 如果线程正在运行，先设置暂停信号再终止
                if self.tag_filter_coordinator.isRunning():
                    print("🛑 正在终止下载任务...")
                    self.download_pause_event.set()
                    self.tag_filter_coordinator.terminate()
                    self.tag_filter_coordinator.wait()
                    print("✅ 下载任务已终止")
                
                # 无论线程是否运行，都重置状态
                self.set_download_state(DownloadState.IDLE)
                self.progress_panel.show_terminated()
                self.terminate_btn.setEnabled(False)
        except Exception as e:
            print(f"⚠️ 终止任务错误: {e}")
            self.set_download_state(DownloadState.IDLE)
            self.progress_panel.show_terminated()
            self.terminate_btn.setEnabled(False)
    
    def on_worker_finished(self):
        """处理下载工作线程完成"""
        if self.download_pause_event.is_set():
            self.set_download_state(DownloadState.PAUSED)
            self.progress_panel.show_paused()
        else:
            self.set_download_state(DownloadState.IDLE)
            self.progress_panel.show_completed()
    
    def _on_download_summary(self, summary: dict):
        """显示下载完成后的统计信息"""
        success_count = summary.get('success', 0)
        failed_count = summary.get('failed', 0)
        failed_files = summary.get('failed_files', [])
        
        if failed_count > 0:
            failed_info = "\n".join([f"  - {name}" for name, url, error in failed_files[:10]])
            if failed_count > 10:
                failed_info += f"\n  ... 还有 {failed_count - 10} 个文件"
            
            message = f"下载完成！\n\n成功: {success_count} 个文件\n失败: {failed_count} 个文件\n\n失败文件:\n{failed_info}"
            QMessageBox.warning(self, _("messages.download_complete"), message)
    
    def on_download_error(self, message: str):
        """处理下载错误"""
        self.set_download_state(DownloadState.IDLE)
        self.progress_panel.show_idle()
    
    def update_download_button(self):
        """更新下载控制按钮"""
        self._update_download_control_btn()

