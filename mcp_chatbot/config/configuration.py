import json
import os
from dotenv import load_dotenv
from typing import Any, Optional

class Configuration:
    """配置管理类，用于处理环境变量和配置文件"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> None:
        """初始化配置，优先使用传入参数，其次从环境变量读取
        
        参数:
            api_key: LLM API密钥，默认为None
            base_url: API基础URL，默认为None
            model_name: 模型名称，默认为None
            model_type: 模型类型，默认为None
        """
        # 优先使用传入参数，若未传入则从环境变量读取
        self.api_key = api_key if api_key is not None else os.getenv("LLM_API_KEY")
        self.base_url = base_url if base_url is not None else os.getenv("LLM_API_URL")
        self.model_name = model_name if model_name is not None else os.getenv("LLM_MODEL_NAME")
        self.model_type = model_type if model_type is not None else os.getenv("LLM_MODEL_TYPE")

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
    
    def print_config(self):
        print("[CFG]: LLM_MODEL_TYPE: ", self.model_type)
        print("[CFG]:    LLM_API_URL: ", self.base_url)
        print("[CFG]: LLM_MODEL_NAME: ", self.model_name)