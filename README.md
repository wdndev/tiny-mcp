## 1.简介

MCP Client 是一个基于 Model Context Protocol 的 Python 客户端实现（使用 Function Calling 和 prompt 两种方式），它允许您的应用连接到各种 MCP 服务器，并通过大语言模型（LLM）与这些服务器交互。MCP（模型上下文协议）是一个开放协议，用于标准化应用程序向 LLM 提供上下文的方式。

- `mcp_client_main.py` : 基于 prompt 模式实现 MCP Client, 支持多MCP服务器运行，但只能支持配置文件运行；
- `simple_mcp_client.py` : 基于 Function Calling 模式实现 MCP Client, 只能支持单个 MCP 服务器，支持配置文件和直接调用服务器运行；
- `simple_mcp_client_stream.py` : 基于 Function Calling 模式实现 MCP Client，支持配置文件和直接调用服务器运行，支持流式输出；

## 2.系统 & 目录

### 2.1 系统要求

- 建议Python版本为 `3.11` 以上
- LLM API 密钥 (建议 deepseek )
- 和风天气密钥 (运行天气服务器)

### 2.2 目录结构

```bash
├───.venv                       # uv 虚拟环境, （uv建立）
├───config                      # MCP Server 配置文件
├───docs                        # 文档
├───mcp_client                  # MCP 客户端
├───services                    # MCP 服务器
├───.env.example                # 示例环境变量文件
├───mcp_client_main.py          # MCP 客户端主程序，依赖于 mcp_client 代码， 支持多MCP服务器， prompt 模式开发
├───simple_mcp_client.py        # simple MCP Client，只能支持单个 MCP 服务器， Function Calling 模式开发
├───simple_mcp_client_stream.py # simple MCP Client（流式），只能支持单个 MCP 服务器， Function Calling 模式开发
├───.python-version             # uv Python版本
├───pyproject.toml              # uv 环境依赖
└───uv.lock                     # uv 锁文件
```

## 3.安装和配置

- 克隆仓库

```Bash
https://github.com/wdndev/tiny-mcp.git

cd tiny-mcp
```
- 安装UV

```Bash
# Linux & MAC
使用 curl 下载脚本并通过 sh 执行：

curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
使用 irm 下载脚本并通过 iex 执行：

powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

```
- 安装依赖

```Bash
uv venv --python 3.11
uv sync
```
- 配置环境变量

```Bash
# 复制示例环境变量文件并设置你的 LLM API 密钥：

cp .env.example .env

# 然后编辑 .env 文件，填入你的 LLM API 密钥、模型提供商 API 地址、以及模型名称：

LLM_MODEL_TYPE = "deepseek"
LLM_API_URL = "https://api.deepseek.com"
LLM_API_KEY = "sk-xxxxxxxxxxxxxxxxxx"
LLM_MODEL_NAME = "deepseek-chat"

```

## 4.使用方法

激活uv环境

```Bash
# Linux & MAC
source .venv/bin/activate

# Windows
./.venv/Scripts/activate

```

要启动 MCP 客户端，可以使用以下几种方式：

#### （1）直接指定服务器脚本路径

```Bash
python simple_mcp_client.py <服务器脚本路径>
```

其中`<服务器脚本路径>`是指向 MCP 服务器脚本的路径，可以是 JavaScript (.js) 或 Python (.py) 文件。

#### （2）使用配置文件

```Bash
python simple_mcp_client.py <服务器标识符> <配置文件路径>
```

其中`<服务器标识符>`是配置文件中定义的服务器名称，`<配置文件路径>`是包含服务器定义的 JSON 文件的路径。

```JSON
{
    "mcpServers": {
      "get_current_time": {
        "name": "时间",
        "type": "stdio",
        "description": "获取时间",
        "command": "uv",
        "args": [
          "--directory",
          "E:/04Code/llm/tiny-mcp/services",
          "run",
          "time_service.py"
        ]
      },
      "get_weather": {
        "name": "天气",
        "type": "stdio",
        "description": "获取国内天气",
        "command": "uv",
        "args": [
          "--directory",
          "E:/04Code/llm/tiny-mcp/services",
          "run",
          "weather_service_zh.py"
        ]
      }
    },
    "defaultServer": "get_current_time",
    "system": "自定义系统提示词"
}
```

## 5.运行

直接指定服务器脚本路径运行

