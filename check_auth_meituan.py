import asyncio
import os
from playwright.async_api import async_playwright

async def check_status():
    if not os.path.exists("auth_meituan.json"):
        print("❌ 找不到 auth_meituan.json")
        return

    async with async_playwright() as p:
        print("🔍 验证上海 Session 有效性...")
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            **p.devices["iPhone 13"],
            storage_state="auth_meituan.json",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            permissions=["geolocation"],
            geolocation={"longitude": 121.4737, "latitude": 31.2304}
        )
        
        page = await context.new_page()
        await page.goto("https://h5.waimai.meituan.com/")
        
        await asyncio.sleep(3) # 等待加载
        content = await page.content()
        
        if "搜索" in content or "我的" in content:
            print("✅ 状态有效！上海人民广场定位已就绪。")
        else:
            print("⚠️ 状态可能失效，请重新运行 save_auth_meituan.py")
            
        input("\n按回车关闭...")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_status())