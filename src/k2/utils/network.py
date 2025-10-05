"""
网络请求工具模块
处理HTTP会话、请求重试、响应解析等
"""
import requests
from requests.adapters import HTTPAdapter
try:
    from requests.packages.urllib3.util.retry import Retry
except ImportError:
    from urllib3.util.retry import Retry
import gzip
import json
import time
import threading
import locale
import ctypes
import re
from fake_useragent import UserAgent


# === HTTP Session管理 ===
_session = None
_session_lock = threading.Lock()
_last_pool_size = None


def get_session(max_workers=None):
    """获取配置好的Session实例，线程安全
    
    Args:
        max_workers: 可选，并发线程数，用于动态调整连接池大小
    """
    global _session, _last_pool_size
    
    # 计算需要的连接池大小
    if max_workers is not None:
        desired_pool_size = max(max_workers * 2, 20)
    else:
        desired_pool_size = 50
    
    # 如果连接池大小变化，需要重新创建session
    should_recreate = (_session is not None and 
                      _last_pool_size is not None and 
                      abs(desired_pool_size - _last_pool_size) > 10)
    
    if _session is None or should_recreate:
        with _session_lock:
            if _session is None or should_recreate:  # 双重检查
                if should_recreate:
                    _session.close()  # 关闭旧的session
                
                _session = requests.Session()
                _last_pool_size = desired_pool_size
                
                # 配置重试策略
                retry_strategy = Retry(
                    total=3,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS"],
                    backoff_factor=1
                )
                
                # 动态配置连接池
                adapter = HTTPAdapter(
                    pool_connections=desired_pool_size,
                    pool_maxsize=desired_pool_size,
                    max_retries=retry_strategy
                )
                
                _session.mount("http://", adapter)
                _session.mount("https://", adapter)
                
                # 设置默认超时
                _session.timeout = (10, 30)
    
    return _session


# === 域名配置 ===
DOMAINS = {
    'kemono': {
        'base_url': 'https://kemono.cr',
        'api_base': 'https://kemono.cr/api/v1',
        'referer': 'https://kemono.cr/'
    },
    'coomer': {
        'base_url': 'https://coomer.st',
        'api_base': 'https://coomer.st/api/v1',
        'referer': 'https://coomer.st/'
    }
}


def get_domain_config(url: str) -> dict:
    """根据 URL 确定并返回对应的域名配置"""
    if 'coomer.st' in url:
        return DOMAINS['coomer']
    return DOMAINS['kemono']


# === 请求头配置 ===
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    locale.setlocale(locale.LC_ALL, 'C')

if hasattr(ctypes, 'windll'):
    lcid = ctypes.windll.kernel32.GetUserDefaultLCID()
    system_language = locale.windows_locale.get(lcid, "en_US")
else:
    locale_info = locale.getlocale(locale.LC_ALL)
    system_language = locale_info[0] if locale_info and locale_info[0] else "en_US"

system_language = system_language.replace('_', '-')
ACCEPT_LANGUAGE = f"{system_language},en;q=0.9"

user_agent_generator = UserAgent()
USER_AGENT = user_agent_generator.chrome

COMMON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/css",
    "Accept-Language": ACCEPT_LANGUAGE,
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}


# === URL 解析 ===
POST_URL_RE = re.compile(
    r"https?://[^/]+/(?P<service>[^/]+)/user/(?P<creator_id>[^/]+)/post/(?P<post_id>\d+)"
)

CREATOR_URL_RE = re.compile(
    r"https?://[^/]+/(?P<service>[^/]+)/user/(?P<creator_id>[^/]+)"
)


def extract_post_info(url: str) -> tuple[str, str, str]:
    """从帖子 URL 中提取服务、创作者和帖子 ID"""
    match = POST_URL_RE.search(url)
    if not match:
        raise ValueError(f"无效的帖子 URL: {url}")
    return (
        match.group("service"),
        match.group("creator_id"),
        match.group("post_id")
    )


def extract_creator_info(url: str) -> tuple[str, str]:
    """从创作者 URL 中提取服务和创作者 ID"""
    match = CREATOR_URL_RE.search(url)
    if not match:
        raise ValueError(f"无效的创作者 URL: {url}")
    return (
        match.group("service"),
        match.group("creator_id")
    )


# === HTTP请求 ===
def make_robust_request(url: str, headers: dict, max_retries: int = 3, timeout: int = 30) -> requests.Response | None:
    """发送一个健壮的 HTTP GET 请求，支持重试和退避
    
    Returns:
        成功时返回 Response 对象，失败时返回 None（不抛出异常）
    """
    session = get_session()
    local_headers = headers.copy()
    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=local_headers, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                # 数据请求被拒绝，尝试备用请求头
                local_headers["Accept"] = "text/css"
                response = session.get(url, headers=local_headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                
        except requests.exceptions.RequestException as e:
            # 网络错误（包括超时），打印错误信息但不抛出异常
            if attempt == max_retries - 1:
                print(f"⚠️ 网络请求失败（已重试{max_retries}次）: {str(e)[:100]}")
                return None
            # 继续重试
        
        # 准备重试
        if attempt < max_retries - 1:  # 不是最后一次尝试
            sleep_time = 2 ** attempt
            time.sleep(sleep_time)
    
    return None


def parse_json_response(response: requests.Response) -> dict | None:
    """解析 HTTP 响应中的 JSON 内容，处理 gzip 压缩和编码"""
    decoded_content = None
    try:
        content = response.content

        # 尝试 gzip 解压缩
        if content.startswith(b'\x1f\x8b'):
            try:
                content = gzip.decompress(content)
            except Exception as e:
                print(f"警告: gzip 解压缩失败: {e}")
        
        # 尝试 UTF-8 解码
        if isinstance(content, bytes):
            decoded_content = content.decode("utf-8", errors="replace")
        else:
            decoded_content = content

        # 尝试解析 JSON
        return json.loads(decoded_content)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"警告: 无法解析 JSON 响应内容或解码失败: {e}")
        return None
    except Exception as e:
        print(f"警告: 解析 JSON 响应时发生未知错误: {e}")
        return None