```Bash
(tiny-mcp) PS tiny-mcp> python simple_mcp_client.py services/weather_service_zh.py
[SYS]: LLM_MODEL_TYPE:  deepseek
[SYS]:    LLM_API_URL:  https://api.deepseek.com
[SYS]: LLM_MODEL_NAME:  deepseek-chat
[SYS]: 成功连接服务器，可用工具: ['get_weather']
[SYS]: MCP客户端已启动！
[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）
[USR]: 珠海的天气怎么样？可以出去看海吗？

[LOG] Call LLM Messages: [{'role': 'user', 'content': '珠海的天气怎么样？可以出去看海吗？'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'get_weather', 'description': '查询天气情况', 'parameters': {'properties': {'location': {'title': 'Location', 'type': 'string'}}, 'required': ['location'], 'title': 'get_weatherArguments', 'type': 'object'}}}]
[LLM]: ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=[ChatCompletionMessageToolCall(id='call_0_4e1586a5-a278-4e4a-bfa0-8117c3c35b38', function=Function(arguments='{"location":"珠海"}', name='get_weather'), type='function', index=0)])

[LOG]: 调用工具 [get_weather] 参数: {'location': '珠海'}
[LOG]: 工具响应: [TextContent(type='text', text='中国广东省珠海市天气查询成功：\n天气情况：多云\n温度：28°C\n体感温度：29°C\n风向：东南风\n风力等级: 3级\n风速：16公里/小时\n相对湿度：74%\n气压: 1008百帕\n过去一小时降水量:0.0毫米\n能见度: 30 公里\n', annotations=None)]

[LOG] Call LLM Messages: [{'role': 'user', 'content': '珠海的天气怎么样？可以出去看海吗？'}, ChatCompletionMessage(content='', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=[ChatCompletionMessageToolCall(id='call_0_4e1586a5-a278-4e4a-bfa0-8117c3c35b38', function=Function(arguments='{"location":"珠海"}', name='get_weather'), type='function', index=0)]), {'role': 'tool', 'content': "[TextContent(type='text', text='中国广东省珠海市天气查询成功：\\n天气情况：多云\\n温度：28°C\\n体感温度：29°C\\n风向：东 南风\\n风力等级: 3级\\n风速：16公里/小时\\n相对湿度：74%\\n气压: 1008百帕\\n过去一小时降水量:0.0毫米\\n能见度: 30 公里\\n', annotations=None)]", 'tool_call_id': 'call_0_4e1586a5-a278-4e4a-bfa0-8117c3c35b38', 'name': 'get_weather'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'get_weather', 'description': '查询天气情况', 'parameters': {'properties': {'location': {'title': 'Location', 'type': 'string'}}, 'required': ['location'], 'title': 'get_weatherArguments', 'type': 'object'}}}]
[LLM]: ChatCompletionMessage(content='珠海目前的天气是多云，温度28°C，体感温度29°C，风力3级，风速16公里/小时，相对湿度74%。能见度为30公里，非常适合外出。\n\n这样的天气非常适合去看海， 建议带上防晒用品，享受海边的风景！', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=None)


[LLM]: 珠海目前的天气是多云，温度28°C，体感温度29°C，风力3级，风速16公里/小时，相对湿度74%。能见度为30公里，非常适合外出。

这样的天气非常适合去看海，建议带上防晒用品，享受海边的风景！ 

[USR]: quit
```

使用配置文件

```Bash
(tiny-mcp) PS tiny-mcp> python simple_mcp_client.py get_weather config/server_config.json
[SYS]: 成功连接服务器，可用工具: ['get_weather']
[SYS]: MCP客户端已启动！
[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）
[USR]: 珠海天气怎么样？适合出行吗？
[LOG]: 调用工具 [get_weather] 参数: {'location': '珠海'}

[LLM]: 珠海目前的天气情况如下：

- **天气**：阴天
- **温度**：25°C（体感温度27°C）
- **风向**：南风，风力3级，风速14公里/小时
- **湿度**：92%
- **能见度**：12公里
- **降水量**：过去1小时无降水

总体来说，天气较为阴湿，但温度适中，风力不大，适合出行。建议根据个人对湿度的适应情况决定是否外出，并可以携带雨具以防万一。 

[USR]: 北京的天气如何？能去参观天安门吗？
[LOG]: 调用工具 [get_weather] 参数: {'location': '北京'}

[LLM]: 北京的天气目前是中雨，温度为11°C，体感温度为10°C，北风2级，相对湿度100%，能见度为4公里。由于下雨，可能会影响户外活动。

如果您计划参观天安门，建议携带雨具，并注意地面湿滑。如果雨势较大，可能会影响游览体验，建议根据天气情况灵活调整行程。
```

