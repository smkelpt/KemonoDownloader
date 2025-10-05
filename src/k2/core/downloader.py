"""
文件下载模块
处理文件下载、断点续传、重试等
"""
import os
import time
import requests
from ..utils.network import get_session


def get_file_size(url: str, headers: dict, timeout: int = 10) -> int:
    """通过HEAD请求获取文件大小
    
    Args:
        url: 文件URL
        headers: HTTP请求头
        timeout: 超时时间（秒）
        
    Returns:
        文件大小（字节），如果无法获取则返回0
    """
    try:
        session = get_session()
        response = session.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # 尝试从 Content-Length 头获取文件大小
        content_length = response.headers.get('Content-Length')
        if content_length:
            return int(content_length)
        
        return 0
    except Exception as e:
        # 如果HEAD请求失败，返回0（将被视为小文件）
        return 0


def download_file(url: str, dest_path: str, headers: dict, max_retries: int = None, 
                 chunk_size: int = 8192, cancel_event=None, progress_callback=None, retry_callback=None) -> tuple[str | None, str | None]:
    """下载文件到指定完整路径，支持重试、断点续传和原子性保存
    
    Args:
        url: 文件URL
        dest_path: 目标保存路径
        headers: HTTP请求头
        max_retries: 最大重试次数
        chunk_size: 下载块大小
        cancel_event: 取消事件
        progress_callback: 进度回调函数
        retry_callback: 重试回调函数 (attempt, is_retrying)
        
    Returns:
        (下载成功的文件路径, 错误信息) 元组
        
    下载机制：
    - 临时文件使用 .part 后缀，只有完整下载才会重命名为最终文件
    - 如果存在同名文件，将覆盖已有文件
    - 支持断点续传，检测到 .part 文件会尝试继续下载
    """
    if cancel_event and cancel_event.is_set():
        return None, None

    dest_folder = os.path.dirname(dest_path)
    os.makedirs(dest_folder, exist_ok=True)
    filename = os.path.basename(dest_path)
    part_path = dest_path + ".part"

    # 下载循环
    attempt = 1
    while True:
        try:
            headers_for_request = headers.copy()
            downloaded_size = 0
            open_mode = "wb"

            if os.path.exists(part_path):
                downloaded_size = os.path.getsize(part_path)
                headers_for_request["Range"] = f"bytes={downloaded_size}-"
                open_mode = "ab"
                print(f"检测到部分文件，从 {downloaded_size} 字节处续传: {filename}")

            session = get_session()
            with session.get(url, headers=headers_for_request, stream=True, timeout=30) as r:
                r.raise_for_status()

                if r.status_code != 206 and downloaded_size > 0:
                    print(f"服务器不支持断点续传，将重新下载: {filename}")
                    downloaded_size = 0
                    open_mode = "wb"
                
                # 获取总文件大小
                total_size = int(r.headers.get('Content-Length', 0))
                if downloaded_size > 0 and total_size > 0:
                    total_size += downloaded_size
                
                with open(part_path, open_mode) as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if cancel_event and cancel_event.is_set():
                            raise InterruptedError("下载被用户暂停。")
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 调用进度回调
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded_size, total_size)
            
            os.replace(part_path, dest_path)
            # 成功下载，通知不再重试
            if retry_callback and attempt > 1:
                retry_callback(attempt, False)
            return dest_path, None

        except InterruptedError:
            raise
        except requests.exceptions.HTTPError as e:
            # 检查是否已暂停
            if cancel_event and cancel_event.is_set():
                return None, None
                
            if e.response.status_code == 416:
                print(f"下载 '{filename}' 范围错误，可能是文件已下载完成。将删除临时文件并重试。")
                if os.path.exists(part_path):
                    os.remove(part_path)
                continue
            # 只在未暂停时输出错误信息
            print(f"下载 '{filename}' 失败（第 {attempt} 次尝试）: {e}")
            # 通知正在重试
            if retry_callback:
                retry_callback(attempt, True)
            sleep_time = min(2 ** min(attempt, 6), 60)
            time.sleep(sleep_time)
            attempt += 1
        except Exception as e:
            # 检查是否已暂停
            if cancel_event and cancel_event.is_set():
                return None, None
            # 只在未暂停时输出错误信息
            print(f"下载 '{filename}' 失败（第 {attempt} 次尝试）: {e}")
            # 通知正在重试
            if retry_callback:
                retry_callback(attempt, True)
            sleep_time = min(2 ** min(attempt, 6), 60)
            time.sleep(sleep_time)
            attempt += 1

