from pprint import pprint
import requests
import nodriver as uc
import random
import time
import sys, os


async def change_proxy(tab):
    try:
        await tab.get('chrome://extensions/')
        script = """
                (async () => {let data = await chrome.management.getAll(); return data;})();
        """

        extensions = await tab.evaluate(expression=script, await_promise=True)
        # print("extensions", extensions)
        if extensions is None:
            print('Проксі розширення не встановлене!')
            return None
        filtered_extensions = [extension for extension in extensions if "BP Proxy Switcher" in extension['name']]

        vpn_id = [extension['id'] for extension in filtered_extensions if 'id' in extension][0]
        vpn_url = f'chrome-extension://{vpn_id}/popup.html'
        await tab.get(vpn_url)
        time.sleep(2)
        select_button = await tab.select('#proxySelectDiv > div > button')
        await select_button.mouse_click()
        time.sleep(2)
        proxy_switch_list = await tab.find_all('#proxySelectDiv > div > div > ul > li')
        if len(proxy_switch_list) == 3:
            await proxy_switch_list[2].scroll_into_view()
            await proxy_switch_list[2].mouse_click()
        else:
            certain_proxy = proxy_switch_list[random.randint(2, len(proxy_switch_list)-1)]
            await certain_proxy.scroll_into_view()
            await certain_proxy.mouse_click()
        time.sleep(5)

        return True
    except Exception as e:
        print('change_proxy function error:', e)
        return False


async def configure_proxy(tab, proxyList):
    try:
        await tab.get('chrome://extensions/')
        time.sleep(2)
        script = """
                (async () => {let data = await chrome.management.getAll(); return data;})();
        """

        extensions = await tab.evaluate(expression=script, await_promise=True)
        # print("extensions", extensions)
        if extensions is None: 
            print('Проксі розширення не встановлене!')
            return None
        filtered_extensions = [extension for extension in extensions if "BP Proxy Switcher" in extension['name']]

        vpn_id = [extension['id'] for extension in filtered_extensions if 'id' in extension][0]
        vpn_url = f'chrome-extension://{vpn_id}/popup.html'
        await tab.get(vpn_url)
        # await tab.get(vpn_url)
        delete_tab = await tab.select('#deleteOptions')
        # driver.evaluate("arguments[0].scrollIntoView();", delete_tab)
        await delete_tab.mouse_click()
        time.sleep(1)
        temp = await tab.select('#privacy > div:first-of-type > input')
        await temp.mouse_click()
        time.sleep(1)
        temp1 = await tab.select('#privacy > div:nth-of-type(2) > input')
        await temp1.mouse_click()
        time.sleep(1)
        temp2 = await tab.select('#privacy > div:nth-of-type(4) > input')
        await temp2.mouse_click()
        time.sleep(1)
        temp3 = await tab.select('#privacy > div:nth-of-type(7) > input')
        await temp3.mouse_click()


        optionsOK = await tab.select('#optionsOK')

        # driver.execute_script("arguments[0].scrollIntoView();", optionsOK)
        await optionsOK.mouse_click()
        time.sleep(1)
        edit = await tab.select('#editProxyList > small > b')
        # driver.execute_script("arguments[0].scrollIntoView();", edit)
        await edit.mouse_click()
        time.sleep(1)
        text_area = await tab.select('#proxiesTextArea')
        for proxy in proxyList:
            js_function = f"""
            (elem) => {{
                elem.value += "{proxy}\\n";
                return elem.value;
            }}
            """
            await text_area.apply(js_function)
        time.sleep(1)
        ok_button = await tab.select('#addProxyOK')
        await ok_button.mouse_click()
        
        proxy_auto_reload_checkbox = await tab.select('#autoReload')
       
        await proxy_auto_reload_checkbox.mouse_click()
        time.sleep(2)

        await change_proxy(tab)

        return True
    except Exception as e:
        print('configure_proxy function error:', e)
        return False


async def create_driver(open_url=None, proxy_list=None):
    """
    Create and return an undetected-chromedriver driver (with extensions and optional remote Selenium host).
    """
    print("[DEBUG] Creating driver…")
    cwd = os.getcwd()
    nopecha_dir='NopeCha'
    extension_path = os.path.join(cwd, nopecha_dir)
    host, port = None, None

    if open_url:
        print(f"[DEBUG] Fetching remote Selenium info from {open_url}")
        resp = requests.get(open_url).json()
        if resp["code"] != 0:
            print(resp["msg"])
            print("please check ads_id")
            sys.exit()
        host, port = resp['data']['ws']['selenium'].split(':')

    # Build nodriver.Config
    if host and port:
        config = uc.Config(
            user_data_dir=None,
            headless=False,
            browser_executable_path=None,
            browser_args=None,
            sandbox=True,
            lang='en-US',
            host=host,
            port=int(port)
        )
        print(f"[DEBUG] Using remote Selenium at {host}:{port}")
    else:
        config = uc.Config(
            user_data_dir=None,
            headless=False,
            browser_executable_path=None,
            browser_args=None,
            sandbox=True,
            lang='en-US'
        )

    # Add extensions
    print(f"[DEBUG] Adding extension from {extension_path}")
    config.add_extension(extension_path=extension_path)
    print("[DEBUG] Adding EditThisCookieChrome.crx and BPProxySwitcher.crx")
    config.add_extension(extension_path="./EditThisCookieChrome.crx")
    config.add_extension(extension_path="./BPProxySwitcher.crx")

    driver = await uc.Browser.create(config=config)
    print("[DEBUG] Driver created successfully")

    # If using proxies, configure them on the main tab
    if proxy_list:
        tab = driver.main_tab
        await configure_proxy(tab, proxy_list)

    return driver