测试 `tools`, `prompts`和`resources` 模块在MCP中客户端和服务端的应用示例：

- 服务端：`services\res_prompt_services.py`
- 客户端：`simple_mcp_client.py`
  - Resources 和 Prompts MCP Service 示例
  - Resources: MCP 的 markdown 文档
  - Prompts: prompt template

```Bash
(tiny-mcp) tiny-mcp> python simple_mcp_client_stream.py services/res_prompt_services.py
[SYS]: LLM_MODEL_TYPE:  deepseek
[SYS]:    LLM_API_URL:  https://api.deepseek.com
[SYS]: LLM_MODEL_NAME:  deepseek-chat
[SYS]: 服务器链接成功 !!!

[SYS]: 可用工具: ['save_to_local']
[SYS]: 可用资源: ['mcp-doc://4.MCP%E8%A7%84%E8%8C%83%E5%8D%8F%E8%AE%AE.md', 'mcp-doc://6.MCP%E6%A0%B8%E5%BF%83%E4%BA%A4%E4%BA%92%E6%B5%81%E7%A8%8B.md']
[SYS]: 可用 Prompt: {'simply_replay': '简洁回答的提示模板', 'detailed_response': '详细回答的提示模板'}
[SYS]: MCP客户端已启动！
[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）
[USR]: 请介绍MCP的交互流程，并保存到本地，文件名为 mcp_interatcion_file.txt

[LOG]: 选择的提示模板: simply_replay

[LOG] Call LLM Messages: [{'role': 'user', 'content': '请简洁地回答以下问题:\n\n请介绍MCP的交互流程，并保存到本地，文件名为 mcp_interatcion_file.txt'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'save_to_local', 'description': '保存问题和回答到本地文件', 'parameters': {'properties': {'file_name': {'title': 'File Name', 'type': 'string'}, 'question': {'title': 'Question', 'type': 'string'}, 'answer': {'title': 'Answer', 'type': 'string'}}, 'required': ['file_name', 'question', 'answer'], 'title': 'save_to_localArguments', 'type': 'object'}}}]
[LLM]: 为了提供一个具体的答案，我需要假设一些关于MCP（可能是某种产品或系统）的信息，因为您没有提供具体的背景信息。通常，一个系统的交互流程会包括用户如何与该系统进行互动的步骤。

假设MCP是一个软件应用，其交互流程可能如下：
1. 用户登录MCP系统。
2. 用户浏览可用的功能或服务。
3. 用户选择一个功能并填写必要的信息。
4. 系统处理请求并返回结果给用户。
5. 用户根据需要重复步骤3-4，直到完成所有任务。
6. 用户退出系统。

现在，我将这个简化的交互流程保存到名为`mcp_interatcion_file.txt`的本地文件中。
{"tool_calls": [{"function": {"name": "save_to_local", "arguments": {"file_name": "mcp_interatcion_file.txt", "question": "请介绍MCP的交互流程", "answer": "1. 用 户登录MCP系统。\n2. 用户浏览可用的功能或服务。\n3. 用户选择一个功能并填写必要的信息。\n4. 系统处理请求并返回结果给用户。\n5. 用户根据需要重复步骤3-4，直到完成所有任务。\n6. 用

[LOG]: 完整工具调用参数: [{"name": "save_to_local", "arguments": {"file_name": "mcp_interatcion_file.txt", "question": "请介绍MCP的交互流程", "answer": "1. 用户登录MCP系统。\n2. 用户浏览可用的功能或服务。\n3. 用户选择一个功能并填写必要的信息。\n4. 系统处理请求并返回结果给用户。\n5. 用户根据需要重复步骤3-4，直到完成所有任务。\n6. 用户退出系统。"}}]
[LOG]: 调用结果: {'meta': None, 'content': [{'type': 'text', 'text': '成功保存到: logs\\mcp_interatcion_file.txt', 'annotations': None}], 'isError': False}
[LOG]: 调用工具 [save_to_local] 参数: {'file_name': 'mcp_interatcion_file.txt', 'question': '请介绍MCP的交互流程', 'answer': '1. 用户登录MCP系统。\n2. 用户浏览可 用的功能或服务。\n3. 用户选择一个功能并填写必要的信息。\n4. 系统处理请求并返回结果给用户。\n5. 用户根据需要重复步骤3-4，直到完成所有任务。\n6. 用户退出系统。'}   
[LOG]: 工具响应: [TextContent(type='text', text='成功保存到: logs\\mcp_interatcion_file.txt', annotations=None)]

[LOG] Call LLM Messages: [{'role': 'user', 'content': '请简洁地回答以下问题:\n\n请介绍MCP的交互流程，并保存到本地，文件名为 mcp_interatcion_file.txt'}, {'role': 'assistant', 'content': None, 'tool_calls': [{'type': 'function', 'id': 'call_d696fa88eab449cc8d223027d948da14', 'function': {'name': 'save_to_local', 'arguments': '{"file_name": "mcp_interatcion_file.txt", "question": "\\u8bf7\\u4ecb\\u7ecdMCP\\u7684\\u4ea4\\u4e92\\u6d41\\u7a0b", "answer": "1. \\u7528\\u6237\\u767b\\u5f55MCP\\u7cfb\\u7edf\\u3002\\n2. \\u7528\\u6237\\u6d4f\\u89c8\\u53ef\\u7528\\u7684\\u529f\\u80fd\\u6216\\u670d\\u52a1\\u3002\\n3. \\u7528\\u6237\\u9009\\u62e9\\u4e00\\u4e2a\\u529f\\u80fd\\u5e76\\u586b\\u5199\\u5fc5\\u8981\\u7684\\u4fe1\\u606f\\u3002\\n4. \\u7cfb\\u7edf\\u5904\\u7406\\u8bf7\\u6c42\\u5e76\\u8fd4\\u56de\\u7ed3\\u679c\\u7ed9\\u7528\\u6237\\u3002\\n5. \\u7528\\u6237\\u6839\\u636e\\u9700\\u8981\\u91cd\\u590d\\u6b65\\u9aa43-4\\uff0c\\u76f4\\u5230\\u5b8c\\u6210\\u6240\\u6709\\u4efb\\u52a1\\u3002\\n6. \\u7528\\u6237\\u9000\\u51fa\\u7cfb\\u7edf\\u3002"}'}}]}, {'role': 'tool', 'content': [{'type': 'text', 'text': '成功保存到: logs\\mcp_interatcion_file.txt', 'annotations': None}], 'tool_call_id': 'call_d696fa88eab449cc8d223027d948da14', 'name': 'save_to_local'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'save_to_local', 'description': '保存问题和回答到本地文件', 'parameters': {'properties': {'file_name': {'title': 'File Name', 'type': 'string'}, 'question': {'title': 'Question', 'type': 'string'}, 'answer': {'title': 'Answer', 'type': 'string'}}, 'required': ['file_name', 'question', 'answer'], 'title': 'save_to_localArguments', 'type': 'object'}}}]
[LLM]: 我已经简要介绍了MCP的交互流程，并将其保存到了文件`mcp_interatcion_file.txt`中。由于您没有提供具体的MCP交互流程内容，我无法给出详细的介绍。如果您能提供更多 信息，我将很乐意帮助您。

[USR]: quit
```

