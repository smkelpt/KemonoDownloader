"""
文件检测模块
从帖子中检测和提取可下载的文件
"""
import os
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup
from ..utils.network import get_domain_config, make_robust_request, parse_json_response, COMMON_HEADERS, extract_post_info


def detect_files_from_post(post_data: dict, service_domain: str, allowed_extensions: set, source_filters: set) -> Tuple[dict, List[dict]]:
    """从帖子数据中检测并提取可下载的文件 URL
    
    Args:
        post_data: 帖子数据字典
        service_domain: 服务域名
        allowed_extensions: 允许的文件扩展名集合
        source_filters: 文件来源过滤器集合 (file, attachments, content)
        
    Returns:
        (帖子信息字典, 文件列表)
    """
    post_info_data = post_data.get('post', post_data)

    # 提取帖子基本信息
    post_id = post_info_data.get('id')
    post_title = post_info_data.get('title')
    published_date = post_info_data.get('published')
    tags = post_info_data.get('tags', []) or []

    files_list = []
    seen_paths = set()

    def _add_file(path, name):
        """内部辅助函数，用于处理和添加文件"""
        if not path or not isinstance(path, str):
            return
        
        # 去重检查
        if path in seen_paths:
            return
        
        file_name = name or os.path.basename(path)
        ext = os.path.splitext(file_name)[1].lower()
        
        # 如果从文件名中无法获取扩展名，尝试从路径中获取
        if not ext:
            path_clean = path.split('?')[0]
            ext = os.path.splitext(path_clean)[1].lower()
            if ext:
                file_name = file_name + ext

        # 过滤扩展名
        if allowed_extensions and ext not in allowed_extensions:
            return

        # 构造完整URL
        if path.startswith(('http://', 'https://')):
            url = path
        else:
            url = f"https://{service_domain}{path}"
        
        files_list.append({'url': url, 'name': file_name})
        seen_paths.add(path)

    # 1. 处理 post['file']
    if "file" in source_filters:
        file_field = post_info_data.get("file")
        if file_field and isinstance(file_field, dict):
            _add_file(file_field.get("path"), file_field.get("name"))

    # 2. 处理 post['attachments']
    if "attachments" in source_filters:
        for attachment in post_info_data.get("attachments", []):
            if isinstance(attachment, dict):
                _add_file(attachment.get("path"), attachment.get("name"))

    # 3. 处理 post['content'] 中的图片
    if "content" in source_filters:
        content_html = post_info_data.get("content")
        if content_html:
            try:
                soup = BeautifulSoup(content_html, "html.parser")
                for img_tag in soup.select("img[src]"):
                    src = img_tag.get("src")
                    # 忽略 base64 编码的图片
                    if src and not src.startswith('data:image'):
                        _add_file(src, os.path.basename(src))
            except Exception as e:
                print(f"解析帖子内容失败: {e}")

    return (
        {
            'id': post_id,
            'title': post_title,
            'published': published_date,
            'tags': tags
        },
        files_list
    )


