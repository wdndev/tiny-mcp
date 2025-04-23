import asyncio
import os
import sys
import json
from contextlib import AsyncExitStack
from typing import Optional, List, Dict, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(
        self,
        model_type: str,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model_name: str = "deepseek-chat",
    ):
        """
        初始化MCP客户端
        :param model_type: 服务商类型 ("openai"/"deepseek")
        :param api_key: API密钥
        :param base_url: API端点
        :param model_name: 模型名称
        """
        self.model_type = model_type
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url

        # 初始化会话参数
        self.session: Optional[ClientSession] = None
        self.stdio_transport = None
        self.exit_stack = AsyncExitStack()
        self.available_tools: List[Dict[str, Any]] = []
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()

        # 初始化客户端
        self.llm_client = AsyncOpenAI(
            api_key=api_key,
            base_url=None if model_type == "openai" else base_url,
        )
        
    @staticmethod
    def parse_arguments(args: List[str]) -> StdioServerParameters:
        """
        静态方法：解析命令行参数并返回服务器参数
        :param args: 命令行参数列表（不包含脚本名称）
        :return: StdioServerParameters 对象
        """
        if len(args) == 1:
            # 方式1：直接指定服务器脚本
            server_script_path = args[0]
            if not server_script_path.endswith(('.py', '.js')):
                raise ValueError("[ERR] 服务器脚本必须是 .py 或 .js 文件")
            
            command = "python" if server_script_path.endswith('.py') else "node"
            return StdioServerParameters(
                command=command,
                args=[server_script_path],
                env=None
            )
        elif len(args) == 2:
            # 方式2：通过配置文件指定
            server_identifier, config_path = args[0], args[1]
            
            # 读取配置文件
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                raise ValueError(f"配置文件读取失败: {str(e)}")
            
            # 解析服务器配置
            mcp_servers = config.get('mcpServers', {})
            server_config = mcp_servers.get(server_identifier)
            if not server_config:
                raise ValueError(f"未找到服务器标识符: {server_identifier}")
            
            if not all(key in server_config for key in ['command', 'args']):
                raise ValueError("服务器配置缺少必要字段（command/args）")
            
            return StdioServerParameters(
                command=server_config['command'],
                args=server_config['args'],
                env=None
            )
        else:
            raise ValueError("参数数量错误")

    async def connect_to_server(self, server_params: StdioServerParameters):
        """
        连接到MCP服务器
        :param server_script_path: 服务器脚本路径（.py或.js）
        """
        # 建立传输层连接
        self.stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        stdio_reader, stdio_writer = self.stdio_transport

        # 初始化客户端会话
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_reader, stdio_writer)
        )
        await self.session.initialize()

        # 获取可用工具列表
        response = await self.session.list_tools()
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in response.tools
        ]
        print(f"[SYS]: 成功连接服务器，可用工具: {[t['function']['name'] for t in self.available_tools]}")

    async def process_query(self, query: str) -> str:
        """处理查询
        """
        messages = [{"role": "user", "content": query}]
        responses = []

        while True:
            try:
                print("[LOG] Call LLM Messages:", messages)
                print("[LOG] Call LLM Tools:", self.available_tools)

                response = await self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=self.available_tools,
                    tool_choice="auto",
                )

                message = response.choices[0].message
                print(f"[LLM]: {message} \n")
                messages.append(message)

                if not message.tool_calls:
                    return message.content or ""

                # 处理工具调用
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    
                    # 增强参数解析
                    if isinstance(tool_call.function.arguments, dict):
                        tool_args = tool_call.function.arguments
                    else:
                        
                        try:
                            tool_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            tool_args = {"input": tool_call.function.arguments}

                    # 执行工具调用
                    result = await self.session.call_tool(tool_name, tool_args)
                    print(f"[LOG]: 调用工具 [{tool_name}] 参数: {tool_args}")
                    print(f"[LOG]: 工具响应: {result.content}\n")
                    responses.append(f"[调用工具] {tool_name} 参数: {tool_args}")

                    # 通用工具响应格式
                    tool_response = {
                        "role": "tool",
                        "content": str(result.content),
                        "tool_call_id": tool_call.id,
                        "name": tool_name 
                    }
                    messages.append(tool_response)

            except Exception as e:
                responses.append(f"[ERR]: 处理错误: {str(e)}")
                break

        return "\n".join(responses)

    async def chat_loop(self):
        """改进的输入处理方法"""
        print("[SYS]: MCP客户端已启动！")
        print("[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）")

        loop = asyncio.get_event_loop()
        
        while True:
            try:
                # 使用run_in_executor处理同步输入
                query = await loop.run_in_executor(
                    None,  # 使用默认执行器
                    lambda: input("[USR]: ").strip()
                )

                print()     # 添加空行
                
                if not query:
                    continue
                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print(f"[LLM]: {response} \n")

            except (KeyboardInterrupt, EOFError):
                print("\n[SYS]: 检测到退出信号，正在关闭...")
                break
            except Exception as e:
                print(f"\n[SYS]: 错误发生：{str(e)}")

    async def cleanup(self):
        """ 清理资源
        """
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                print(f"Error during cleanup of server: {e}")

async def main():

    try:
        # 通过类方法解析参数
        server_params = MCPClient.parse_arguments(sys.argv[1:])
    except ValueError as e:
        print(f"[ERR]: 参数错误: {str(e)}")
        print("使用方法:")
        print("方式 1: python mcp_client.py <服务器脚本路径>")
        print("方式 2: python mcp_client.py <服务器标识符> <配置文件路径>")
        sys.exit(1)

    print("[SYS]: LLM_MODEL_TYPE: ", os.getenv("LLM_MODEL_TYPE", ""))
    print("[SYS]:    LLM_API_URL: ", os.getenv("LLM_API_URL", ""))
    print("[SYS]: LLM_MODEL_NAME: ", os.getenv("LLM_MODEL_NAME", ""))
    client = MCPClient(
        model_type=os.getenv("LLM_MODEL_TYPE", ""),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_API_URL", ""),
        model_name=os.getenv("LLM_MODEL_NAME", ""),
    )

    try:
        await client.connect_to_server(server_params)
        await client.chat_loop()
    except ValueError as e:
        print(f"[ERR] 参数错误: {str(e)}")
    except Exception as e:
        print(f"\n[ERR] 运行时错误: {str(e)}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import platform
    if platform.system().lower() == 'windows':
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())