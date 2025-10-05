"""
K2 应用程序入口点
"""
import sys
import os

# 检测是否为编译后的程序
def is_compiled():
    """检测是否为编译后的程序"""
    current_file = os.path.abspath(__file__)
    # 检查是否在开发环境的 src 目录下
    # 开发环境路径特征：C:\...\K2\src\k2\__main__.py
    # 编译/安装路径：C:\...\dist\...\__main__.py 或 D:\K2\__main__.py 等
    
    # 如果路径包含 src\k2\__main__.py，说明是开发环境
    if os.path.normpath('src' + os.sep + 'k2' + os.sep + '__main__.py') in os.path.normpath(current_file):
        return False
    
    # 其他情况都视为编译/安装后运行
    return True

# 仅允许编译后运行
if not is_compiled():
    sys.exit(1)

# 设置模块路径
base_path = os.path.dirname(os.path.abspath(__file__))
if base_path not in sys.path:
    sys.path.insert(0, base_path)

from k2.ui.main_window import main

# 启动应用
main()

