
import asyncio
import json
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any


from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .mcp_tool import MCPTool

class MCPClient:
    """ MCP服务器管理类，处理连接和工具执行

    {
        "mcpServers": {
            "get_current_time": {
                "name": "时间",
                "type": "stdio",
                "description": "获取时间",
                "command": "uv",
                "args": [
                "--directory",
                "E:/04Code/llm/mcp_code/tiny-mcp-demo/services",
                "run",
                "time_service.py"
                ]
            },
            "defaultServer": "get_current_time",
            "system": "自定义系统提示词"
        }
    }
    """
    def __init__(self,
        name: str,
        config: dict[str, Any]
    ):
        self.name: str = name   # 服务器名称
        self.config: dict[str, Any] = config  # 服务器配置
        self.stdio_context: Any | None = None  # 标准输入输出上下文
        self.session: ClientSession | None = None  # 客户端会话
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()  # 异步清理锁
        self.exit_stack: AsyncExitStack = AsyncExitStack()  # 异步上下文管理器栈

    async def initialize(self) -> None:
        """ 初始化服务器
        """
        # 解析执行命令（支持npx或自定义命令）
        command = (
            shutil.which("npx") if self.config["command"] == "npx"
            else self.config["command"]
        )

        # print("command: ", command)
        # print("args: ", self.config["args"])
        if command is None:
            raise ValueError("[ERR]: 命令必须是有效字符串且不能为None")
        

        # 构建服务器参数
        server_params = StdioServerParameters(
            command=command,
            args=self.config["args"],  # 命令行参数
            env={**os.environ, **self.config["env"]} if self.config.get("env") else None  # 合并环境变量
        )

        try:
            # 建立标准输入输出连接
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport  # 获取读写通道
            
            # 创建客户端会话
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            print(f"[ERR]: 初始化服务器 {self.name} 失败: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[Any]:
        """获取服务器可用工具列表
        """
        if not self.session:
            raise RuntimeError(f"[ERR]: 服务器 {self.name} 未初始化")

        tools_response = await self.session.list_tools()
        return [
            MCPTool(tool.name, tool.description, tool.inputSchema)
            for item in tools_response
            if isinstance(item, tuple) and item[0] == "tools"
            for tool in item[1]  # 解析工具数据
        ]
    
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> str:
        """
        执行工具（带重试机制）
        
        参数:
            tool_name: 工具名称
            arguments: 参数字典
            retries: 重试次数
            delay: 重试间隔（秒）
        """
        if not self.session:
            raise RuntimeError(f"[ERR]: 服务器 {self.name} 未初始化")
        
        attempt = 0
        while attempt < retries:
            try:
                print(f"[LOG]: 调用工具 [{tool_name}] 参数: {arguments}")
                tool_result = await self.session.call_tool(tool_name, arguments)
                print(f"[LOG]: 调用结果: {tool_result.model_dump()}")
                print(f"[LOG]: 工具响应: {tool_result.content}\n")
                
                return tool_result
            except Exception as e:
                attempt += 1
                print(f"[ERR]: 工具执行失败: {e}. 第 {attempt} 次重试（最多 {retries} 次）")
                if attempt < retries:
                    await asyncio.sleep(delay)
                else:
                    print("[ERR]: 达到最大重试次数，操作终止")
                    raise

    async def cleanup(self) -> None:
        """ 清理服务器 
        """
        async with self._cleanup_lock:  # 使用锁防止并发清理
            try:
                await self.exit_stack.aclose()  # 关闭所有异步上下文
                self.session = None
                self.stdio_context = None
            except Exception as e:
                print(f"[LOG]: 清理服务器 {self.name} 时出错: {e}")

    async def __aenter__(self):
        """Enter the async context manager.
        """
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager.
        """
        await self.cleanup()
