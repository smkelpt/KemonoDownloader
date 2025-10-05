"""
格式化工具函数
"""
import re


def format_name_from_template(template: str, data: dict) -> str:
    """根据模板和数据字典格式化名称"""
    name = template
    for key, value in data.items():
        name = name.replace(f"{{{key}}}", str(value) if value is not None else "")
    # 清理文件名
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.rstrip('. ')
    name = name.strip()
    if len(name) > 150:
        name = name[:150].rstrip('. ')
    return name if name else "untitled"

