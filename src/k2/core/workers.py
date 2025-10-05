"""
后台工作线程
"""
import os
import time
import concurrent.futures
import threading
from PyQt6.QtCore import QThread, pyqtSignal

from ..utils.i18n import get_text, _
from ..utils.network import (
    COMMON_HEADERS, make_robust_request, parse_json_response,
    get_domain_config, extract_post_info, extract_creator_info
)
from ..utils.formatters import format_name_from_template
from ..core.detector import detect_files_from_post
from ..core.api import get_creator_profile as get_creator_info, get_creator_tags as get_creator_tags_with_counts
from ..core.downloader import download_file, get_file_size


def _get_creator_name(service: str, creator_id: str, domain_config: dict) -> str:
    """获取创作者名称"""
    creator_info = get_creator_info(service, creator_id, domain_config)
    return creator_info.get('name', creator_id)


# Worker for detecting files from a URL
class DetectionWorker(QThread):
    finished = pyqtSignal(str, str, dict)      # Signal: service, creator_id, domain_config (大数据存储在实例属性中)
    creator_info_detected = pyqtSignal(dict)  # 新增：传递作者信息的信号
    error = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # Signal for progress updates (loaded_count, total_count)

    def __init__(self, url: str, extensions: set, source_filters: set, parent=None):
        super().__init__(parent)
        self.url = url
        self.extensions = extensions
        self.source_filters = source_filters
        
        # 存储检测结果（避免通过信号传递大数据）
        self.all_data = []
        self.creator_tags = set()
        self.creator_tags_with_counts = {}

    def run(self):
        try:
            from ..core.detector import get_files_for_url
            all_data = []
            service, creator_id, domain_config = None, None, None
            creator_tags = set()

            # Determine context from URL
            is_creator_url = False
            try: # is it a post url?
                service, creator_id, post_id = extract_post_info(self.url)
            except ValueError: # must be a creator url
                service, creator_id = extract_creator_info(self.url)
                is_creator_url = True
            domain_config = get_domain_config(self.url)

            # 如果是创作者URL，获取并发送作者详细信息
            total_posts = 0
            if is_creator_url:
                creator_info = get_creator_info(service, creator_id, domain_config)
                if creator_info:
                    self.creator_info_detected.emit(creator_info)
                    total_posts = creator_info.get('post_count', 0)

            # Get creator tags for both creator URLs and post URLs
            creator_tags_with_counts = get_creator_tags_with_counts(service, creator_id, domain_config)
            creator_tags = set(creator_tags_with_counts.keys())
            # Store creator tags for later use

            # get_files_for_url yields raw post JSONs for creator URLs,
            # and pre-processed dicts for single post URLs.
            collected_count = 0
            last_update_time = 0
            
            # 预处理所有帖子数据（在worker线程中），避免在主线程UI中处理大量数据导致栈溢出
            creator_name = None
            if is_creator_url:
                creator_name = _get_creator_name(service, creator_id, domain_config)
            
            # 使用try-except包裹迭代，捕获潜在错误
            try:
                for raw_data in get_files_for_url(self.url, self.extensions, self.source_filters):
                    if not raw_data:
                        continue
                    
                    # 如果是已处理的数据（有post_info字段），直接使用
                    if 'post_info' in raw_data:
                        all_data.append(raw_data)
                    else:
                        # 原始数据，在worker线程中预处理
                        try:
                            post_details, files = detect_files_from_post(
                                raw_data, 
                                domain_config['base_url'].replace('https://', ''), 
                                set(),  # 检测所有文件类型
                                {"file", "attachments", "content"}
                            )
                            
                            # 显示所有帖子，即使没有文件（保持与网页顺序一致）
                            post_details['post_title'] = post_details.pop('title', None)
                            post_info = {
                                "service": service.capitalize(), 
                                "creator_id": creator_id, 
                                "creator_name": creator_name,
                                "post_id": post_details.pop('id', None),
                                **post_details
                            }
                            all_data.append({"post_info": post_info, "files": files})  # files可能为空列表
                        except Exception as parse_error:
                            # 单个帖子解析失败不应该中断整个流程
                            print(f"⚠️ 解析帖子失败: {parse_error}")
                            continue
                    
                    collected_count += 1
                    
                    # 每50个帖子或每0.5秒更新一次进度（避免过于频繁）
                    current_time = time.time()
                    if collected_count % 50 == 0 or (current_time - last_update_time) >= 0.5:
                        self.progress_update.emit(collected_count, total_posts)
                        last_update_time = current_time
            except Exception as iteration_error:
                print(f"❌ 迭代获取文件时发生错误: {iteration_error}")
                import traceback
                traceback.print_exc()
            
            # 检测完成后保存缓存
            from ..utils.cache import get_cache_manager
            cache = get_cache_manager()
            cache.flush_pending_cache()
            
            # 存储数据到实例属性（避免通过信号传递大数据导致栈溢出）
            self.all_data = all_data
            self.creator_tags = creator_tags
            self.creator_tags_with_counts = creator_tags_with_counts
            
            # 只传递元数据
            self.finished.emit(service, creator_id, domain_config)
            
        except Exception as e:
            self.error.emit(f"检测文件时发生未预期错误: {e}")