## 6.工作原理

![alt text](docs/image/image.png)

1. 服务器连接：客户端连接到指定的 MCP 服务器
2. 工具发现：自动获取服务器提供的可用工具列表
3. 查询处理：
   - 将用户查询发送给 LLM
   - LLM 决定是否需要使用工具
   - 如果需要，客户端通过服务器执行工具调用
   - 将工具结果返回给 LLM
   - LLM 提供最终回复
4. 交互式循环：用户可以不断输入查询，直到输入"quit"退出


## 7.FAQ

### 7.1 API Key


在本项目中，所有对 LLM 的调用均采用 OpenAI 格式的请求，支持市面上兼容 OpenAI 格式的 API Key。

推荐使用 DeepSeek 的 [API](https://platform.deepseek.com/api_keys)，其价格合理且效果良好。

如果您只想运行此项目并学习 MCP 相关知识，而不愿购买 API Key，可以选择本地部署。对于 Linux 系统，建议使用 VLLM 部署大型模型；对于 Windows 系统，建议使用 Ollama 部署模型。

以下是一个适用于 Windows 系统的 Ollama 部署 qwen2.5:1.5b 模型的 .env 文件示例配置，供参考：

```Bash
LLM_MODEL_TYPE = "ollama"
LLM_API_URL = "http://localhost:11434/v1"
LLM_API_KEY = "ollama"
LLM_MODEL_NAME = "qwen2.5:1.5b"
```

注意：若无GPU资源，可以在 Windows 系统上部署 Ollama + qwen2.5:1.5b 模型，该模型大约占用 2GB 内存，建议至少有 4GB 的内存余量以确保正常运行。测试发现，qwen2.5:0.5b 模型在调用 function call 时存在问题，而 qwen2.5:1.5b 模型调用 function call 则正常。

Ollama + qwen2.5:1.5b 测试示例：

```bash
(tiny-mcp) PStiny-mcp> python simple_mcp_client_stream.py services/weather_service_zh.py
[SYS]: LLM_MODEL_TYPE:  ollama
[SYS]:    LLM_API_URL:  http://localhost:11434/v1
[SYS]: LLM_MODEL_NAME:  qwen2.5:1.5b
[SYS]: 成功连接服务器，可用工具: ['get_weather']
[SYS]: MCP客户端已启动！
[SYS]: 输入自然语言查询开始交互（输入 'quit' 退出）
[USR]: 北京市的天气怎么样？能出去玩吗？

[LOG] Call LLM Messages: [{'role': 'user', 'content': '北京市的天气怎么样？能出去玩吗？'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'get_weather', 'description': '查询天气情况', 'parameters': {'properties': {'location': {'title': 'Location', 'type': 'string'}}, 'required': ['location'], 'title': 'get_weatherArguments', 'type': 'object'}}}]
[LLM]: 

[LOG]: 完整工具调用参数: [{"name": "get_weather", "arguments": {"location": "北京"}}]
[LOG]: 调用结果: {'meta': None, 'content': [{'type': 'text', 'text': '中国北京省北京市天气查询成功：\n天气情况：晴\n温度：20°C\n体感温度：18°C\n风向：南风\n风力等级: 2级\n风速：6公里/小时\n相对湿度：18%\n气压: 1012百帕\n 过去一小时降水量:0.0毫米\n能见度: 30 公里\n', 'annotations': None}], 'isError': False}
[LOG]: 调用工具 [get_weather] 参数: {'location': '北京'}
[LOG]: 工具响应: [TextContent(type='text', text='中国北京省北京市天气查询成功：\n天气情况：晴\n温度：20°C\n体感温度：18°C\n风向：南风\n风力等级: 2级\n风速：6公里/小时\n相对湿度：18%\n气压: 1012百帕\n过去一小时降水量:0.0毫米\n能见度: 30 公里\n', annotations=None)]

[LOG] Call LLM Messages: [{'role': 'user', 'content': '北京市的天气怎么样？能出去玩吗？'}, {'role': 'assistant', 'content': None, 'tool_calls': [{'type': 'function', 'id': 'call_4bkqo3xu', 'function': {'name': 'get_weather', 'arguments': '{"location":"北京"}'}}]}, {'role': 'tool', 'content': [{'type': 'text', 'text': '中国北京省北京市天气查询成功：\n天气情况：晴\n温度：20°C\n体感温度：18°C\n风向：南风\n风力等级: 2级\n风速：6公里/小时\n相 对湿度：18%\n气压: 1012百帕\n过去一小时降水量:0.0毫米\n能见度: 30 公里\n', 'annotations': None}], 'tool_call_id': 'call_4bkqo3xu', 'name': 'get_weather'}]
[LOG] Call LLM Tools: [{'type': 'function', 'function': {'name': 'get_weather', 'description': '查询天气情况', 'parameters': {'properties': {'location': {'title': 'Location', 'type': 'string'}}, 'required': ['location'], 'title': 'get_weatherArguments', 'type': 'object'}}}]
[LLM]: 目前中国北京的天气情况是晴朗，温度大约为20°C。体感温度较为舒适，风向来自南方，属微风级别，风速约为6公里/小时。请注意保暖和随身携带雨具，以防突发降雨。建议带上墨镜、太阳伞等防晒防尘用品，保持良好的体态，并确保车内或外行的安全，随时观察天气变化。当前的空气质量良好，紫外线强，请适量做好防护措施，以保证您的健康安全。
```


## 8.参考文档

- [MCP Docs](https://modelcontextprotocol.io)
- [MCP Docs cn](https://mcp-docs.cn)
- [UV Docs](https://hellowac.github.io/uv-zh-cn)
- [飞书 MCP中文社区](https://larkcommunity.feishu.cn/wiki/FvgIwbijgiXmh8k0Jk2c7nOznXQ)
- [MCP服务器列表](https://github.com/punkpeye/awesome-mcp-servers)

