from pprint import pprint
import requests
import nodriver as uc
import random
import sounddevice as sd
import soundfile as sf
import threading
import time
import sys, os
import re
import json
import socket
import time
import eel
from utils.helpers import uc_fix
from utils.nodriver_helpers import custom_wait, custom_wait_elements, check_for_element, check_for_elements
from utils.nodriver_init import change_proxy, configure_proxy, create_driver
from utils.filtration import get_event_data_based_on_link
from utils.sheets_api import GoogleSheetClient

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
        response = requests.post(f"http://localhost:8015/book", data=json_data, headers=headers)
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


async def wait_for_initial_page(page, actual_link, browser_info):
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
            print(f'[WARNING] browser {browser_info} has been banned, waiting for 2 min..')
            text = f"CAPTCHA"
            message = "\n".join([browser_info, text])
            post_request(message)
            time.sleep(120)
            continue
        # check for page expiration message
        if await check_for_element(page, 'div[role="alert"]'):
            page.get(actual_link)
        return True


async def change_ticket_type(page, blacklist):
    try:
        await check_for_element(page, 'div[role="toolbar"] > button:nth-child(3)', click=True)
        all_ticket_types_obj = await check_for_elements(page, '#list-view > div > div > div:nth-child(3) > div > div:nth-child(2) > ul > li')

        ticket_type_to_obj = []
        for obj in all_ticket_types_obj:
            obj_name = await check_for_element(obj, 'label > span')
            if obj_name:
                ticket_type_to_obj.append({obj_name.text: obj_name})

        for item in ticket_type_to_obj:
            for name, element in item.items():
                if name not in blacklist: 
                    await element.scroll_into_view()
                    await element.mouse_click()
        
        return True
    except Exception as e:
        print('change_ticket_type function error:', e)
        return False


async def change_quantity_of_tickets(page, quantity_to_change):
    try:
        await check_for_element(page, 'div[role="toolbar"] > button:nth-child(1)', click=True)
        minus, quantity_obj, plus = await check_for_elements(page, '#list-view > div > div > div:nth-child(3) > div > div > div > *')

        if not quantity_obj: return False
        quantity = int(quantity_obj.text)

        operation = minus if quantity_to_change > quantity else plus

        for _ in range(0, abs(quantity_to_change - quantity)): await operation.mouse_click()
        
        return True
    except Exception as e: 
        print('change_amount_of_tickets function error:', e)
        return False


async def scroll_tickets_list(page):
    try:
        loaded_count_element = await check_for_element(page, '#quickpicks-list > div:nth-child(3) > span')
        if not loaded_count_element: 
            print('No tickets found')
            return None
        loaded_count = loaded_count_element.text
        current_loaded, total_items = map(int, re.search(r"Loaded (\d+) of (\d+)", loaded_count).groups())
        
        temp_current_loaded = 0
        while not await check_for_element(page, '[class*="LoadingSpinner"]'):
            loaded_count_element = await custom_wait(page, '#quickpicks-list > div:nth-child(3) > span', timeout=15)
            if not loaded_count_element: return None
            loaded_count = loaded_count_element.text
            current_loaded, total_items = map(int, re.search(r"Loaded (\d+) of (\d+)", loaded_count).groups())
            print('comparison', temp_current_loaded, current_loaded)
            if current_loaded == temp_current_loaded: return True
            else: temp_current_loaded = current_loaded
            if total_items == current_loaded: return True
            await loaded_count_element.scroll_into_view()
            time.sleep(1)
        return True
    except Exception as e:
        print('scroll_tickets_list function error', e)
        return False


async def purchase_tickets(page, ticket):
    try:
        await ticket.scroll_into_view()
        await ticket.click()
        await custom_wait(page, 'button[data-bdd="offer-card-buy-button"]', timeout=5)
        get_tickets_button = await check_for_element(page, 'button[data-bdd="offer-card-buy-button"]')
        time.sleep(1)
        await get_tickets_button.mouse_click()
        time.sleep(1)
        counter = 0
        while await check_for_element(page, 'div[role="alert"]'):
            if counter >= 20: return False
            else: time.sleep(1)
        return True
    except Exception as e:
        print('purchase tickets function error', e)
        return False
    

async def parse_ticket(ticket):
    try:
        place = await check_for_element(ticket, 'dl')
        place_info = place.text_all
        category = await check_for_element(ticket, 'div:nth-child(2) > div span:nth-child(1)')
        category_info = category.text
        price = await check_for_element(ticket, 'div:nth-child(2) > div span:nth-child(2)')
        price_info = price.text
        return {'price': price_info, 'category': category_info, 'place': place_info}
    except Exception as e:
        print('parse_tickets function error', e)
        return False


