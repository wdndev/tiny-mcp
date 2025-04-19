import asyncio
import json
from loguru import logger

from mcp_client.chatbot_config import Configuration
from mcp_client.chat_session import ChatSession
from mcp_client.llm_service import LLMService
from mcp_client.mcp_server import MCPServer


async def main() -> None:
    """主入口函数
    """
    config = Configuration()
    server_config = config.load_config("config/server_config.json")  # 加载服务器配置

    servers = [
        MCPServer(name, config)
        for name, config in server_config["mcpServers"].items()  # 创建服务器实例
    ]

    llm_service = LLMService(
        api_key=config.llm_api_key,
        model_name=config.model_name,
        base_url=config.base_url,
        model_type=config.model_type,
    )

    chat_session = ChatSession(servers, llm_service)
    await chat_session.start()


if __name__ == "__main__":
    asyncio.run(main()) 