# Worker for filtering posts by tags and coordinating downloads
class TagFilterDownloadCoordinator(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    file_completed = pyqtSignal(str)  # url of the completed file
    progress_update = pyqtSignal(str)  # progress message
    stats_update = pyqtSignal(int, int)  # downloaded_files_count, processed_posts_count
    download_summary = pyqtSignal(dict)  # 下载完成后的统计信息 {success, failed, failed_files}
    file_progress = pyqtSignal(int, int, int)  # downloaded_bytes, total_bytes, retry_count

    def __init__(self, detected_files_data: list, tag_filter_enabled: bool, selected_tags: set, 
                 allowed_exts: set, download_settings: dict, 
                 pause_event, tags_with_counts: dict = None, start_post_id: str = "", end_post_id: str = "", parent=None):
        super().__init__(parent)
        self.detected_files_data = detected_files_data
        self.tag_filter_enabled = tag_filter_enabled
        self.selected_tags = selected_tags
        self.allowed_exts = allowed_exts
        self.download_settings = download_settings
        self.pause_event = pause_event
        self.tags_with_counts = tags_with_counts or {}
        self.start_post_id = start_post_id
        self.end_post_id = end_post_id
        
        # UI批量更新优化
        self.ui_update_batch_size = 5  # 每5个文件更新一次UI
        self.ui_update_interval = 1000  # 1秒强制更新一次
        self.last_ui_update = 0
        self.last_downloaded_count = 0
        self.last_processed_count = 0
        
        # 大文件下载控制（50MB阈值）
        self.large_file_threshold = 50 * 1024 * 1024  # 50MB in bytes
        self.large_file_future = None  # 当前正在下载的大文件的future对象
        self.current_large_file_lock = threading.Lock()
        self.current_large_file_progress = None  # (downloaded, total)
        self.retry_count = 0  # 正在重试的文件数
        
        # 跟踪所有文件的下载进度
        self.all_files_progress = {}  # {url: (downloaded, total)}
        self.all_files_progress_lock = threading.Lock()
        
        # 跟踪正在重试的文件
        self.retrying_files = set()  # 正在重试的文件URL集合
        self.retrying_files_lock = threading.Lock()
    
    def is_ext_match(self, file_ext: str) -> bool:
        """
        判断文件扩展名是否匹配过滤器
        如果allowed_exts包含.001，则.001-.999都会被匹配
        """
        # 直接匹配
        if file_ext in self.allowed_exts:
            return True
        
        # 如果.001在过滤器中，检查是否为数字扩展名（.001-.999）
        if ".001" in self.allowed_exts and file_ext.startswith(".") and len(file_ext) == 4:
            # 检查是否为3位数字
            if file_ext[1:].isdigit():
                return True
        
        return False

    def _should_update_ui(self, downloaded_files_count, matched_posts_count):
        """判断是否应该更新UI"""
        current_time = time.time() * 1000  # 转换为毫秒
        
        # 检查是否达到批量大小
        files_diff = downloaded_files_count - self.last_downloaded_count
        
        # 达到批量大小或超过时间间隔时更新
        if (files_diff >= self.ui_update_batch_size or 
            current_time - self.last_ui_update >= self.ui_update_interval):
            self.last_ui_update = current_time
            self.last_downloaded_count = downloaded_files_count
            self.last_processed_count = matched_posts_count
            return True
        return False
    
    def _create_progress_callback(self, url: str, is_large_file: bool):
        """创建进度回调函数"""
        last_emit_time = [0]  # 使用列表来存储可变值
        min_emit_interval = 0.1  # 最小发射间隔（秒）
        
        def callback(downloaded, total):
            # 记录所有文件的进度
            with self.all_files_progress_lock:
                self.all_files_progress[url] = (downloaded, total)
            
            # 限制信号发射频率，避免栈溢出
            current_time = time.time()
            if current_time - last_emit_time[0] < min_emit_interval:
                return  # 跳过太频繁的更新
            
            last_emit_time[0] = current_time
            
            # 如果是大文件，单独记录并发送信号
            if is_large_file:
                with self.current_large_file_lock:
                    self.current_large_file_progress = (downloaded, total)
                # 发送大文件进度信号
                self.file_progress.emit(downloaded, total, self.retry_count)
            else:
                # 小文件：如果没有大文件在下载，发送所有文件的综合进度
                with self.current_large_file_lock:
                    has_large_file = self.current_large_file_progress is not None
                
                if not has_large_file:
                    # 计算所有小文件的总进度
                    with self.all_files_progress_lock:
                        total_downloaded = sum(d for d, t in self.all_files_progress.values())
                        total_size = sum(t for d, t in self.all_files_progress.values())
                    
                    if total_size > 0:
                        self.file_progress.emit(total_downloaded, total_size, self.retry_count)
        return callback
    
    def _create_retry_callback(self, url: str):
        """创建重试回调函数"""
        def callback(attempt, is_retrying):
            with self.retrying_files_lock:
                if is_retrying:
                    # 文件正在重试，加入集合
                    self.retrying_files.add(url)
                else:
                    # 文件下载成功或停止重试，从集合移除
                    self.retrying_files.discard(url)
                
                # 更新重试计数
                self.retry_count = len(self.retrying_files)
        return callback

    def run(self):
        try:
            # 早期检查：如果没有允许的扩展名，直接结束
            if not self.allowed_exts:
                return
            
            # 早期检查：预先扫描是否有任何符合扩展名条件的文件
            has_eligible_files = False
            for post_data in self.detected_files_data:
                files_in_post = post_data.get("files", [])
                for file_info in files_in_post:
                    file_ext = os.path.splitext(file_info.get("name", ""))[1].lower()
                    if self.is_ext_match(file_ext):
                        has_eligible_files = True
                        break
                if has_eligible_files:
                    break
            
            # 如果没有符合扩展名条件的文件，直接结束
            if not has_eligible_files:
                return
            
            # Create download executor with optimized settings
            max_workers = min(self.download_settings['threads'], 10)  # 限制最大线程数
            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="download"
            )
            download_futures = {}
            active_downloads = 0  # 跟踪活跃下载数
            
            total_posts = len(self.detected_files_data)
            processed_posts = 0
            matched_posts_count = 0  # 用于早期终止的计数器
            downloaded_files_count = 0  # 已下载文件计数
            failed_files_count = 0  # 失败文件计数
            failed_files_list = []  # 失败文件列表 [(file_name, url, error)]
            
            # 跟踪每个帖子的下载情况（简单计数）
            post_download_tracker = {}  # {post_key: {"total": 10, "completed": 5, "post_info": {...}}}
            url_to_post_key = {}  # URL -> post_key 映射，用于在下载完成时找到对应的帖子
            
            # 帖子ID范围过滤
            started = not self.start_post_id  # 如果没有起始ID，则从一开始就启用
            
            for post_data in self.detected_files_data:
                if self.pause_event.is_set():
                    # Gracefully shutdown executor
                    executor.shutdown(wait=False, cancel_futures=True)
                    return
                    
                try:
                    post_info = post_data.get("post_info", {})
                    post_id = str(post_info.get('post_id', ''))
                    
                    # 检查是否到达起始帖子ID
                    if not started:
                        if post_id == self.start_post_id:
                            started = True
                            # 找到起始ID，继续处理这个帖子（不跳过）
                        else:
                            continue  # 跳过起始ID之前的帖子
                    
                    processed_posts += 1
                    files_in_post = post_data.get("files", [])
                    
                    # 进度输出（简化：只在关键节点显示）
                    if processed_posts == 1 or processed_posts % 50 == 0:
                        if self.tag_filter_enabled and self.selected_tags:
                            # 标签过滤：只显示已处理数量，不显示总数
                            tags_preview = "、".join(list(self.selected_tags)[:3])
                            if len(self.selected_tags) > 3:
                                tags_preview += "..."
                            print(f"📊 处理: {processed_posts} 帖子 (标签: {tags_preview})")
                        else:
                            # 未启用标签过滤：显示所有帖子总数
                            print(f"📊 处理: {processed_posts}/{total_posts} 帖子")
                    
                    # === 标签过滤检查 ===
                    # If tag filtering is enabled, we need to get detailed post data to check tags
                    if self.tag_filter_enabled and self.selected_tags:
                        # Get detailed post data via post API
                        post_id = post_info.get('post_id')
                        creator_id = post_info.get('creator_id')
                        service = post_info.get('service', '').lower()
                        
                        if not all([post_id, creator_id, service]):
                            continue  # 跳过帖子：缺少必要信息
                        
                        # Construct post API URL
                        # We need domain config, let's determine it from service
                        if service == 'patreon':
                            domain_config = {'api_base': 'https://kemono.cr/api/v1', 'referer': 'https://kemono.cr/', 'base_url': 'https://kemono.cr'}
                        else:
                            domain_config = {'api_base': 'https://coomer.st/api/v1', 'referer': 'https://coomer.st/', 'base_url': 'https://coomer.st'}
                        
                        post_api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}/post/{post_id}"
                        
                        # Get detailed post data
                        headers = COMMON_HEADERS.copy()
                        headers["Referer"] = domain_config['referer']
                        
                        try:
                            response = make_robust_request(post_api_url, headers, max_retries=2, timeout=15)
                            if not response:
                                continue  # 跳过帖子（API请求失败）
                            
                            detailed_post_data = parse_json_response(response)
                            if not detailed_post_data:
                                continue  # 跳过帖子（数据解析失败）
                        except Exception as api_error:
                            continue  # 跳过帖子（请求异常）
                        
                        # Extract tags from detailed post data
                        actual_post_content = detailed_post_data.get('post', detailed_post_data)
                        post_tags = set(actual_post_content.get('tags', []) or [])
                        
                        # Apply tag filtering (包含模式：帖子必须包含所有选中的标签)
                        post_matches_filter = self.selected_tags.issubset(post_tags)
                        
                        # Skip post if it doesn't match filter
                        if not post_matches_filter:
                            continue
                        
                        # Re-detect files from detailed post data to ensure we have complete file info
                        post_details, updated_files = detect_files_from_post(
                            detailed_post_data,
                            domain_config['base_url'].replace('https://', ''),
                            self.allowed_exts,
                            {"file", "attachments", "content"}
                        )
                        files_in_post = updated_files
                
                    # Count eligible files in this post
                    eligible_files_count = 0
                    for file_info in files_in_post:
                        file_ext = os.path.splitext(file_info.get("name", ""))[1].lower()
                        if self.is_ext_match(file_ext):
                            eligible_files_count += 1
                    
                    # Only log and process if post has eligible files
                    if eligible_files_count > 0:
                        matched_posts_count += 1
                        post_title = post_info.get('post_title', 'Untitled')
                    else:
                        # Skip if no eligible files
                        continue
                
                    # 初始化帖子下载跟踪
                    service = post_info.get('service', '').lower()
                    creator_id_str = str(post_info.get('creator_id', ''))
                    post_id_str = str(post_info.get('post_id', ''))
                    post_key = f"{service}:{creator_id_str}:{post_id_str}"
                    
                    if post_key and post_key not in post_download_tracker:
                        post_download_tracker[post_key] = {
                            "total": eligible_files_count,
                            "completed": 0,
                            "post_info": post_info
                        }
                    
                    # Process files in this post
                    for file_info in files_in_post:
                        # 在处理每个文件前检查暂停信号
                        if self.pause_event.is_set():
                            print(f"⏸️ 检测到暂停信号，停止提交新任务...")
                            executor.shutdown(wait=False, cancel_futures=True)
                            return
                        
                        file_name_with_ext = file_info.get("name", "")
                        
                        # 确保文件名包含扩展名
                        if not file_name_with_ext:
                            continue
                        
                        file_name_original, file_ext_with_dot = os.path.splitext(file_name_with_ext)
                        
                        # 如果分离后没有扩展名，尝试从URL中获取
                        if not file_ext_with_dot:
                            url = file_info.get("url", "")
                            _, url_ext = os.path.splitext(url.split('?')[0])  # 移除URL参数
                            if url_ext:
                                file_ext_with_dot = url_ext.lower()
                                file_name_with_ext = file_name_original + file_ext_with_dot
                        
                        # Check if file extension is allowed
                        if not self.is_ext_match(file_ext_with_dot.lower()):
                            continue
                        
                        # 最后确保扩展名存在（安全检查）
                        if not file_ext_with_dot:
                            continue
                        
                        # Construct file path
                        creator_folder_name = format_name_from_template(
                            self.download_settings["creator_folder_name_template"], post_info
                        )
                        post_folder_name = format_name_from_template(
                            self.download_settings["post_folder_name_template"], post_info
                        )
                        
                        file_name_data = {
                            **post_info, 
                            "file_name_original": file_name_original, 
                            "file_ext": file_ext_with_dot 
                        }
                        
                        final_file_name = format_name_from_template(
                            self.download_settings["file_name_template"], file_name_data
                        )
                        
                        full_path = os.path.join(
                            self.download_settings["download_root"], 
                            creator_folder_name, 
                            post_folder_name, 
                            final_file_name
                        )
                        
                        # 及时清理已完成的任务，避免队列堆积
                        completed_futures = []
                        for future in list(download_futures.keys()):
                            if future.done():
                                completed_futures.append(future)
                        
                        # 处理所有已完成的任务（静默清理）
                        if len(completed_futures) > 0:
                            pass  # 静默清理已完成的任务
                        
                        for completed_future in completed_futures:
                            url = download_futures[completed_future]
                            del download_futures[completed_future]
                            
                            # 清理该文件的进度记录
                            with self.all_files_progress_lock:
                                self.all_files_progress.pop(url, None)
                            
                            # 如果是大文件，清理大文件进度
                            if completed_future == self.large_file_future:
                                with self.current_large_file_lock:
                                    self.current_large_file_progress = None
                                self.large_file_future = None
                            
                            try:
                                path, file_hash = completed_future.result()
                                if path:
                                    downloaded_files_count += 1
                                    if self._should_update_ui(downloaded_files_count, matched_posts_count):
                                        self.stats_update.emit(downloaded_files_count, matched_posts_count)
                                    
                                    # 更新帖子下载计数
                                    p_key = url_to_post_key.get(url)
                                    if p_key and p_key in post_download_tracker:
                                        post_download_tracker[p_key]["completed"] += 1
                                        tracker = post_download_tracker[p_key]
                                        
                                        # 如果帖子所有文件都下载完成，显示提示
                                        if tracker["completed"] >= tracker["total"]:
                                            p_info = tracker["post_info"]
                                            print(f"✅ 帖子已完成: {p_info.get('post_title', 'Untitled')} ({tracker['completed']}/{tracker['total']})")
                                else:
                                    failed_files_count += 1
                            except Exception as e:
                                failed_files_count += 1
                                file_name = os.path.basename(url)
                                failed_files_list.append((file_name, url, str(e)))
                        
                        # 如果队列太满，等待任务完成（避免内存占用过高）
                        wait_attempts = 0
                        max_wait_attempts = 10  # 最多等待10次
                        while len(download_futures) >= max_workers * 3:
                            if wait_attempts >= max_wait_attempts:
                                # 队列过满但等待超时，强制继续添加任务
                                break
                            
                            try:
                                # 检查是否有任务完成
                                if not download_futures:
                                    break
                                
                                completed_future = next(concurrent.futures.as_completed(download_futures.keys(), timeout=0.5))
                                url = download_futures[completed_future]
                                del download_futures[completed_future]
                                
                                # 清理该文件的进度记录
                                with self.all_files_progress_lock:
                                    self.all_files_progress.pop(url, None)
                                
                                # 如果是大文件，清理大文件进度
                                if completed_future == self.large_file_future:
                                    with self.current_large_file_lock:
                                        self.current_large_file_progress = None
                                    self.large_file_future = None
                                
                                try:
                                    path, file_hash = completed_future.result()
                                    if path:
                                        downloaded_files_count += 1
                                        if self._should_update_ui(downloaded_files_count, matched_posts_count):
                                            self.stats_update.emit(downloaded_files_count, matched_posts_count)
                                    else:
                                        failed_files_count += 1
                                except Exception as e:
                                    failed_files_count += 1
                                    file_name = os.path.basename(url)
                                    failed_files_list.append((file_name, url, str(e)))
                                
                                break
                            except concurrent.futures.TimeoutError:
                                wait_attempts += 1
                                # 超时后再次检查已完成的任务
                                for future in list(download_futures.keys()):
                                    if future.done():
                                        url = download_futures[future]
                                        del download_futures[future]
                                        
                                        # 清理该文件的进度记录
                                        with self.all_files_progress_lock:
                                            self.all_files_progress.pop(url, None)
                                        
                                        # 如果是大文件，清理大文件进度
                                        if future == self.large_file_future:
                                            with self.current_large_file_lock:
                                                self.current_large_file_progress = None
                                            self.large_file_future = None
                                        
                                        try:
                                            path, file_hash = future.result()
                                            if path:
                                                downloaded_files_count += 1
                                        except:
                                            pass
                                continue
                        
                        # 检查文件大小以决定下载策略
                        file_url = file_info["url"]
                        file_size = get_file_size(file_url, COMMON_HEADERS, timeout=5)
                        is_large_file = file_size > self.large_file_threshold
                        
                        # 如果是大文件（>50MB），等待之前的大文件下载完成
                        if is_large_file:
                            if self.large_file_future and not self.large_file_future.done():
                                # 等待当前大文件下载完成
                                prev_url = download_futures.get(self.large_file_future)
                                try:
                                    path, file_hash = self.large_file_future.result()
                                    if path:
                                        downloaded_files_count += 1
                                        if self._should_update_ui(downloaded_files_count, matched_posts_count):
                                            self.stats_update.emit(downloaded_files_count, matched_posts_count)
                                        
                                        # 更新帖子下载计数
                                        if prev_url:
                                            p_key = url_to_post_key.get(prev_url)
                                            if p_key and p_key in post_download_tracker:
                                                post_download_tracker[p_key]["completed"] += 1
                                                tracker = post_download_tracker[p_key]
                                                if tracker["completed"] >= tracker["total"]:
                                                    p_info = tracker["post_info"]
                                                    print(f"✅ 帖子已完成: {p_info.get('post_title', 'Untitled')} ({tracker['completed']}/{tracker['total']})")
                                    else:
                                        failed_files_count += 1
                                except Exception as e:
                                    failed_files_count += 1
                                    if prev_url:
                                        file_name = os.path.basename(prev_url)
                                        failed_files_list.append((file_name, prev_url, str(e)))
                                
                                # 清理已完成的future和进度记录
                                if self.large_file_future in download_futures:
                                    del download_futures[self.large_file_future]
                                if prev_url:
                                    with self.all_files_progress_lock:
                                        self.all_files_progress.pop(prev_url, None)
                                # 清理大文件进度标记
                                with self.current_large_file_lock:
                                    self.current_large_file_progress = None
                                self.large_file_future = None
                            
                            # 提交新的大文件下载任务
                            file_size_mb = file_size / (1024 * 1024)
                            print(f"📦 大文件检测: {final_file_name} ({file_size_mb:.1f}MB) - 使用串行下载")
                        
                        # Submit download task（为所有文件创建进度回调和重试回调）
                        progress_callback = self._create_progress_callback(file_url, is_large_file)
                        retry_callback = self._create_retry_callback(file_url)
                        future = executor.submit(
                            download_file, 
                            file_url, 
                            full_path, 
                            COMMON_HEADERS, 
                            cancel_event=self.pause_event,
                            progress_callback=progress_callback,
                            retry_callback=retry_callback
                        )
                        download_futures[future] = file_url  # 恢复原始结构
                        url_to_post_key[file_url] = post_key  # 建立URL到帖子的映射
                        active_downloads += 1
                        
                        # 如果是大文件，记录其future以便后续等待
                        if is_large_file:
                            self.large_file_future = future
                    
                    # 检查是否到达结束帖子ID
                    if self.end_post_id and post_id == self.end_post_id:
                        print(f"✅ 已到达结束帖子ID: {self.end_post_id}，停止下载")
                        break
                        
                except Exception as post_error:
                    # 单个帖子处理失败不应该中断整个下载进程
                    post_title = post_info.get('post_title', 'Unknown') if 'post_info' in locals() else 'Unknown'
                    print(f"⚠️ 处理帖子 '{post_title}' 时出错: {post_error}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"✓ 帖子检测完成，共处理 {processed_posts}/{total_posts} 个帖子，匹配 {matched_posts_count} 个")
            
            # Wait for all downloads to complete
            completed_count = 0
            total_downloads = len(download_futures)
            
            print(f"📥 等待任务完成...")
            
            # 如果没有下载任务，直接结束
            if total_downloads == 0:
                print("✓ 没有符合条件的文件需要下载")
                return
            
            try:
                # 先清理所有已完成的任务
                # 检查已完成的任务
                completed_futures = []
                for future in list(download_futures.keys()):
                    if future.done():
                        completed_futures.append(future)
                
                # 处理已完成的任务
                for completed_future in completed_futures:
                    url = download_futures[completed_future]
                    del download_futures[completed_future]
                    completed_count += 1
                    
                    # 清理该文件的进度记录
                    with self.all_files_progress_lock:
                        self.all_files_progress.pop(url, None)
                    
                    # 清理该文件的重试状态
                    with self.retrying_files_lock:
                        self.retrying_files.discard(url)
                        self.retry_count = len(self.retrying_files)
                    
                    # 如果是大文件，清理大文件进度
                    if completed_future == self.large_file_future:
                        with self.current_large_file_lock:
                            self.current_large_file_progress = None
                        self.large_file_future = None
                    
                    try:
                        path, file_hash = completed_future.result()
                        if path:
                            downloaded_files_count += 1
                        else:
                            failed_files_count += 1
                    except Exception as e:
                        failed_files_count += 1
                        file_name = os.path.basename(url)
                        failed_files_list.append((file_name, url, str(e)))
                
                # 更新剩余任务数
                remaining_tasks = len(download_futures)
                # 等待剩余任务
                
                # 等待剩余的任务
                if remaining_tasks > 0:
                    pass  # 等待剩余任务
                    processed_in_loop = 0
                    for future in concurrent.futures.as_completed(download_futures, timeout=None):
                        if self.pause_event.is_set():
                            print("⏸️  检测到暂停信号")
                            break  # 检测到暂停信号
                            
                        url = download_futures[future]
                        completed_count += 1
                        processed_in_loop += 1
                        
                        # 清理该文件的进度记录
                        with self.all_files_progress_lock:
                            self.all_files_progress.pop(url, None)
                        
                        # 清理该文件的重试状态
                        with self.retrying_files_lock:
                            self.retrying_files.discard(url)
                            self.retry_count = len(self.retrying_files)
                        
                        # 如果是大文件，清理大文件进度
                        if future == self.large_file_future:
                            with self.current_large_file_lock:
                                self.current_large_file_progress = None
                            self.large_file_future = None
                        
                        # 显示进度（简化）
                        if completed_count % 50 == 0 or completed_count == total_downloads:
                            print(f"⏳ {completed_count}/{total_downloads}")
                        
                        try:
                            path, file_hash = future.result()
                            if path:  # 只要有路径就认为下载成功
                                downloaded_files_count += 1
                                # 只在满足条件时更新UI，减少信号发送频率
                                if self._should_update_ui(downloaded_files_count, matched_posts_count):
                                    self.stats_update.emit(downloaded_files_count, matched_posts_count)
                            else:
                                failed_files_count += 1
                                file_name = os.path.basename(url)
                                failed_files_list.append((file_name, url, "Download returned None"))
                        except InterruptedError:
                            print("⏸️  任务被中断")
                            continue  # 下载已暂停（不计入失败）
                        except Exception as exc:
                            print(f"⚠️  任务异常: {exc}")
                            failed_files_count += 1
                            file_name = os.path.basename(url)
                            failed_files_list.append((file_name, url, str(exc)))
                        
                        # 检查是否所有任务都已处理
                        if processed_in_loop >= remaining_tasks:
                            print(f"✓ 已处理所有 {remaining_tasks} 个剩余任务，退出循环")
                            break
                    
                    print(f"🏁 as_completed 循环结束（处理了 {processed_in_loop} 个任务）")
                
                print(f"✓ 所有任务已完成: 成功 {downloaded_files_count}, 失败 {failed_files_count}")
                
                if self.pause_event.is_set():
                    print("⏸️  检测到暂停，关闭执行器...")
                    executor.shutdown(wait=False, cancel_futures=True)
                    return
                else:
                    print("📊 发送最终统计...")
                    # 下载完成时发送最终的UI更新
                    self.stats_update.emit(downloaded_files_count, matched_posts_count)
                    
                    # 发送下载统计摘要
                    summary = {
                        'success': downloaded_files_count,
                        'failed': failed_files_count,
                        'failed_files': failed_files_list[:20]  # 最多显示20个失败文件
                    }
                    self.download_summary.emit(summary)
                    
                    print("🔒 关闭下载执行器...")
                    
                    executor.shutdown(wait=True)
                    print("✅ 下载流程完成！")
                    
            except Exception as e:
                # 等待下载完成时发生错误
                executor.shutdown(wait=False, cancel_futures=True)
                raise
                
        except Exception as e:
            self.error.emit(f"标签过滤下载协调器发生错误: {e}")
        finally:
            self.finished.emit()

