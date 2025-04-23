import asyncio
import json
import sys
import re
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union


from ..mcp.mcp_client import MCPClient
from ..llm.llm_service import LLMService
# from ..mcp.mcp_tool import MCPTool

SYSTEM_PROMPT = (
    "你是一个可以使用以下工具的有用助手:\n\n"
    "{tools_descriptions}\n"
    "根据用户的问题选择合适的工具。 "
    "如果不需要工具，请直接回复。\n\n"
    "注意：当你需要使用工具时，必须仅以如下JSON对象格式回复，不要包含其他内容：\n "
    "{{\n"
    '    "tool": "tool-name",\n'
    '    "arguments": {{\n'
    '        "argument-name": "value"\n'
    "    }}\n"
    "}}\n\n"
    "在收到工具响应后：\n"
    "1. 将原始数据转换为自然、对话式的回复\n"
    "2. 保持回复简洁但信息丰富\n"
    "3. 专注于最相关的信息\n"
    "4. 使用用户问题中的适当上下文\n"
    "5. 避免简单重复原始数据\n\n"
    "请仅使用上述明确定义的工具。"
)

@dataclass
class ToolCall:
    """ 工具调用数据类
    """

    tool: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None

    def is_successful(self) -> bool:
        """ 检查工具调用是否成功
        """
        return self.error is None and self.result is not None

    def to_description(self, for_display: bool = False, max_length: int = 200) -> str:
        """ 格式化工具调用为字符串

        Args:
            for_display: 是否格式化显示
            max_length: 最大字符长度

        Returns:
            字符串
        """
        base_description = (
            f"Tool Name: {self.tool}\n"
            f"- Arguments: {json.dumps(self.arguments, indent=2)}\n"
        )
        final_description = base_description
        if self.is_successful():
            result_str = (
                str(self.result)[:max_length] if for_display else str(self.result)
            )
            final_description += f"- Tool call result: {result_str}\n"
        else:
            error_str = str(self.error)[:max_length] if for_display else str(self.error)
            final_description += f"- Tool call error: {error_str}\n"
        return final_description

