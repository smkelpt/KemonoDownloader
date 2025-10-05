"""
常量和枚举定义
"""
import os
from enum import Enum, auto


class DownloadState(Enum):
    """下载状态枚举"""
    IDLE = auto()
    DOWNLOADING = auto()
    PAUSED = auto()


# 默认设置
DEFAULT_SETTINGS = {
    "default_download_path": os.path.expanduser("~/Desktop"),  # 默认下载路径为用户桌面
    "creator_folder_name_template": "{creator_name} ({creator_id}) - {service}",
    "post_folder_name_template": "{post_id} {post_title}",
    "file_name_template": "{file_name_original}{file_ext}",
    "concurrency": 5,
    "filter_extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi", ".mkv", ".ts", ".zip", ".rar", ".7z", ".tar", ".001"],
    "language": "en_US"  # 默认语言为英文
}

