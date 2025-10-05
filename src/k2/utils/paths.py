import os
import sys

def get_k2_module_directory():
    """
    获取k2模块目录的绝对路径
    
    开发环境：K2/src/k2/
    打包环境：build/k2/windows/app/src/app/k2/
    """
    # 无论什么环境，都从当前文件计算 k2 模块目录
    # 当前文件位置：.../src/k2/utils/paths.py
    # 向上1级到 k2 模块目录 (utils -> k2)
    current_file = os.path.abspath(__file__)
    utils_dir = os.path.dirname(current_file)   # .../src/k2/utils
    k2_dir = os.path.dirname(utils_dir)          # .../src/k2
    return k2_dir

def get_program_root():
    """
    获取程序根目录（数据存储位置）
    
    情况1: Nuitka打包 - exe所在目录
    情况2: 直接运行 - K2/ (项目根目录)
    """
    if getattr(sys, 'frozen', False):
        # Nuitka/PyInstaller打包后运行：可执行文件所在目录
        # sys.executable = .../dist/__main__.dist/__main__.exe
        exe_path = sys.executable
        # 返回可执行文件所在目录
        return os.path.dirname(exe_path)
    else:
        # 开发环境：直接运行
        k2_dir = get_k2_module_directory()
        # k2_dir: .../K2/src/k2 -> .../K2/
        src_dir = os.path.dirname(k2_dir)  # .../K2/src
        project_root = os.path.dirname(src_dir)  # .../K2
        return project_root

# 获取k2模块目录的绝对路径
K2_MODULE_DIR = get_k2_module_directory()

# 获取程序根目录
PROGRAM_ROOT = get_program_root()

# K2 数据目录：存储所有配置、缓存、日志（在程序根目录下）
# 开发环境：K2/data/
# 打包环境：build/k2/windows/app/data/
DATA_DIR = os.path.join(PROGRAM_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 应用配置文件
APP_DATA_FILE = os.path.join(DATA_DIR, "config.json")

# 作者数据根目录
CREATORS_DIR = os.path.join(DATA_DIR, "creators")
os.makedirs(CREATORS_DIR, exist_ok=True)

# 日志目录
LOGS_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# 崩溃日志文件
CRASH_LOG_FILE = os.path.join(LOGS_DIR, "crash.log")

def get_creator_dir(service: str, creator_id: str) -> str:
    """获取作者的专属目录
    
    Args:
        service: 服务类型（如 patreon）
        creator_id: 创作者ID
        
    Returns:
        作者目录的完整路径
    """
    creator_dirname = f"{service}_{creator_id}"
    creator_dir = os.path.join(CREATORS_DIR, creator_dirname)
    os.makedirs(creator_dir, exist_ok=True)
    return creator_dir

def get_creator_cache_file(service: str, creator_id: str) -> str:
    """获取作者的缓存文件路径
    
    Args:
        service: 服务类型（如 patreon）
        creator_id: 创作者ID
        
    Returns:
        缓存文件的完整路径
    """
    creator_dir = get_creator_dir(service, creator_id)
    return os.path.join(creator_dir, "cache.json") 