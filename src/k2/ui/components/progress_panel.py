"""进度条面板组件"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt
from ...utils.i18n import _


class ProgressPanel(QWidget):
    """进度条面板，显示下载/检测进度"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._reset()
        
        # 保存当前状态，用于语言切换时刷新
        self._current_state = None  # 'idle', 'config_loaded', 'detecting', 'downloading', 'paused', 'terminated', 'completed'
        self._current_params = {}
    
    def _setup_ui(self):
        """设置UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 0)
        main_layout.setSpacing(3)
        
        # 第一行：状态说明（左）+ 重试说明（右）
        first_row = QHBoxLayout()
        first_row.setSpacing(10)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 12px; color: #f8f9fa;")
        first_row.addWidget(self.status_label)
        
        first_row.addStretch()
        
        self.retry_label = QLabel("")
        self.retry_label.setStyleSheet("font-size: 12px; color: #ffc107;")
        self.retry_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        first_row.addWidget(self.retry_label)
        
        main_layout.addLayout(first_row)
        
        # 第二行：进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        main_layout.addWidget(self.progress_bar)
        
        # 第三行：进程进度（左）+ 当前文件进度（右）
        third_row = QHBoxLayout()
        third_row.setSpacing(10)
        
        self.process_label = QLabel("")
        self.process_label.setStyleSheet("font-size: 11px; color: #adb5bd;")
        third_row.addWidget(self.process_label)
        
        third_row.addStretch()
        
        self.file_progress_label = QLabel("")
        self.file_progress_label.setStyleSheet("font-size: 11px; color: #adb5bd;")
        self.file_progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        third_row.addWidget(self.file_progress_label)
        
        main_layout.addLayout(third_row)
    
    def _reset(self):
        """重置所有显示"""
        self.status_label.setText("")
        self.retry_label.setText("")
        self.process_label.setText("")
        self.file_progress_label.setText("")
        self.progress_bar.setValue(0)
    
    def show_config_loaded(self):
        """显示配置加载完成"""
        self._current_state = 'config_loaded'
        self._current_params = {}
        
        self.status_label.setText(_("progress.config_loaded"))
        self.retry_label.setText("")
        self.process_label.setText("")
        self.file_progress_label.setText("")
        self.progress_bar.setMaximum(100)  # 确保不在不确定模式
        self.progress_bar.setValue(100)
    
    def show_detecting(self, loaded_count: int, total_count: int = None):
        """显示检测状态
        
        Args:
            loaded_count: 已加载的帖子数
            total_count: 总帖子数（可选）
        """
        self._current_state = 'detecting'
        self._current_params = {'loaded_count': loaded_count, 'total_count': total_count}
        
        # 如果已经完成（loaded == total且都>0），显示完成状态
        if total_count and total_count > 0 and loaded_count == total_count:
            self.status_label.setText(_("progress.detection_completed"))
            self.process_label.setText(_("progress.detected_posts_with_total", loaded=loaded_count, total=total_count))
            self.progress_bar.setMaximum(total_count)
            self.progress_bar.setValue(total_count)
        else:
            self.status_label.setText(_("progress.detecting"))
            # 显示进度格式：已检测123/456个帖子 或 已检测123个帖子
            if total_count and total_count > 0:
                self.process_label.setText(_("progress.detecting_posts_with_total", loaded=loaded_count, total=total_count))
                # 使用确定的进度条
                self.progress_bar.setMaximum(total_count)
                self.progress_bar.setValue(loaded_count)
            else:
                self.process_label.setText(_("progress.detecting_posts", count=loaded_count))
                # 没有总数时也使用确定进度，但从0开始
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(0)
        
        self.retry_label.setText("")
        self.file_progress_label.setText("")
    
    def show_downloading(self, downloaded_count: int, total_count: int = None, 
                        current_file_size: tuple = None, retry_count: int = 0):
        """显示下载状态
        
        Args:
            downloaded_count: 已下载的文件数
            total_count: 总文件数（可选，如果提供则显示百分比进度条）
            current_file_size: 当前文件进度 (已下载字节, 总字节)
            retry_count: 正在重试的文件数
        """
        self._current_state = 'downloading'
        self._current_params = {
            'downloaded_count': downloaded_count,
            'total_count': total_count,
            'current_file_size': current_file_size,
            'retry_count': retry_count
        }
        
        self.status_label.setText(_("progress.downloading"))
        
        if retry_count > 0:
            self.retry_label.setText(_("progress.retrying_files", count=retry_count))
        else:
            self.retry_label.setText("")
        
        self.process_label.setText(_("progress.downloaded_files", count=downloaded_count))
        
        if current_file_size:
            downloaded_mb = current_file_size[0] / (1024 * 1024)
            total_mb = current_file_size[1] / (1024 * 1024)
            self.file_progress_label.setText(_("progress.file_size_mb", downloaded=f"{downloaded_mb:.1f}", total=f"{total_mb:.1f}"))
            
            # 显示当前文件进度
            if total_count and total_count > 0:
                # 如果知道总数，基于文件数计算总进度
                file_progress = (downloaded_count / total_count) * 100
                # 加上当前文件的部分进度
                if current_file_size[1] > 0:
                    current_file_progress = (current_file_size[0] / current_file_size[1]) / total_count * 100
                    file_progress += current_file_progress
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(int(file_progress))
            else:
                # 否则只显示当前文件进度
                if current_file_size[1] > 0:
                    progress = int((current_file_size[0] / current_file_size[1]) * 100)
                    self.progress_bar.setMaximum(100)
                    self.progress_bar.setValue(progress)
                else:
                    # 文件大小未知时，显示空进度条
                    self.progress_bar.setMaximum(100)
                    self.progress_bar.setValue(0)
        else:
            self.file_progress_label.setText("")
            # 如果有总数，显示整体进度
            if total_count and total_count > 0:
                progress = int((downloaded_count / total_count) * 100)
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(progress)
            else:
                # 没有当前文件进度时，显示空进度条而非不确定状态
                self.progress_bar.setMaximum(100)
                self.progress_bar.setValue(0)
    
    def show_terminated(self):
        """显示已终止状态"""
        self._current_state = 'terminated'
        self._current_params = {}
        
        self.status_label.setText(_("progress.terminated"))
        self.retry_label.setText("")
        self.process_label.setText("")
        self.file_progress_label.setText("")
        # 进度条为空
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
    
    def show_idle(self):
        """显示空闲状态（隐藏进度条）"""
        self._current_state = 'idle'
        self._current_params = {}
        self._reset()
    
    def show_paused(self):
        """显示暂停状态"""
        self._current_state = 'paused'
        self._current_params = {}
        
        self.status_label.setText(_("progress.paused"))
        self.retry_label.setText("")
        self.file_progress_label.setText("")
        # 进度条为空且不动
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
    
    def show_completed(self):
        """显示完成状态"""
        self._current_state = 'completed'
        self._current_params = {}
        
        self.status_label.setText(_("progress.completed"))
        self.retry_label.setText("")
        self.file_progress_label.setText("")
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)
    
    def refresh_texts(self):
        """刷新所有文本（用于语言切换）"""
        if self._current_state == 'idle':
            self._reset()
        elif self._current_state == 'config_loaded':
            self.show_config_loaded()
        elif self._current_state == 'detecting':
            self.show_detecting(
                self._current_params.get('loaded_count', 0),
                self._current_params.get('total_count')
            )
        elif self._current_state == 'downloading':
            self.show_downloading(
                self._current_params.get('downloaded_count', 0),
                self._current_params.get('total_count'),
                self._current_params.get('current_file_size'),
                self._current_params.get('retry_count', 0)
            )
        elif self._current_state == 'paused':
            self.show_paused()
        elif self._current_state == 'terminated':
            self.show_terminated()
        elif self._current_state == 'completed':
            self.show_completed()

