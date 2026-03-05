import asyncio
import os
import sys
import random
from mcp.server import Server
from mcp.types import Tool, TextContent
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- 环境初始化 ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(CURRENT_DIR)
sys.path.append(CURRENT_DIR)

server = Server("meituan-bot")

class BrowserState:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        # --- 记忆模块：专门存储上次 fetch 到的商户名 ---
        self.remembered_shops = [] 

state = BrowserState()

async def show_click_feedback(page, x, y):
    await page.evaluate(f'''
        () => {{
            const dot = document.createElement('div');
            dot.style.position = 'fixed';
            dot.style.left = '{x}px';
            dot.style.top = '{y}px';
            dot.style.width = '30px';
            dot.style.height = '30px';
            dot.style.backgroundColor = 'rgba(255, 0, 0, 0.7)';
            dot.style.borderRadius = '50%';
            dot.style.border = '3px solid #FFD700';
            dot.style.pointerEvents = 'none';
            dot.style.zIndex = '999999';
            dot.style.transform = 'translate(-50%, -50%)';
            dot.style.boxShadow = '0 0 15px rgba(255,0,0,0.8)';
            document.body.appendChild(dot);
            setTimeout(() => {{ if (dot.parentElement) document.body.removeChild(dot); }}, 1500);
        }}
    ''')
    await asyncio.sleep(1.5)

async def human_smooth_scroll(page, distance):
    scrolled = 0
    is_down = distance > 0
    abs_dist = abs(distance)
    while scrolled < abs_dist:
        step = random.randint(300, 700) 
        if scrolled + step > abs_dist:
            step = abs_dist - scrolled
        await page.mouse.wheel(0, step if is_down else -step)
        scrolled += step
        await asyncio.sleep(random.uniform(0.04, 0.08))
    await asyncio.sleep(1.8)

async def ensure_browser():
    if state.page is None:
        state.playwright = await async_playwright().start()
        state.browser = await state.playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        storage_path = "auth_meituan.json"
        storage_state = storage_path if os.path.exists(storage_path) else None
        device = state.playwright.devices["iPhone 13"]
        state.context = await state.browser.new_context(
            **device,
            storage_state=storage_state,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],
            geolocation={"longitude": 121.4737, "latitude": 31.2304}
        )
        state.page = await state.context.new_page()
        try:
            await state.page.goto("https://h5.waimai.meituan.com/", wait_until="networkidle")
        except: pass

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(name="fetch_meituan_content", description="获取列表（自动判断状态并清洗商户/菜品残留）", inputSchema={"type": "object"}),
        Tool(name="smart_scroll", description="按像素滑动", 
             inputSchema={"type": "object", "properties": {"distance": {"type": "integer"}}, "required": ["distance"]}),
        Tool(name="click_target", description="点击餐厅名进入商店", 
             inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        Tool(name="add_food_to_cart", description="点击菜品名进详情页加购", 
             inputSchema={"type": "object", "properties": {"food_name": {"type": "string"}}, "required": ["food_name"]})
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    await ensure_browser()
    
    if name == "fetch_meituan_content":
        await asyncio.sleep(1.5)
        content = await state.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # 识别当前页面特征
        has_add_btn = soup.find(attrs={"aria-label": "增加"}) is not None
        has_cart = soup.select_one('[class*="cart"], .shopping-cart') is not None
        is_in_menu = has_add_btn or has_cart
        
        # 统一的选择器
        selectors = ['.shop-name', '.wm-item-title', 'h3', 'div[class*="name"]', '.food-name', 'span[class*="name"]']
        raw_list = []
        for s in selectors:
            for tag in soup.select(s):
                txt = tag.get_text().strip()
                if txt and len(txt) > 1 and not any(x in txt for x in ["搜索", "配送", "评价", "月售", "公告"]):
                    raw_list.append(txt)
        
        unique_raw = list(dict.fromkeys(raw_list))

        if is_in_menu:
            page_label = "🍴 菜单模式"
            # --- 核心逻辑：从菜品列表里直接删掉之前记住的商户名 ---
            final_items = [x for x in unique_raw if x not in state.remembered_shops]
        else:
            page_label = "🏠 商户模式"
            final_items = unique_raw
            # 在商户模式下，实时更新“商户名单”记忆
            state.remembered_shops = unique_raw

        res = f"📊 状态：【{page_label}】\n列表内容 ({len(final_items)}项)：\n" + \
              "\n".join([f"[{i}] {s}" for i, s in enumerate(final_items)])
        return [TextContent(type="text", text=res)]

    elif name == "smart_scroll":
        await human_smooth_scroll(state.page, arguments["distance"])
        return [TextContent(type="text", text="✅ 滑动完成")]

    elif name == "click_target":
        text = arguments["text"]
        target = state.page.get_by_text(text).last
        if await target.is_visible():
            box = await target.bounding_box()
            if box:
                await show_click_feedback(state.page, box['x'] + box['width']/2, box['y'] + box['height']/2)
            await target.click()
            await asyncio.sleep(3)
            return [TextContent(type="text", text=f"🔴 已进入：{text}")]
        return [TextContent(type="text", text=f"❌ 找不到：{text}")]

    elif name == "add_food_to_cart":
        food_name = arguments["food_name"]
        target_loc = state.page.get_by_text(food_name).last
        if await target_loc.is_visible():
            box = await target_loc.bounding_box()
            if box:
                await show_click_feedback(state.page, box['x'] + box['width']/2, box['y'] + box['height']/2)
                await target_loc.click()
                await asyncio.sleep(2.5) 
                # 详情页加购
                for btn_txt in ["加入购物车", "选好了", "确定"]:
                    btn = state.page.get_by_text(btn_txt).last
                    if await btn.is_visible():
                        b_box = await btn.bounding_box()
                        if b_box: await show_click_feedback(state.page, b_box['x'] + b_box['width']/2, b_box['y'] + b_box['height']/2)
                        await btn.click()
                        return [TextContent(type="text", text=f"✅ 已通过详情页加购：{food_name}")]
        return [TextContent(type="text", text=f"❌ 操作失败，请确保菜品可见")]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())