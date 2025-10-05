"""
API请求模块
处理与Kemono/Coomer API的交互
"""
import requests
from typing import Optional, Dict, List
from ..utils.network import make_robust_request, parse_json_response, get_domain_config


def get_creator_profile(service: str, creator_id: str, domain_config: dict, cache_manager=None) -> dict:
    """获取创作者详细信息
    
    Args:
        service: 服务类型 (如 'patreon')
        creator_id: 创作者ID
        domain_config: 域名配置
        cache_manager: 缓存管理器（可选）
        
    Returns:
        包含创作者信息的字典
    """
    # 尝试从缓存获取
    if cache_manager:
        cached_profile = cache_manager.get_cached_profile(service, creator_id)
        if cached_profile:
            return cached_profile
    
    # 从API获取
    profile_api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}/profile"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": domain_config['referer']
    }
    
    try:
        response = make_robust_request(profile_api_url, headers, max_retries=2, timeout=10)
        if not response:
            print(f"⚠️ 无法获取创作者信息: {service}:{creator_id}")
            return {}
        
        profile_data = parse_json_response(response)
        if not isinstance(profile_data, dict):
            return {}
        
        # 构造创作者URL
        creator_url = f"{domain_config['base_url']}/{service}/user/{creator_id}"
        
        # 提取需要的字段
        creator_info = {
            'id': profile_data.get('id', creator_id),
            'name': profile_data.get('name', creator_id),
            'service': profile_data.get('service', service),
            'post_count': profile_data.get('post_count', 0),
            'updated': profile_data.get('updated', ''),
            'url': creator_url
        }
        
        # 更新缓存
        if cache_manager:
            cache_manager.update_profile_cache(service, creator_id, creator_info)
        
        return creator_info
        
    except Exception as e:
        print(f"⚠️ 获取创作者信息失败: {e}")
        return {}


def get_creator_tags(service: str, creator_id: str, domain_config: dict, cache_manager=None) -> Dict[str, int]:
    """获取创作者的所有标签及其对应的帖子数量
    
    Args:
        service: 服务类型
        creator_id: 创作者ID
        domain_config: 域名配置
        cache_manager: 缓存管理器（可选）
        
    Returns:
        标签名称到帖子数量的字典
    """
    # 尝试从缓存获取
    if cache_manager:
        cached_tags = cache_manager.get_cached_tags(service, creator_id)
        if cached_tags:
            return cached_tags
    
    # 从API获取
    tags_api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}/tags"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": domain_config['referer']
    }
    
    try:
        response = make_robust_request(tags_api_url, headers)
        if not response:
            return {}
        
        tags_data = parse_json_response(response)
        if not isinstance(tags_data, list):
            return {}
        
        # 提取标签名称和帖子数量
        tags_with_counts = {}
        for tag_item in tags_data:
            if isinstance(tag_item, dict) and "tag" in tag_item and "post_count" in tag_item:
                tag_name = tag_item["tag"]
                post_count = tag_item["post_count"]
                if isinstance(post_count, int) and post_count > 0:
                    tags_with_counts[tag_name] = post_count
        
        # 更新缓存
        if cache_manager:
            cache_manager.update_tags_cache(service, creator_id, tags_with_counts)
        
        return tags_with_counts
        
    except Exception as e:
        print(f"获取创作者标签失败: {e}")
        return {}


def get_post_detail(service: str, creator_id: str, post_id: str, domain_config: dict) -> Optional[dict]:
    """获取单个帖子的详细信息
    
    Args:
        service: 服务类型
        creator_id: 创作者ID
        post_id: 帖子ID
        domain_config: 域名配置
        
    Returns:
        帖子详细信息字典，失败返回None
    """
    api_url = f"{domain_config['api_base']}/{service}/user/{creator_id}/post/{post_id}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": domain_config['referer']
    }
    
    response = make_robust_request(api_url, headers, max_retries=2, timeout=15)
    if not response:
        return None
    
    post_data = parse_json_response(response)
    if not isinstance(post_data, dict):
        return None
    
    return post_data