async def finalize_booking(page, browser_info, event_data, ticket_info):
    if 'auth.ticketmaster.com' not in await get_location(page):
        print('Book is not successfull')
        return False
    print(f"[INFO] {browser_info}. Booking succeeded—playing notification sound")

    post_data = {"data": f"{browser_info}\nevent: {event_data.get('name')}\ncity: {event_data.get('city')}\ndate: {event_data.get('date')}\nПіймано квитків: {event_data.get('quantity')}\nКатегорія: {ticket_info.get('category')}\nЦіна: {ticket_info.get('price')}\Місце: {ticket_info.get('place')}"}
    print(post_data)
    post_request(post_data)
    sound, fs = sf.read('notify.wav', dtype='float32')
    sd.play(sound, fs)
    sd.wait()

    input("Press Enter to continue after booking…")
    return True

    


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
    page = driver.main_tab
    
    print(f"[DEBUG] Navigating to setup page for NopeCha…")
    await page.get('https://nopecha.com/setup#sub_1RWdSzCRwBwvt6ptKAX3W64k|keys=|enabled=true|disabled_hosts=|hcaptcha_auto_open=true|hcaptcha_auto_solve=true|hcaptcha_solve_delay=true|hcaptcha_solve_delay_time=3000|recaptcha_auto_open=true|recaptcha_auto_solve=true|recaptcha_solve_delay=true|recaptcha_solve_delay_time=1000|funcaptcha_auto_open=true|funcaptcha_auto_solve=true|funcaptcha_solve_delay=true|funcaptcha_solve_delay_time=0|awscaptcha_auto_open=true|awscaptcha_auto_solve=true|awscaptcha_solve_delay=true|awscaptcha_solve_delay_time=0|turnstile_auto_solve=true|turnstile_solve_delay=true|turnstile_solve_delay_time=1000|perimeterx_auto_solve=false|perimeterx_solve_delay=true|perimeterx_solve_delay_time=1000|textcaptcha_auto_solve=true|textcaptcha_solve_delay=true|textcaptcha_solve_delay_time=0|textcaptcha_image_selector=#img_captcha|textcaptcha_input_selector=#secret|recaptcha_solve_method=Image')
    browser_part = f"Browser: {adspower_id if adspower_id else browser_id}"
    user_part    = f"User: {os.getlogin()}."
    user_info = "\n".join([user_part + " " + browser_part])

    while True:
        try:
            await wait_for_initial_page(page, initial_link, user_info)
            await reject_cookies(page)
            current_location = await get_location(page)

            event_data = get_event_data_based_on_link(data, current_location)
            if not event_data:
                print('Не було знайдено даних про цю подію в гугл таблиці.')
                time.sleep(random.randint(reload_time[0], reload_time[1]))
                continue
            
            # filter tickets on page
            await change_ticket_type(page, event_data.get('blacklist'))
            await change_quantity_of_tickets(page, event_data.get('quantity'))
            time.sleep(2)
            if not await custom_wait(page, '#quickpicks-list', timeout=15): 
                print('No tickets found')
                time.sleep(random.randint(reload_time[0], reload_time[1]))
                continue
            stl = await scroll_tickets_list(page)
            if stl == None:
                print('No tickets found')
                time.sleep(random.randint(reload_time[0], reload_time[1]))
                continue
            tickets = await custom_wait_elements(page, '#quickpicks-list > div:nth-child(1) > div[role="button"]', timeout=15)
            print('found tickets', len(tickets))
            random_ticket = random.choice(tickets)
            ticket_info = await parse_ticket(random_ticket)
            await purchase_tickets(page, random_ticket)
            # Error modal
            await check_for_element(page, '#modals div[role="dialog"] button', click=True)
            # These Tickets Are No Longer Available modal
            await check_for_element(page, 'div[role="alertdialog"] > div:nth-child(4) > button', click=True)
            time.sleep(2)
            result = await finalize_booking(page, user_info, event_data, ticket_info)
            if not result:
                print('Purchase is not successful, reloading page...')
                time.sleep(random.randint(reload_time[0], reload_time[1]))
                continue
        except Exception as e:
            print(f"[ERROR] main encountered exception: {e}")
            time.sleep(60)


@eel.expose
def start_workers(initial_link, browsers_amount, reload_time, proxy_input, adspower_api, adspower_ids, google_sheets_data_link):
    threads = []
    print('start_workers', initial_link, browsers_amount, reload_time, adspower_api, adspower_ids)

    if google_sheets_data_link:
        polling_thread = threading.Thread(
            target=poll_sheet_every,
            args=(60.0, google_sheets_data_link, ''),
            daemon=True 
        )
        polling_thread.start()
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

def poll_sheet_every(interval: float, sheets_data_link: str, sheets_accounts_link: str):
    """
    Poll the Google Sheet every `interval` seconds.
    """
    global data
    
    data_client = GoogleSheetClient(sheets_data_link, "main")
    # accounts_client = GoogleSheetClient(sheets_accounts_link, "main")
     
    while True:
        try:
            data_response = data_client.fetch_sheet_data()
            # accounts_response = accounts_client.fetch_sheet_columns("A2:B")
            print('[DEBUG] google sheets data retrieved: ', str(data_response)[:25] + '...')
            if not data_response:
                print(f"Data response is empty, retrying in {interval} seconds...") 
                time.sleep(interval)
                continue
            
            data = data_response
        except Exception as e:
            print(f"Error fetching sheet data: {e!r}")
        time.sleep(interval)


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
