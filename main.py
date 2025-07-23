from pprint import pprint
import requests
import nodriver as uc
import random
import sounddevice as sd
import soundfile as sf
import threading
import time
import sys, os
import logging
import json
import socket
import eel
from colorama import init, Fore
from utils.helpers import uc_fix
from utils.nodriver_helpers import custom_wait, custom_wait_elements, check_for_element, check_for_elements
from utils.nodriver_init import create_driver


init(autoreset=True)
logger = logging.getLogger("uc.connection")

accounts = []
data = []


def post_request(data):
    try:
        json_data = json.dumps(data)
        
    except Exception as e:
        print(e)
    # Set the headers to specify the content type as JSON
    headers = {
        "Content-Type": "application/json"
    }

    # Send the POST request
    try:
        response = requests.post(f"http://localhost:8010/book", data=json_data, headers=headers)
        print(response)
    except Exception as e:
        print(e)
    # Check the response status code
    if response.status_code == 200:
        print("POST request successful!")
    else:
        print("POST request failed.")


async def handle_captcha_dialog(page):
    """
    If there’s a standalone captcha form (not the login form), click to resolve/continue.
    Return True if we handled a captcha-dialog click; False otherwise.
    """
    try:
        captcha_form = await custom_wait(page, 'form[id="form_captcha"]', timeout=3)
        if captcha_form:
            print("[DEBUG] Captcha form detected—attempting to resolve")
            button = await page.query_selector('div#form_input_buttons> #submit_button')
            await button.click()
            # Wait for the “continue” button inside #action
            cont_btn = await custom_wait(page, '#action > #actionButtonSpan', timeout=10)
            if cont_btn:
                await cont_btn.click()
                print("[DEBUG] Clicked continue on captcha dialog")
            return True
    except Exception as e:
        print(f"[WARN] handle_captcha_dialog exception: {e}")
    return False


async def is_queue(page):
    try:
        queue = await custom_wait(page, '[data-bdd="status-card-container"]', timeout=3)
        if queue:
            print("[DEBUG] Queue detected")
            return True
    except Exception as e:
        print(f"[WARN] is_queue exception: {e}")
    return False


async def is_403(page):
    try:
        ban = await custom_wait(page, '#t1', timeout=3)
        if ban:
            print("[DEBUG] browser has was banned")
            return True
    except Exception as e:
        print(f"[WARN] is_403 exception: {e}")


async def reject_cookies(page):
    cookie_box = await custom_wait(page, 'div > #onetrust-reject-all-handler', timeout=3)
    if cookie_box:
        print("[DEBUG] Rejecting cookies…")
        await cookie_box.mouse_click()


async def wait_for_initial_page(page, actual_link, browser_id=None):
    print(f"[DEBUG] Navigating to main page {actual_link}")
    await page.get(actual_link)

    while True:
        print("[DEBUG] Checking for main page load…")
        # check for queue
        if await is_queue(page):
            print('[DEBUG] waiting for 60 sec..')
            time.sleep(60)
            continue
        # check for 403
        if await is_403(page):
            print(f'[WARNING] browser {browser_id} has been banned, waiting for 2 min..')
            time.sleep(120)
            continue
        # check for page expiration message
        if await check_for_element(page, 'div[role="alert"]'):
            page.get(actual_link)
        return True


async def change_ticket_type(page, ticket_types):
    try:
        await check_for_element(page, 'div[role="toolbar"] > button:nth-child(3)', click=True)
        all_ticket_types_obj = await check_for_elements(page, '#list-view > div > div > div:nth-child(3) > div > div:nth-child(2) > ul > li')
        ticket_type_to_obj = [{obj_name.text: obj} async for obj in all_ticket_types_obj if (obj_name := await check_for_element(obj, 'label > span'))]
        print(ticket_type_to_obj)
        for name, obj in ticket_type_to_obj.items():
            if name in ticket_types: await obj.mouse_click()
        
        return True
    except Exception as e:
        print('change_ticket_type function error:', e)
        return False


async def change_quantity_of_tickets(page, quantity_to_change):
    try:
        await check_for_element(page, 'div[role="toolbar"] > button:nth-child(1)', click=True)

        minus, quantity_obj, plus = await check_for_element(page, '#list-view > div > div > div:nth-child(3) > div > div > div > *')

        if not quantity_obj: return False
        quantity = int(quantity.text)

        operation = minus if quantity_to_change > quantity else plus

        for _ in range(0, abs(quantity_to_change - quantity)): await operation.mouse_click()
        
        return True
    except Exception as e: 
        print('change_amount_of_ticekts function error:', e)
        return False



