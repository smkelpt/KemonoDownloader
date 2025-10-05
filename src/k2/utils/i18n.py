# i18n.py - 国际化支持模块
import os
import json
from typing import Dict, Any

# 语言文件目录（使用resources/languages目录）
LANGUAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "languages")

# 默认语言
DEFAULT_LANGUAGE = "zh_CN"
CURRENT_LANGUAGE = DEFAULT_LANGUAGE

# 语言数据缓存
_language_data: Dict[str, Any] = {}

# 支持的语言列表
SUPPORTED_LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English"
}

def get_language_file_path(language_code: str) -> str:
    """获取语言文件路径"""
    return os.path.join(LANGUAGES_DIR, f"{language_code}.json")

def load_language_data(language_code: str) -> Dict[str, Any]:
    """加载语言数据"""
    language_file = get_language_file_path(language_code)
    
    try:
        with open(language_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"警告: 无法加载语言文件 {language_file}: {e}")
        return {}

def set_language(language_code: str):
    """设置当前语言"""
    global CURRENT_LANGUAGE, _language_data
    
    if language_code not in SUPPORTED_LANGUAGES:
        print(f"警告: 不支持的语言代码 {language_code}，使用默认语言")
        language_code = DEFAULT_LANGUAGE
    
    CURRENT_LANGUAGE = language_code
    _language_data = load_language_data(language_code)

def get_text(key: str, **kwargs) -> str:
    """获取翻译文本"""
    if not _language_data:
        set_language(CURRENT_LANGUAGE)
    
    # 支持嵌套键，如 "ui.buttons.download"
    keys = key.split('.')
    value = _language_data
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # 如果找不到翻译，返回键名作为后备
            print(f"警告: 找不到翻译键 '{key}'")
            return key
    
    # 如果值是字符串，支持格式化
    if isinstance(value, str) and kwargs:
        try:
            return value.format(**kwargs)
        except KeyError as e:
            print(f"警告: 翻译文本格式化失败 '{key}': {e}")
            return value
    
    return str(value)

# 便捷函数，简化调用
def _(key: str, **kwargs) -> str:
    """翻译函数的简化版本"""
    return get_text(key, **kwargs)

# 初始化语言系统
def initialize_i18n(language_code: str = None):
    """初始化国际化系统"""
    if language_code is None:
        language_code = DEFAULT_LANGUAGE
    
    # 设置当前语言
    set_language(language_code)

# 自动初始化
initialize_i18n()
