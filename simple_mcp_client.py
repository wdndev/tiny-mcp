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
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()

        self.available_tools: List[Dict[str, Any]] = []
        # {resources_name: resources}
        self.resources_dict = {}
        # {promts_name, description}
        self.prompts_dict = {}

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

        print(f"[SYS]: 服务器链接成功 !!!\n")

        # 获取可用工具列表
        tools_response = await self.session.list_tools()
        self.available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema
                }
            }
            for tool in tools_response.tools
        ]
        print(f"[SYS]: 可用工具: {[t['function']['name'] for t in self.available_tools]}")

        # 获取资源列表
        resources_response = await self.session.list_resources()
        resources_names = [resource.name for resource in resources_response.resources]
        for resource_name in resources_names:
            resource = await self.session.read_resource(resource_name)
            self.resources_dict[resource_name] = resource.contents[0].text

        print(f"[SYS]: 可用资源: {resources_names}")

        prompts_response = await self.session.list_prompts()
        prompts_names = []
        for prompt in prompts_response.prompts:
            prompt_name = prompt.name
            prompts_names.append(prompt_name)
            self.prompts_dict[prompt_name] = prompt.description
        # print(f"[SYS]: 可用 Prompt: {prompts_names}")
        print(f"[SYS]: 可用 Prompt: {self.prompts_dict}")

    async def selcect_prompt_template(self, user_question: str) -> str:
        """ 根据用户问题选择 prompt 模板
        """
        # 需要详细回答的指示词
        detailed_indicators = [
            "解释", "说明", "详细", "具体", "详尽", "深入", "全面", "彻底", 
            "分析", "为什么", "怎么样", "如何", "原因", "机制", "过程",
            "explain", "detail", "elaborate", "comprehensive", "thorough",
            "in-depth", "analysis", "why", "how does", "reasons",
            "背景", "历史", "发展", "比较", "区别", "联系", "影响", "意义",
            "优缺点", "利弊", "方法", "步骤", "案例", "举例", "证明",
            "理论", "原理", "依据", "论证", "详解", "指南", "教程",
            "细节", "要点", "关键", "系统", "完整", "清晰", "请详细"
        ]

        # 判断问题类型
        question_lower = user_question.lower()
        is_brief_question = len(question_lower.split()) < 10
        wants_details = any(
            indicator in question_lower for indicator in detailed_indicators
        )

        # 返回模板类型， 和service对应
        return (
            "detailed_response"
            if (wants_details or not is_brief_question)
            else "simply_replay"
        )
    
    async def add_relevant_resources(self, user_question: str) -> str:
        """ 根据用户问题添加资源
        """
        keywords_map = {
            "MCP规范协议": ["mcp-doc://4.MCP规范协议.md"],
            "MCP交互流程": ["mcp-doc://6.MCP核心交互流程.md"],
            "MCP": ["mcp-doc://4.MCP规范协议.md", "mcp-doc://6.MCP核心交互流程.md"],
        }

        # 关键字匹配查找
        matched_resources = []
        for keyword, resources in keywords_map.items():
            if keyword in user_question:
                for resource in resources:
                    if (
                        resource in self.resources_dict
                        and resource not in matched_resources
                    ):
                        matched_resources.append(resource)
        
        # 没有匹配则返回原问题
        if not matched_resources:
            return user_question
        
        # 构建增强的问题
        context_parts = []
        for resource in matched_resources:
            context_parts.append(f"--- {resource} ---\n{self.resources_dict[resource]}")

        return (
            user_question + "\n\n相关信息:\n\n" + "\n\n".join(context_parts)
        )

    async def process_query(self, query: str) -> str:
        """处理查询
        """
        user_text = query.strip()
        # 1.选择 prompt
        if self.prompts_dict:
            template_name = await self.selcect_prompt_template(user_text)
            prompt_response = await self.session.get_prompt(
                template_name, arguments={"question": user_text}
            )
            user_text = prompt_response.messages[0].content.text
            print(f"[LOG]: 选择的提示模板: {template_name} \n")

        # 2.添加相关资源
        if self.resources_dict:
            user_text = await self.add_relevant_resources(user_text)

        # 3.消息格式
        messages = [{"role": "user", "content": user_text}]
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