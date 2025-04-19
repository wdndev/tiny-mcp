import json
import os
from dotenv import load_dotenv
from typing import Any

class Configuration:
    """配置管理类，用于处理环境变量和配置文件"""
    
    def __init__(self) -> None:
        """初始化时自动加载.env文件
        """
        self.load_env()
        self.api_key = os.getenv("LLM_API_KEY")  # 从环境变量获取API密钥
        self.base_url = os.getenv("LLM_API_URL") 
        self.model_name = os.getenv("LLM_MODEL_NAME") 
        self.model_type = os.getenv("LLM_MODEL_TYPE") 

    @staticmethod
    def load_env() -> None:
        """加载.env文件到环境变量
        """
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> dict[str, Any]:
        """
        加载JSON格式的服务器配置文件
        
        参数:
            file_path: JSON配置文件路径
            
        返回:
            配置字典
            
        异常:
            FileNotFoundError: 文件不存在
            JSONDecodeError: JSON格式错误
        """
        with open(file_path, "r") as f:
            return json.load(f)

    @property
    def llm_api_key(self) -> str:
        """获取LLM API密钥（属性方式访问）
        """
        if not self.api_key:
            raise ValueError("环境变量中未找到LLM_API_KEY")
        return self.api_key