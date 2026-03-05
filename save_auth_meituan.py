import asyncio
from playwright.async_api import async_playwright

async def save_meituan_session():
    async with async_playwright() as p:
        print("🛠️ 启动【上海专用】环境...")
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # 使用你 manual_test.py 中验证成功的配置
        context = await browser.new_context(
            **p.devices["iPhone 13"],
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],
            geolocation={"longitude": 121.4737, "latitude": 31.2304}
        )

        page = await context.new_page()

        print("🚀 模拟人工开启网址...")
        # 技巧：先去一个中间页，再通过模拟键盘动作进入美团
        await page.goto("about:blank") 
        await asyncio.sleep(1)
        
        # 模拟你在地址栏输入并回车的效果
        # 虽然 Playwright 不能直接点物理地址栏，但我们可以通过 API 触发最接近的导航行为
        await page.evaluate('window.location.href = "https://h5.waimai.meituan.com/"')

        print("🚨 请在弹出的窗口完成登录。")
        print("💡 确认定位在【上海】且看到商家列表后，回来按回车...")
        
        input("👉 登录完成后，按回车保存状态...")

        # 保存状态到本地
        await context.storage_state(path="auth_meituan.json")
        print("✅ 上海身份已存至 auth_meituan.json")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(save_meituan_session())