async def main(
    initial_link, browser_id, total_browsers,
    reload_time, proxy_list=None,
    adspower_api=None, adspower_id=None
):
    """
    Top-level orchestration: set up driver, wait for initial page, filtration, select match & category, click buy, then finalize booking.
    """
    global data
    time.sleep(5)
    adspower_link = ""
    if adspower_api and adspower_id:
        adspower_link = f"{adspower_api}/api/v1/browser/start?serial_number={adspower_id}"
    

    driver = await create_driver(open_url=adspower_link, proxy_list=proxy_list)
    print('returned driver')
    page = driver.main_tab
    print(f"[DEBUG] Navigating to setup page for NopeCha…")
    await page.get('https://nopecha.com/setup#sub_1RWdSzCRwBwvt6ptKAX3W64k|keys=|enabled=true|disabled_hosts=|hcaptcha_auto_open=true|hcaptcha_auto_solve=true|hcaptcha_solve_delay=true|hcaptcha_solve_delay_time=3000|recaptcha_auto_open=true|recaptcha_auto_solve=true|recaptcha_solve_delay=true|recaptcha_solve_delay_time=1000|funcaptcha_auto_open=true|funcaptcha_auto_solve=true|funcaptcha_solve_delay=true|funcaptcha_solve_delay_time=0|awscaptcha_auto_open=true|awscaptcha_auto_solve=true|awscaptcha_solve_delay=true|awscaptcha_solve_delay_time=0|turnstile_auto_solve=true|turnstile_solve_delay=true|turnstile_solve_delay_time=1000|perimeterx_auto_solve=false|perimeterx_solve_delay=true|perimeterx_solve_delay_time=1000|textcaptcha_auto_solve=true|textcaptcha_solve_delay=true|textcaptcha_solve_delay_time=0|textcaptcha_image_selector=#img_captcha|textcaptcha_input_selector=#secret|recaptcha_solve_method=Image')
    browser_part = f"Browser: {adspower_id if adspower_id else browser_id}"
    user_part    = f"User: {os.getlogin()}."
    user_info = "\n".join([user_part + " " + browser_part])
    while True:
        try:
            await wait_for_initial_page(page, initial_link, browser_id=browser_part)
            await reject_cookies(page)
            input('on page, continue?')
            await change_ticket_type(page)
            await change_quantity_of_tickets(page)


        except Exception as e:
            print(f"[ERROR] main encountered exception: {e}")
            time.sleep(60)


@eel.expose
def start_workers(initial_link, browsers_amount, reload_time, proxy_input, adspower_api, adspower_ids, google_sheets_data_link):
    threads = []
    print('start_workers', initial_link, browsers_amount, reload_time, adspower_api, adspower_ids)

    # Case: using adspower API
    if not browsers_amount and all([adspower_api, adspower_ids]):
        total = len(adspower_ids)
        for i in range(1, total + 1):
            ads_id = adspower_ids[i - 1]
            # bind i, total, ads_id into lambda defaults
            thread = threading.Thread(
                target=lambda idx=i, tot=total, aid=ads_id:
                    uc.loop().run_until_complete(
                        main(initial_link, idx, tot, reload_time, proxy_input, adspower_api, aid)
                    )
            )
            threads.append(thread)
            thread.start()

    # Case: fixed number of browsers
    elif browsers_amount and not any([adspower_api, adspower_ids]):
        total = int(browsers_amount)
        for i in range(1, total + 1):
            # bind i, total into lambda defaults
            thread = threading.Thread(
                target=lambda idx=i, tot=total:
                    uc.loop().run_until_complete(
                        main(initial_link, idx, tot, reload_time, proxy_input,)
                    )
            )
            threads.append(thread)
            thread.start()

    # Wait for all to finish
    for thread in threads:
        thread.join()


def is_port_open(host, port):
  try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    sock.connect((host, port))
    return True
  except (socket.timeout, ConnectionRefusedError):
    return False
  finally:
    sock.close()


async def get_location(driver):
    script = f"""
    (function() {{
        return window.location.href
    }}())
    """
    # await the promise, return the JS value directly
    result = await driver.evaluate(
        script,
        await_promise=True,
        return_by_value=True
    )
    return result


if __name__ == "__main__":
    uc_fix(uc)
    eel.init('gui')

    port = 8000
    while True:
        try:
            if not is_port_open('localhost', port):
                eel.start('main.html', size=(600, 800), port=port)
                break
            else:
                port += 1
        except OSError as e:
            print(e)
