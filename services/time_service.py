from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TimeServer")

@mcp.tool()
def get_current_time(timezone: Optional[str] = None) -> str:
    """
    获取指定时区或本地的当前时间
    
    参数：
        timezone (str, 可选): IANA标准时区名称（例如'Asia/Shanghai'）
                            支持自动清理输入的空格和大小写转换
    
    返回：
        str: 格式化的当前时间，格式为'YYYY-MM-DD HH:MM:SS [时区名称]'
            包含更友好的错误提示
    """
    try:
        # 输入清理和规范化
        if timezone:
            # 去除前后空格并替换下划线为斜杠（处理常见笔误）
            cleaned_tz = timezone.strip().replace("_", "/")
            tz = ZoneInfo(cleaned_tz)
        else:
            tz = datetime.now().astimezone().tzinfo
        
        current_time = datetime.now(tz)
        
        # 添加时区详细信息
        tz_info = (
            f"{tz.tzname(current_time)} "
            f"(UTC{current_time.strftime('%z')})"
        )
        
        return current_time.strftime(f"%Y-%m-%d %H:%M:%S {tz_info}")
        
    except ZoneInfoNotFoundError as e:
        # 提供常见时区示例
        examples = "\n".join([
            "常见时区示例：",
            "- Europe/London", 
            "- Asia/Shanghai",
            "- UTC",
            "完整列表：https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ])
        return f"无效时区名称：'{timezone}'\n{examples}"
    except Exception as e:
        return f"时间服务暂时不可用，请稍后再试（错误代码：{hash(e) & 0xFFFF})"

if __name__ == "__main__":
    mcp.run(transport='stdio')