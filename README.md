# 🍱 Meituan-Mcp-Server (Beta 🚧)

> **English:** An MCP server enabling LLMs to automate Meituan food-ordering via Playwright. 
> **中文:** 基于 Model Context Protocol (MCP) 的美团外卖自动化插件，支持大模型搜索商家与加购。

## 🛠️ 环境搭建
1. **创建环境**: `conda create -n meituan_mcp python=3.10`
2. **安装依赖**: `pip install playwright mcp beautifulsoup4`
3. **安装浏览器**: `playwright install chromium`

## 🔑 使用说明
1. 运行 `python save_auth_meituan.py` 进行人工登录并保存 Session。
2. 运行 `python check_auth_meituan.py` 验证登录状态。
3. 在 Claude Desktop 中配置 `server.py` 路径。

## 📅 开发进展
- [x] 美团 H5 页面适配
- [x] Session 持久化 (auth_meituan.json)
- [x] 商家列表与菜单实时识别
- [ ] 自动结算功能