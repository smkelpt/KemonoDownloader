# cache.py - 缓存管理模块
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from .paths import CREATORS_DIR, get_creator_cache_file, get_creator_dir


class CacheManager:
    """统一的缓存管理器 - 每个作者使用独立的缓存文件"""
    
    # 缓存配置
    MAX_POSTS_PER_CREATOR = None  # 不限制缓存数量（None = 无限制）
    
    def __init__(self):
        # 使用独立文件存储，不需要加载所有缓存到内存
        # 内存缓存：用于当前会话的快速访问
        self._memory_cache = {}  # {service:creator_id: cache_data}
        
        # 待写入的缓存更新（延迟批量写入）
        self._pending_saves = set()  # 记录需要保存的作者
    
    def _get_cache_key(self, service: str, creator_id: str) -> str:
        """生成缓存键"""
        return f"{service}:{creator_id}"
    
    def _load_creator_cache(self, service: str, creator_id: str) -> dict:
        """加载指定作者的缓存文件"""
        cache_key = self._get_cache_key(service, creator_id)
        
        # 先检查内存缓存
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        # 从文件加载
        cache_file = get_creator_cache_file(service, creator_id)
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self._memory_cache[cache_key] = cache_data
                    return cache_data
            except (json.JSONDecodeError, IOError) as e:
                print(f"警告: 加载缓存文件失败 {cache_file}: {e}")
                return self._create_empty_cache(service, creator_id)
        
        return self._create_empty_cache(service, creator_id)
    
    def _create_empty_cache(self, service: str, creator_id: str) -> dict:
        """创建空的缓存数据结构"""
        return {
            'service': service,
            'creator_id': creator_id,
            'posts': [],
            'profile': None,
            'tags': None,
            'cached_post_count': 0,
            'cached_at': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
    
    def _save_creator_cache(self, service: str, creator_id: str, immediate: bool = False):
        """保存指定作者的缓存文件"""
        cache_key = self._get_cache_key(service, creator_id)
        
        if immediate:
            # 立即保存
            if cache_key in self._memory_cache:
                cache_file = get_creator_cache_file(service, creator_id)
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(self._memory_cache[cache_key], f, ensure_ascii=False, indent=2)
                except (IOError, Exception) as e:
                    print(f"❌ 保存缓存失败 {service}:{creator_id}: {e}")
        else:
            # 延迟保存
            self._pending_saves.add(cache_key)
    
    def _is_cache_valid(self, cache_time_str: str) -> bool:
        """检查缓存是否有效（永久有效，仅检查格式）"""
        try:
            # 只验证时间戳格式是否正确，不检查过期
            datetime.fromisoformat(cache_time_str)
            return True
        except (ValueError, TypeError):
            return False
    
    # ========== 帖子缓存 ==========
    
    def get_cached_posts(self, service: str, creator_id: str, offset: int = 0) -> Optional[List[dict]]:
        """获取缓存的帖子数据
        
        Returns:
            如果缓存存在且包含请求的offset，返回帖子列表；否则返回None
        """
        cache_data = self._load_creator_cache(service, creator_id)
        
        # 检查缓存格式是否有效
        if not self._is_cache_valid(cache_data.get('cached_at', '')):
            return None
        
        # 检查是否有请求的offset的数据
        posts = cache_data.get('posts', [])
        if offset < len(posts):
            return posts[offset:]
        
        return None
    
    def update_posts_cache(self, service: str, creator_id: str, new_posts: List[dict], offset: int = 0, delay_save: bool = True):
        """更新帖子缓存（增量更新，支持延迟保存）
        
        Args:
            service: 服务名
            creator_id: 创作者ID
            new_posts: 新获取的帖子列表
            offset: 当前offset
            delay_save: 是否延迟保存（默认True，检测完成后统一保存）
        """
        cache_data = self._load_creator_cache(service, creator_id)
        existing_posts = cache_data.get('posts', [])
        
        # 使用post_id去重合并
        existing_ids = {p.get('id') for p in existing_posts if p.get('id')}
        
        # 添加新帖子（不重复）
        added_count = 0
        for post in new_posts:
            post_id = post.get('id')
            if post_id and post_id not in existing_ids:
                existing_posts.append(post)
                existing_ids.add(post_id)
                added_count += 1
        
        if added_count > 0 or not cache_data.get('posts'):
            # 按published时间排序（最新的在前）
            existing_posts.sort(
                key=lambda p: p.get('published', ''), 
                reverse=True
            )
            
            # 如果设置了数量限制，则只保留最新的
            if self.MAX_POSTS_PER_CREATOR:
                existing_posts = existing_posts[:self.MAX_POSTS_PER_CREATOR]
            
            cache_data['posts'] = existing_posts
            cache_data['last_updated'] = datetime.now().isoformat()
            cache_data['cached_post_count'] = len(existing_posts)
            
            # 更新内存缓存
            cache_key = self._get_cache_key(service, creator_id)
            self._memory_cache[cache_key] = cache_data
            
            # 保存到文件
            self._save_creator_cache(service, creator_id, immediate=not delay_save)
    
    def update_cached_post_count(self, service: str, creator_id: str, post_count: int):
        """更新缓存的帖子数量
        
        Args:
            service: 服务名
            creator_id: 创作者ID
            post_count: 最新的帖子总数
        """
        cache_data = self._load_creator_cache(service, creator_id)
        cache_data['cached_post_count'] = post_count
        cache_data['last_updated'] = datetime.now().isoformat()
        
        cache_key = self._get_cache_key(service, creator_id)
        self._memory_cache[cache_key] = cache_data
        self._save_creator_cache(service, creator_id, immediate=False)
    
    def get_cached_post_count(self, service: str, creator_id: str) -> int:
        """获取已缓存的帖子数量
        
        Returns:
            缓存的帖子数量，如果无缓存返回0
        """
        cache_data = self._load_creator_cache(service, creator_id)
        return cache_data.get('cached_post_count', 0)
    
    def flush_pending_cache(self):
        """立即保存所有待写入的缓存更新"""
        for cache_key in list(self._pending_saves):
            if cache_key in self._memory_cache:
                service, creator_id = cache_key.split(':', 1)
                self._save_creator_cache(service, creator_id, immediate=True)
        self._pending_saves.clear()
    
    def get_posts_count(self, service: str, creator_id: str) -> int:
        """获取缓存的帖子数量"""
        cache_data = self._load_creator_cache(service, creator_id)
        return len(cache_data.get('posts', []))
    
    # ========== 个人资料缓存 ==========
    
    def get_cached_profile(self, service: str, creator_id: str) -> Optional[dict]:
        """获取缓存的个人资料"""
        cache_data = self._load_creator_cache(service, creator_id)
        
        # 检查缓存格式是否有效
        if not self._is_cache_valid(cache_data.get('cached_at', '')):
            return None
        
        return cache_data.get('profile')
    
    def update_profile_cache(self, service: str, creator_id: str, profile_data: dict):
        """更新个人资料缓存"""
        cache_data = self._load_creator_cache(service, creator_id)
        cache_data['profile'] = profile_data
        cache_data['last_updated'] = datetime.now().isoformat()
        
        cache_key = self._get_cache_key(service, creator_id)
        self._memory_cache[cache_key] = cache_data
        self._save_creator_cache(service, creator_id, immediate=True)
    
    # ========== 标签缓存 ==========
    
    def get_cached_tags(self, service: str, creator_id: str) -> Optional[Dict[str, int]]:
        """获取缓存的标签数据"""
        cache_data = self._load_creator_cache(service, creator_id)
        
        # 检查缓存格式是否有效
        if not self._is_cache_valid(cache_data.get('cached_at', '')):
            return None
        
        return cache_data.get('tags')
    
    def update_tags_cache(self, service: str, creator_id: str, tags_data: Dict[str, int]):
        """更新标签缓存"""
        cache_data = self._load_creator_cache(service, creator_id)
        cache_data['tags'] = tags_data
        cache_data['last_updated'] = datetime.now().isoformat()
        
        cache_key = self._get_cache_key(service, creator_id)
        self._memory_cache[cache_key] = cache_data
        self._save_creator_cache(service, creator_id, immediate=True)
    
    # ========== 帖子标签映射缓存 ==========
    
    def get_post_tags(self, service: str, creator_id: str, post_id: str) -> Optional[List[str]]:
        """获取指定帖子的标签列表"""
        cache_data = self._load_creator_cache(service, creator_id)
        posts = cache_data.get('posts', [])
        
        for post in posts:
            if post.get('id') == post_id:
                return post.get('tags', [])
        
        return None
    
    # ========== 缓存统计 ==========
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total_posts = 0
        total_creators = 0
        
        # 遍历所有作者目录
        if os.path.exists(CREATORS_DIR):
            creator_dirs = [d for d in os.listdir(CREATORS_DIR) if os.path.isdir(os.path.join(CREATORS_DIR, d))]
            
            for creator_dir_name in creator_dirs:
                cache_file = os.path.join(CREATORS_DIR, creator_dir_name, "cache.json")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            total_posts += len(cache_data.get('posts', []))
                            total_creators += 1
                    except:
                        continue
        
        return {
            'total_creators': total_creators,
            'total_posts': total_posts
        }
    
    def clear_invalid_cache(self):
        """清理格式无效的缓存"""
        invalid_count = 0
        
        if os.path.exists(CREATORS_DIR):
            creator_dirs = [d for d in os.listdir(CREATORS_DIR) if os.path.isdir(os.path.join(CREATORS_DIR, d))]
            
            for creator_dir_name in creator_dirs:
                cache_file = os.path.join(CREATORS_DIR, creator_dir_name, "cache.json")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        # 检查缓存格式是否有效
                        if not self._is_cache_valid(cache_data.get('cached_at', '')):
                            os.remove(cache_file)
                            # 如果目录为空，删除目录
                            creator_dir = os.path.join(CREATORS_DIR, creator_dir_name)
                            if not os.listdir(creator_dir):
                                os.rmdir(creator_dir)
                            invalid_count += 1
                    except:
                        # 文件损坏，删除
                        try:
                            os.remove(cache_file)
                            creator_dir = os.path.join(CREATORS_DIR, creator_dir_name)
                            if not os.listdir(creator_dir):
                                os.rmdir(creator_dir)
                            invalid_count += 1
                        except:
                            pass
        
        # 清理内存缓存
        self._memory_cache.clear()
        self._pending_saves.clear()
        
        return {'invalid_files': invalid_count}
    
    def clear_all_cache(self):
        """清空所有缓存"""
        deleted_count = 0
        
        if os.path.exists(CREATORS_DIR):
            creator_dirs = [d for d in os.listdir(CREATORS_DIR) if os.path.isdir(os.path.join(CREATORS_DIR, d))]
            
            for creator_dir_name in creator_dirs:
                creator_dir = os.path.join(CREATORS_DIR, creator_dir_name)
                try:
                    # 删除目录中的所有文件
                    for file in os.listdir(creator_dir):
                        file_path = os.path.join(creator_dir, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    # 删除空目录
                    os.rmdir(creator_dir)
                    deleted_count += 1
                except:
                    pass
        
        # 清理内存缓存
        self._memory_cache.clear()
        self._pending_saves.clear()
        
        return {'status': 'success', 'message': f'已清空 {deleted_count} 个作者的缓存'}
    
    def diagnose_cache_integrity(self, service: str, creator_id: str, expected_total: int = None) -> dict:
        """诊断缓存完整性，检测潜在问题
        
        Args:
            service: 服务类型
            creator_id: 创作者ID
            expected_total: 期望的帖子总数（从profile获取）
            
        Returns:
            诊断结果字典
        """
        cache_data = self._load_creator_cache(service, creator_id)
        
        if not cache_data.get('posts'):
            return {'status': 'no_cache', 'message': '无缓存数据'}
        
        posts = cache_data.get('posts', [])
        cached_count = len(posts)
        
        # 提取所有帖子ID（转换为字符串以便比较）
        post_ids = [str(p.get('id')) for p in posts if p.get('id')]
        unique_ids = set(post_ids)
        
        issues = []
        
        # 检查1: ID重复
        if len(post_ids) != len(unique_ids):
            duplicates = len(post_ids) - len(unique_ids)
            issues.append(f"发现 {duplicates} 个重复的帖子ID")
        
        # 检查2: 数量不匹配
        if expected_total is not None and cached_count != expected_total:
            diff = expected_total - cached_count
            if diff > 0:
                issues.append(f"缓存不完整：缺少 {diff} 个帖子 ({cached_count}/{expected_total})")
            else:
                issues.append(f"缓存异常：帖子数量超出预期 ({cached_count}/{expected_total})")
        
        # 检查3: 时间戳连续性（检测是否有明显的时间跳跃）
        timestamps = [p.get('published', '') for p in posts if p.get('published')]
        if len(timestamps) > 10:  # 至少10个帖子才有意义
            # 简单检查：如果时间戳不是单调递减，可能存在问题
            is_sorted = all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))
            if not is_sorted:
                issues.append("帖子时间戳顺序异常（可能存在缺失或错位）")
        
        result = {
            'key': self._get_cache_key(service, creator_id),
            'cached_count': cached_count,
            'expected_count': expected_total,
            'unique_ids': len(unique_ids),
            'issues': issues,
            'status': 'healthy' if not issues else 'problematic'
        }
        
        return result


# 全局缓存管理器实例
_cache_manager = None

def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例（单例）"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager

