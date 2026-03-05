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

state = BrowserState()

# --- 视觉反馈：红点锁定 ---
async def show_click_feedback(page, x, y):
    """在点击位置显示红点并停留 1.5 秒，让你看清 Claude 的操作"""
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
    """模拟真人滑动：大步幅（300-700px）确保 H5 加载"""
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
        Tool(name="fetch_meituan_content", description="获取列表（实时识别环境并展示带序号的菜单或商户）", inputSchema={"type": "object"}),
        Tool(name="smart_scroll", description="按条目数滑动（180px/条）", 
             inputSchema={"type": "object", "properties": {"item_count": {"type": "integer"}}, "required": ["item_count"]}),
        Tool(name="click_target", description="点击餐厅名进入商店", 
             inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}),
        Tool(name="add_food_to_cart", description="点击菜名进详情页并加购", 
             inputSchema={"type": "object", "properties": {"food_name": {"type": "string"}}, "required": ["food_name"]})
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    await ensure_browser()
    
    if name == "fetch_meituan_content":
        await asyncio.sleep(1)
        content = await state.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # --- 环境检测：是否已进入菜单页 ---
        # 寻找加号按钮、菜品容器或具体的类名
        is_in_menu = soup.select_one('.food-list, .menu-list, [class*="food-item"], [aria-label="增加"]')
        
        items = []
        if is_in_menu:
            # 🍴 菜单模式：只抓菜品
            selectors = ['.food-name', 'span[class*=\"name\"]', 'div[class*=\"food\"] b', '.product-name']
            page_label = "🍴 菜单列表"
        else:
            # 🏠 商店列表模式
            selectors = ['.shop-name', '.wm-item-title', 'h3', 'div[class*=\"name\"]']
            page_label = "🏠 商店列表"

        for s in selectors:
            for tag in soup.select(s):
                txt = tag.get_text().strip()
                # 过滤无意义字符
                if txt and len(txt) > 1 and not any(x in txt for x in ["搜索", "配送", "评价", "月售"]):
                    items.append(txt)
        
        unique_items = list(dict.fromkeys(items))
        
        if not unique_items:
            return [TextContent(type="text", text=f"⚠️ 当前处于【{page_label}】，但未识别到具体项，请尝试滑动。")]

        res = f"📊 当前处于【{page_label}】，识别到 ({len(unique_items)}项)：\n" + \
              "\n".join([f"[{i}] {s}" for i, s in enumerate(unique_items)])
        return [TextContent(type="text", text=res)]

    elif name == "smart_scroll":
        await human_smooth_scroll(state.page, arguments["item_count"] * 180)
        return [TextContent(type="text", text="✅ 已完成滑动寻找。")]

    elif name == "click_target":
        text = arguments["text"]
        target = state.page.get_by_text(text).last
        if await target.is_visible():
            box = await target.bounding_box()
            if box:
                await show_click_feedback(state.page, box['x'] + box['width']/2, box['y'] + box['height']/2)
            await target.click()
            await asyncio.sleep(2)
            return [TextContent(type="text", text=f"🔴 已成功进店：{text}")]
        return [TextContent(type="text", text=f"❌ 未能找到：{text}")]

    elif name == "add_food_to_cart":
        food_name = arguments["food_name"]
        # 先尝试在屏幕内找菜名
        target_loc = state.page.get_by_text(food_name).last
        
        if not await target_loc.is_visible():
            return [TextContent(type="text", text=f"❌ 菜品 '{food_name}' 不在当前视野内，请先根据 fetch 结果计算 item_count 并调用 smart_scroll。")]

        box = await target_loc.bounding_box()
        if box:
            # 1. 点击菜名进详情页
            await show_click_feedback(state.page, box['x'] + box['width']/2, box['y'] + box['height']/2)
            await target_loc.click()
            await asyncio.sleep(2.5) 
            
            # 2. 在详情页寻找加购按钮
            found_btn = False
            for btn_text in ["加入购物车", "选好了", "确定", "下一步", "确定并加入"]:
                btn = state.page.get_by_text(btn_text).last
                if await btn.is_visible():
                    b_box = await btn.bounding_box()
                    if b_box:
                        await show_click_feedback(state.page, b_box['x'] + b_box['width']/2, b_box['y'] + b_box['height']/2)
                    await btn.click()
                    found_btn = True
                    break
            
            if found_btn:
                return [TextContent(type="text", text=f"✅ 已通过详情页成功加购：{food_name}")]
            return [TextContent(type="text", text=f"⚠️ 已进入详情页，但未发现加购按钮，可能需要手动选规格。")]
        
        return [TextContent(type="text", text=f"❌ 锁定菜品坐标失败")]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())