from typing import Any
from loguru import logger


class MCPTool:
    """ MCP 工具, 更壮工具信息
    """
    def __init__(
        self, 
        name: str,
        description: str, 
        input_schema: dict[str, Any]
    ):
        self.name = name  # 工具名称
        self.description = description  # 工具描述
        self.input_schema = input_schema  # 输入参数模式

    def format_for_llm(self) -> str:
        """ 格式化成 LLM 可理解的格式
        """
        args_desc = []
        if "properties" in self.input_schema:
            # 解析参数属性
            for param_name, param_info in self.input_schema["properties"].items():
                desc = f"- {param_name}: {param_info.get('description', 'No description')}"
                if param_name in self.input_schema.get("required", []):
                    desc += " (required)"
                args_desc.append(desc)
        
        # 生成结构化描述
        return f"""
        Tool: {self.name}
        Description: {self.description}
        Arguments:
        {chr(10).join(args_desc)}
        """.replace("        ", "")