class ChatSession:
    """ 聊天会话类，协调用户、LLM和工具之间的交互
    """
    def __init__(
        self,
        clients: list[MCPClient],
        llm_service: LLMService,
    ):
        self.clients = clients
        self.llm_service = llm_service 
        self.messages: List[Dict[str, str]] = []
        self.is_initialized: bool = False
        self.tool_client_map = {}

    async def cleanup_clients(self) -> None:
        """ 清理所有服务器
        """
        await asyncio.gather(
            *[asyncio.create_task(client.cleanup()) for client in self.clients],
            return_exceptions=True
        )

    async def initialize(self) -> bool:
        """ MCP 初始化

        """
        try:
            if self.is_initialized:
                return True
            all_tools = []
            all_tools_name = []
            for client in self.clients:
                await client.initialize()
                tools = await client.list_tools()
                all_tools.extend(tools)
                for tool in tools:
                    self.tool_client_map[tool.name] = client
                    all_tools_name.append(tool.name)
                
            print(f"[SYS]: 可用工具: {all_tools_name}")
            print(f"[SYS]: 可用工具: {self.tool_client_map}")

            tools_descriptions = "\n".join([tool.format_for_llm() for tool in all_tools])

            system_message = SYSTEM_PROMPT.format(tools_descriptions=tools_descriptions)
            
            self.messages = [
                {"role": "system", "content": system_message}
            ]    
            
            self.is_initialized = True
            return True
        except Exception as e:
            print(f"[ERR]: 初始化失败: {e}")
            await self.cleanup_clients()
            return False
        
    def _extract_tool_dict(self, llm_response: str) -> List[Dict[str, Any]]:
        """ 从 LLM 的响应中提取工具调用
        """
        try:
            tool_dict = json.loads(llm_response)
            if (
                isinstance(tool_dict, dict)
                and "tool" in tool_dict
                and "arguments" in tool_dict
            ):
                return [tool_dict]
        except json.JSONDecodeError:
            pass
        # Try to extract all JSON objects from the response
        tool_dict = []
        # Regex pattern to match JSON objects
        json_pattern = r"({[^{}]*({[^{}]*})*[^{}]*})"
        json_matches = re.finditer(json_pattern, llm_response)

        for match in json_matches:
            try:
                json_obj = json.loads(match.group(0))
                if (
                    isinstance(json_obj, dict)
                    and "tool" in json_obj
                    and "arguments" in json_obj
                ):
                    tool_dict.append(json_obj)
            except json.JSONDecodeError:
                continue

        return tool_dict
    
    async def _execute_tool_call(self, tool_call_data: Dict[str, Any]) -> ToolCall:
        """ 执行工具调用
        """
        tool_name = tool_call_data["tool"]
        arguments = tool_call_data["arguments"]
        tool_call = ToolCall(tool=tool_name, arguments=arguments)

        # 查找对应服务器
        if tool_name in self.tool_client_map:
            client = self.tool_client_map[tool_name]
            try:
                tool_result = await client.execute_tool(
                    tool_name=tool_name,
                    arguments=arguments
                )
                tool_call.result = tool_result
                return tool_call
            except Exception as e:
                error_msg = f"Error executing tool: {str(e)}"
                print(f"[ERR]: {error_msg}")
                tool_call.error = str(error_msg)
                return tool_call
            
        # 没有工具调用
        tool_call.error = f"No server found with tool: {tool_name}"
        return tool_call
    async def process_tool_calls(
        self,
        llm_response: str
    ) -> Tuple[List[ToolCall], bool]:
        """ 处理 LLM 的响应，并执行工具调用
        """
        tool_call_data_list = self._extract_tool_dict(llm_response)


        print("tool_call_data_list: ", tool_call_data_list)

        if not tool_call_data_list:
            return [], False
        
        tool_calls = []
        for tool_call_data in tool_call_data_list:
            tool_call = await self._execute_tool_call(tool_call_data)
            tool_calls.append(tool_call)

        return tool_calls, True
    
    def _format_tool_result(
        self,
        tool_calls: List[ToolCall],
        max_length: int = 1000,
        for_display: bool = False
    ) -> str:
        """ 格式化工具调用的描述
        """
        tool_str_list = []
        for i, tool in enumerate(tool_calls):
            tool_str = f"Tool Call {i}:\n"
            tool_str += tool.to_description(
                for_display=for_display,
                max_length=max_length
            )
            tool_str_list.append(tool_str)
        return "Tool execution results:\n\n" + "\n".join(tool_str_list)
    
    async def get_llm_response_with_tool_call(
        self,
        user_input_msg: str,
        is_process_tools: bool = True,
        max_iters: int = 5
    ) -> str:
        """ 处理 LLM 的响应，并执行工具调用
        Args:
            user_input_msg (str): 用户输入的消息
            is_process_tools (bool, optional): 是否处理工具调用. Defaults to True.
            max_iters (int, optional): 最大迭代次数. Defaults to 5.
        Returns:
            str: LLM 的响应
        """
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                return "Failed to initialize chat session"
            
        self.messages.append({"role": "user", "content": user_input_msg})

        print("[LOG]: LLM is processing your request...")

        llm_response = self.llm_service.get_response(
            messages=self.messages,
            stream=False
        )
        self.messages.append({"role": "assistant", "content": llm_response})
        print(f"[LOG]: LLM Response: {llm_response}")

        if not is_process_tools:
            return llm_response
        
        # 处理工具调用
        tool_iter = 0
        while tool_iter < max_iters:
            tool_iter += 1
            tool_calls, has_tools = await self.process_tool_calls(llm_response)
            if not has_tools:
                return llm_response
            # 记录工具调用
            for i, tool_call in enumerate(tool_calls):
                print(f"[LOG]: Tool Call {i}: tool_name: {tool_call.tool}, arguments: {tool_call.arguments}")
            
            tool_results = self._format_tool_result(tool_calls)
            self.messages.append({"role": "system", "content": tool_results})
            # 下一次模型生成
            llm_next_response = self.llm_service.get_response(
                messages=self.messages,
                stream=False
            )
            print(f"[LOG]: LLM Next Response: {llm_next_response}")
            self.messages.append({"role": "assistant", "content": llm_next_response})

            # 检查是否存在函数调用
            next_tool_calls_data =self._extract_tool_dict(llm_next_response)
            if not next_tool_calls_data:
                return llm_next_response

    async def get_llm_response_stream_with_tool_call(
        self,
        user_input_msg: str,
        is_process_tools: bool = True,
        max_iters: int = 5
    ) -> AsyncGenerator[Union[str, Tuple[str, str]], None]:
        """ 处理 LLM 的响应，并执行工具调用
        Args:
            user_input_msg (str): 用户输入的消息
            is_process_tools (bool, optional): 是否处理工具调用. Defaults to True.
            max_iters (int, optional): 最大迭代次数. Defaults to 5.
        Returns:
            str: LLM 的响应
        """
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                yield ("error", "Failed to initialize chat session")
                return
        
        self.messages.append({"role": "user", "content": user_input_msg})

        yield ("status", "Thinking...")
        response_chunks = []
        for chunk in self.llm_service.get_response(self.messages, stream=True):
            response_chunks.append(chunk)
            yield ("response", chunk)

        llm_response = "".join(response_chunks)
        self.messages.append({"role": "assistant", "content": llm_response})

        if not is_process_tools:
            return
        
        tool_iter = 0
        while tool_iter < max_iters:
            # 提取工具调用
            tool_call_data_list = self._extract_tool_dict(llm_response)
            if not tool_call_data_list:
                return
            
            # 处理工具调用
            tool_calls = []
            for idx, tool_call_data in enumerate(tool_call_data_list):
                tool_name = tool_call_data["tool"]
                argments = tool_call_data["arguments"]

                yield ("tool_call", tool_name)
                yield ("tool_arguments", json.dumps(argments))

                # 执行工具调用
                yield ("tool_execution", f"Executing tool {tool_name} ...")
                tool_call = await self._execute_tool_call(tool_call_data)
                tool_calls.append(tool_call)
                # 执行结果
                success = tool_call.is_successful()
                yield ("tool_result", json.dumps({
                    "success": success,
                    "result": str(tool_call.result)
                    if success
                    else str(tool_call.error),
                }))

            # 格式化所有工具调用
            tool_results = self._format_tool_result(tool_calls)
            self.messages.append({"role": "system", "content": tool_results})

            # 下一次模型生成
            yield ("status", "Processing results...")
            next_response_chunks = []
            for chunk in self.llm_service.get_response(
                messages=self.messages,
                stream=True
            ):
                next_response_chunks.append(chunk)
                yield ("response", chunk)

            llm_next_response = "".join(next_response_chunks)
            self.messages.append({"role": "assistant", "content": llm_next_response})

            # 检查是否还存在工具调用
            next_tool_calls_data =self._extract_tool_dict(llm_next_response)
            if not next_tool_calls_data:
                return
            
            tool_iter += 1
        

    async def process_llm_response(self, llm_response: str) -> str:
        """ 处理 LLM 的响应，并执行工具调用
        """
        try:
            llm_response = llm_response.replace("```json", "").replace("```", "")
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                # 查找对应服务器
                for server in self.clients:
                    if any(tool.name == tool_call["tool"] for tool in await server.list_tools()):
                        result = await server.execute_tool(tool_call["tool"], tool_call["arguments"])

                        # 处理进度信息
                        if isinstance(result, dict) and "progress" in result:
                            progress = (result["progress"] / result["total"]) * 100
                            print(f"[LOG]: 进度: {progress:.1f}%")
                        
                        return f"工具执行结果: {result}"
                        
                return f"未找到工具: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            print("[ERR]: LLM 响应不是有效的 JSON 格式")
            return llm_response
        
    async def start(self) -> None:
        """ 主循环聊天
        """
        try:
            # 初始化所有服务器
            for server in self.clients:
                try:
                    await server.initialize()
                except Exception as e:
                    print(f"[ERR]: 初始化 server 失败: {e}")
                    await self.cleanup_clients()
                    return

            # 收集所有工具信息
            all_tools = []
            all_tools_name = []
            for server in self.clients:
                tools = await server.list_tools()
                all_tools.extend(tools)
                all_tools_name.extend([tool.name for tool in tools])

            print(f"[SYS]: 可用工具: {all_tools_name}")

            tools_descriptions = "\n".join([tool.format_for_llm() for tool in all_tools])

            system_message = SYSTEM_PROMPT.format(tools_descriptions=tools_descriptions)
            
            messages = [
                {"role": "system", "content": system_message}
            ]

            while True:
                user_input = input("\n[USR]: ").strip().lower()
                print()
                if user_input in ["quit", "exit"]:
                    print("[SYS]: \n退出聊天")
                    break

                messages.append({"role": "user", "content": user_input})

                # 获取LLM输出
                llm_stream = self.llm_service.get_response(messages, stream=True)
                # print(f"[LOG]: {llm_response}")
                sys.stdout.write("[LOG]: ")
                sys.stdout.flush()
                llm_response = ""
                for content_chunk in llm_stream:
                    if content_chunk:
                        sys.stdout.write(content_chunk)
                        sys.stdout.flush()
                        llm_response += content_chunk
                print("\n")  # 流式输出结束后换行

                # 工具调用
                processed_result = await self.process_llm_response(llm_response)

                # 处理
                if processed_result != llm_response:
                    messages.append({"role": "assistant", "content": llm_response})
                    messages.append({"role": "system", "content": processed_result})
                    
                    llm_stream = self.llm_service.get_response(messages, stream=True)
                    # print(f"[LLM]: {final_response}")
                    sys.stdout.write("[LLM]: ")
                    sys.stdout.flush()
                    final_response = ""
                    for content_chunk in llm_stream:
                        if content_chunk:
                            sys.stdout.write(content_chunk)
                            sys.stdout.flush()
                            final_response += content_chunk
                    print("\n")  # 流式输出结束后换行

                else:
                    messages.append({"role": "assistant", "content": llm_response})
        
        finally:
            await self.cleanup_clients()