def get_files_for_url(url: str, extensions: set, source_filters: set):
    """根据 URL (帖子或创作者) 获取所有可下载文件的信息
    
    这是一个生成器函数，会逐个帖子地 yield 数据
    
    Args:
        url: 帖子或创作者URL
        extensions: 文件扩展名集合
        source_filters: 文件来源过滤器集合
        
    Yields:
        帖子数据字典 (包含 post_info 和 files)
    """
    try:
        service, creator_id, is_post, is_creator = None, None, False, False

        # 优先匹配更具体的帖子 URL 格式
        try:
            service, creator_id, post_id = extract_post_info(url)
            is_post = True
        except ValueError:
            # 如果不是帖子 URL，再尝试匹配创作者 URL
            try:
                from ..utils.network import extract_creator_info
                service, creator_id = extract_creator_info(url)
                is_creator = True
            except ValueError:
                pass
        
        if not is_post and not is_creator:
            raise ValueError(f"URL 格式无法识别: {url}")

        domain_config = get_domain_config(url)
        
        if is_creator:
            # 处理创作者 URL - 获取所有帖子
            base_api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}"
            headers = COMMON_HEADERS.copy()
            headers["Referer"] = domain_config['referer']

            posts_per_page = 50
            
            # 获取缓存管理器
            from ..utils.cache import get_cache_manager
            cache = get_cache_manager()
            
            # 步骤1: 从 profile API 获取最新的帖子总数
            from ..core.api import get_creator_profile
            creator_profile = get_creator_profile(service, creator_id, domain_config, cache_manager=cache)
            total_posts_on_server = creator_profile.get('post_count', 0)
            
            # 步骤2: 获取缓存中的帖子数量
            cached_post_count = cache.get_cached_post_count(service, creator_id)
            cached_posts = cache.get_cached_posts(service, creator_id, offset=0)
            
            # 步骤3: 判断是否需要更新
            if cached_post_count == total_posts_on_server and cached_posts:
                # 缓存数量与服务器一致，直接使用缓存
                # 分批产出缓存的帖子数据
                BATCH_SIZE = 100
                for i in range(0, len(cached_posts), BATCH_SIZE):
                    batch = cached_posts[i:i + BATCH_SIZE]
                    for post_summary in batch:
                        if isinstance(post_summary, dict) and "id" in post_summary:
                            yield post_summary
                    import time
                    time.sleep(0.001)
                return
            
            # 步骤4: 需要从API获取数据（全新或增量更新）
            # 计算需要获取的新帖子数量
            posts_to_fetch = total_posts_on_server - cached_post_count if cached_post_count > 0 else total_posts_on_server
            
            # 如果有缓存，先产出缓存的帖子
            if cached_posts and cached_post_count > 0:
                BATCH_SIZE = 100
                for i in range(0, len(cached_posts), BATCH_SIZE):
                    batch = cached_posts[i:i + BATCH_SIZE]
                    for post_summary in batch:
                        if isinstance(post_summary, dict) and "id" in post_summary:
                            yield post_summary
                    import time
                    time.sleep(0.001)
            
            # 从API获取新帖子（增量或全量）
            offset = 0
            collected_new_posts = []
            max_retries_per_page = 3
            consecutive_failures = 0
            max_consecutive_failures = 5
            
            # 增量更新：只获取差额部分
            while len(collected_new_posts) < posts_to_fetch:
                list_api_url = f"{base_api_url}/posts?o={offset}"
                
                # 带重试的页面获取
                page_post_summaries = None
                for attempt in range(max_retries_per_page):
                    response = make_robust_request(list_api_url, headers)
                    
                    if response:
                        page_post_summaries = parse_json_response(response)
                        if isinstance(page_post_summaries, list):
                            consecutive_failures = 0
                            break
                    
                    # 重试前等待
                    if attempt < max_retries_per_page - 1:
                        import time
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                
                # 检查是否获取成功
                if not page_post_summaries or not isinstance(page_post_summaries, list):
                    consecutive_failures += 1
                    
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    
                    offset += posts_per_page
                    continue
                
                # 成功获取数据
                if not page_post_summaries:
                    break
                
                collected_new_posts.extend(page_post_summaries)
                
                # 产出新帖子数据
                for post_summary in page_post_summaries:
                    if isinstance(post_summary, dict) and "id" in post_summary:
                        yield post_summary
                
                # 检查是否获取完整
                if len(page_post_summaries) < posts_per_page:
                    break
                
                offset += posts_per_page
            
            # 更新缓存（去重合并）
            if collected_new_posts:
                cache.update_posts_cache(service, creator_id, collected_new_posts, offset, delay_save=True)
            
            # 更新缓存的帖子数量
            final_cached_count = cached_post_count + len(collected_new_posts)
            cache.update_cached_post_count(service, creator_id, final_cached_count)
            
            # 保存缓存
            cache.flush_pending_cache()
        
        elif is_post:
            # 处理单个帖子 URL
            from ..core.api import get_creator_profile
            creator_name = get_creator_profile(service, creator_id, domain_config).get('name', creator_id)

            api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}/post/{post_id}"
            headers = COMMON_HEADERS.copy()
            headers["Referer"] = domain_config['referer']

            response = make_robust_request(api_url, headers)
            if not response:
                print(f"⚠️ 单个帖子API请求失败: {api_url}")
                return

            post_data = parse_json_response(response)
            if not isinstance(post_data, dict):
                print(f"⚠️ 单个帖子API返回数据格式错误")
                return
            
            # 检测文件并构建结果
            post_details, files = detect_files_from_post(
                post_data, domain_config['base_url'].replace('https://', ''), extensions, source_filters
            )
            
            if files:
                post_details['post_title'] = post_details.pop('title', None)
                post_info = {
                    "service": service.capitalize(), 
                    "creator_id": creator_id, 
                    "creator_name": creator_name,
                    "post_id": post_details.pop('id', None),
                    **post_details
                }
                yield {"post_info": post_info, "files": files}

    except Exception as e:
        print(f"检测文件时发生错误: {e}")

