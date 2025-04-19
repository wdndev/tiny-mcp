import os
import ujson
import requests
from typing import Tuple, Optional

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from dotenv import load_dotenv

from mcp.server.fastmcp import Context, FastMCP

load_dotenv()

class CityWeather:
    """
    城市信息高效查询类
    功能特点：
    - 初始化时自动加载并索引JSON数据
    - 支持中文和拼音双模式查询
    - 毫秒级响应速度（基于哈希索引）
    - 内存优化设计
    """
    
    __slots__ = ['_index', 'weather_url', 'weather_key']  # 内存优化

    def __init__(
            self,
            weather_url: str,
            weather_key: str,
            city_json_path: str
        ):
        """
        初始化加载城市数据
        :param json_path: JSON文件路径
        """
        self.weather_url = weather_url
        self.weather_key = weather_key
        self._index = {}
        if not self.weather_key:
            raise ValueError("必须配置WEATHER_API_KEY环境变量")
        self._load_and_index(city_json_path)

    def _load_and_index(self, path: str):
        """
        高性能数据加载和索引构建
        时间复杂度: O(n)
        """
        with open(path, 'rb') as f:  # 二进制模式读取更快
            data = ujson.load(f)
            
        # 并行构建索引
        for city in data:
            name_key = city["cityName"].strip().lower()
            pinyin_key = city["cityPinyin"].strip().lower()
            value = (city["province"], city["cityCode"])
            
            # 同时建立中文和拼音索引
            self._index[name_key] = value
            self._index[pinyin_key] = value

    def get_city_info(self, city_input: str) -> Tuple[Optional[str], Optional[str]]:
        """
        获取城市信息（线程安全）
        :param city_input: 支持中文或拼音（不区分大小写）
        :return: (省份, 城市代码) 元组
        时间复杂度: O(1)
        """
        key = city_input.strip().lower()
        return self._index.get(key, (None, None))

    @property
    def total_cities(self) -> int:
        """获取索引城市总数（去重计数）"""
        return len(self._index) // 2
    
    def get_weather(self, location: str) -> str:
        try:
            province, city_id = self.get_city_info(location)
            url = f"{self.weather_url}/v7/weather/now"
            params = {
                "location": city_id  # 北京城市代码
            }
            headers = {
                "X-QW-Api-Key": self.weather_key
            }

        
            # 发送带压缩支持的GET请求
            response = requests.get(url, headers=headers, params=params)     
            response.raise_for_status()  # 自动处理4xx/5xx错误   
            # 解析压缩后的JSON响应（requests自动处理gzip解码）
            data = response.json()

            print(data)
            
            # 示例数据解析（根据实际响应结构调整）
            if data["code"] == "200":
                return f"""中国{province}省{location}市天气查询成功：
                天气情况：{data['now']['text']}
                温度：{data['now']['temp']}°C
                体感温度：{data['now']['feelsLike']}°C
                风向：{data['now']['windDir']}
                风力等级: {data['now']['windScale']}级
                风速：{data['now']['windSpeed']}公里/小时
                相对湿度：{data['now']['humidity']}%
                气压: {data['now']['pressure']}百帕
                过去一小时降水量:{data['now']['precip']}毫米
                能见度: {data['now']['vis']} 公里
                """.replace("                ", "")
            else:
                return f"API错误: {data['code']} - {data['message']}"

        except requests.exceptions.HTTPError as e:
            return f"HTTP错误: {e.response.status_code}"
        except requests.exceptions.JSONDecodeError:
            return "响应解析失败"
        except Exception as e:
            return  f"请求异常: {str(e)}"


@dataclass
class MCPContext:
    weather_cxt: CityWeather

@asynccontextmanager
async def mcp_lifespan(server: FastMCP) -> AsyncIterator[MCPContext]:
    """ MCP 生命周期管理器
    """
    try:
        weather_cxt = CityWeather(
            weather_url=os.getenv("WEATHER_API_URL", ""),
            weather_key=os.getenv("WEATHER_API_KEY", ""),
            city_json_path=os.getenv("CITY_JSON_PATH", "")
        )

        # 进入服务
        yield MCPContext(
            weather_cxt=weather_cxt
        )
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        raise
    finally:
        print("清理资源")

# mcp dev E:/04Code/llm/tiny-mcp/services/weather_service_zh.py
mcp = FastMCP(
    name="天气查询",
    instructions="""
    这是一个天气查询工具，你可以查询任意城市的天气情况。
    """,
    lifespan=mcp_lifespan
)

@mcp.tool(name="get_weather", description="查询天气情况")
async def get_weather(location: str, ctx: Context) -> str:
    """查询天气情况
    :param location: 城市名称（支持中文或拼音）
    :return: 天气情况（JSON格式）
    """
    weather_cxt = ctx.request_context.lifespan_context.weather_cxt
    return weather_cxt.get_weather(location)

if __name__ == "__main__":
    mcp.run(transport='stdio')

# # 使用示例
# if __name__ == "__main__":
#     # 初始化（假设文件大小为2MB，约2000城市）
#     city_weather = CityWeather(
#             weather_url=os.getenv("WEATHER_API_URL", ""),
#             weather_key=os.getenv("WEATHER_API_KEY", ""),
#             city_json_path=os.getenv("CITY_JSON_PATH", "")
#         )
    
#     # 测试查询
#     test_cases = ["北京", "beijing", "Chaoyang", "未知城市"]
#     for case in test_cases:
#         weather_str = city_weather.get_weather(case)
#         print(f"查询结果: {weather_str}")
#         print("--------------------------")