import os
import json
import csv
import pathlib
import shutil
from threading import Thread
from urllib.parse import unquote, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import requests
from bs4 import BeautifulSoup
import logging

WRK_DIR = pathlib.Path(__file__).parent.resolve()
OUTPUT_FILENAME = "output.csv"
PROXY_FILENAME = "proxy_config.txt"
LOG_FILENAME = "brownbook.log"
BASE_URL = "https://www.brownbook.net/search/worldwide/{location}/{keyword}/?page={page}"
BUSINESS_API = "https://api.brownbook.net/app/api/v1/business/{business_id}/fetch"
HEADERS = {
    'authority': 'www.brownbook.net',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.6',
    'Referer': 'https://google.com/',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Brave";v="122"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}
THREAD_STATUS = False
TEXT_FONTS = ("Times New Roman", 14)

# logging config
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(os.path.join(WRK_DIR, LOG_FILENAME))
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.propagate = False


def print_ui_logs(mgs):
    # existing_msg = log_status.get()
    # existing_msg += "\n" + mgs
    log_status.set(mgs)


def check_live_proxy(proxy):
    """
    supported proxy types are http and socks
    """
    base_proxy = {'http': "http://"}

    if proxy["username"] and proxy["password"]:
        base_proxy["http"] += f"{proxy['username']}:{proxy['password']}@"

    base_proxy["http"] += f"{proxy['host']}:{proxy['port']}"
    try:
        response = requests.get("http://httpbin.org/ip", proxies=base_proxy, headers=HEADERS, timeout=10)
        if response.ok:
            logger.debug(f"Alive Proxy: {proxy['host']}")
            print_ui_logs(f'Alive Proxy: {proxy["host"]}')
            app.update_idletasks()
            return base_proxy
    except Exception:
        logger.error("Dead Proxy: " + proxy["host"])
        print_ui_logs(f'Dead Proxy: {proxy["host"]}')
        app.update_idletasks()
        return None


def read_from_csv(filename):
    try:
        with open(filename, "r", newline='', encoding="UTF-8") as fp:
            reader = csv.reader(fp)
            headers = next(reader)
            return headers, list(reader)
    except Exception as e:
        logger.error(f"Error while reading csv file, {e}")
        return None, None


def get_proxy():
    filepath = os.path.join(WRK_DIR, PROXY_FILENAME)
    with open(filepath, "r", newline='', encoding="UTF-8") as fp:
        data = fp.readlines()

    proxies = []
    for line in data:
        if not line:
            continue
        cols = line.split(":")
        if len(cols) == 2:
            proxies.append({"host": cols[0], "port": cols[1]})
        elif len(cols) == 4:
            proxies.append({"host": cols[0], "port": cols[1], "username": cols[2], "password": cols[3]})

    if not proxies:
        raise AttributeError("No proxies")

    logger.debug("testing live proxies")
    with ThreadPoolExecutor(max_workers=15) as exe:
        futures = exe.map(check_live_proxy, proxies)
        live_proxies = [i for i in list(futures) if i]

    logger.info(f"Found {len(live_proxies)} live proxies")
    if len(live_proxies) < 1:
        raise AttributeError("No live proxies found")

    index = 0
    while True:
        if index == len(live_proxies):
            index = 0
            continue
        yield live_proxies[index]
        index += 1


# def get_proxy():
#     headers, rows = read_from_csv(filename=os.path.join(WRK_DIR, PROXY_FILENAME))
#     if not headers:
#         raise ValueError("Proxy csv file not found.")
#     data = [dict(zip(headers, row)) for row in rows]
#
#     logger.debug("testing live proxies")
#     with ThreadPoolExecutor(max_workers=15) as exe:
#         futures = exe.map(check_live_proxy, data)
#         live_proxies = [i for i in list(futures) if i]
#
#     logger.info(f"Found {len(live_proxies)} live proxies")
#     if len(live_proxies) < 1:
#         raise AttributeError("No live proxies found")
#
#     index = 0
#     while True:
#         if index == len(live_proxies):
#             index = 0
#             continue
#         yield live_proxies[index]
#         index += 1


def downgrade_url_http(url):
    url = url.split(":")
    url[0] = url[0][:-1]
    return ":".join(url)


def request_page(url, *args, **kwargs):
    logger.debug("Requesting " + url)
    print_ui_logs(f"Requesting data from {url}")
    retry = kwargs.pop('retry', 0)
    max_retries = kwargs.pop('max_retries', 3)
    proxies = kwargs.pop("proxy", None)
    if proxies:
        url = downgrade_url_http(url)
        proxies = next(proxies)
    response = requests.get(url, headers=HEADERS, timeout=20, proxies=proxies, *args, **kwargs)
    if not response.ok and retry < max_retries:
        logger.error(f"Retrying {url} with {retry}/{max_retries} time")
        print_ui_logs(f"Retrying {url} with {retry}/{max_retries} time")
        app.update_idletasks()
        return request_page(url, retry=retry + 1, *args, **kwargs)
    app.update_idletasks()
    return response


def get_total_count(url):
    response = request_page(url)
    soup = BeautifulSoup(response.text, "html.parser")
    for total_records in soup.findAll("span", {"class": 'font-bold'}):
        total_records = total_records.text
        try:
            if total_records:
                return int(total_records.strip())
        except ValueError:
            continue
    return 0


def parse_business_ids(soup):
    urls_soup = soup.find_all("a", {"aria-label": "business-link"})

    business_ids = []
    for urls in urls_soup:
        url = urls.get("href")
        try:
            business_id = url.split("/")[2]
            business_ids.append(int(business_id))
        except ValueError:
            logger.debug("business id not found " + url)
        except AttributeError:
            logger.debug("business id URL is None " + urls)

    return business_ids


def is_next_page(soup):
    next_page = soup.find("button", {"id": "nav-right-arrow"})
    if next_page:
        return True
    return False


def convert_bool(num):
    if str(num) == "1":
        return "Yes"
    elif str(num) == "0":
        return "No"
    else:
        return ""


def parse_business_data(response, keyword):
    try:
        business_data = json.loads(response.text)
    except json.decoder.JSONDecodeError:
        logger.error("Error parsing json data.." + response.url)
        return

    if business_data["message"] != "Business has been retrieved":
        logger.error("Status not ok.. " + response.url)
        return

    data = dict()
    business_data = business_data["data"]["metadata"]
    data["Business Id"] = business_data.get("id")
    data["Business Category"] = unquote(keyword)
    data["Business Name"] = business_data.get("name")
    data["Contact Name"] = business_data["user"].get("name")
    data["Contact Email"] = business_data["user"].get("email")
    data["Business Email"] = business_data.get("email")
    data["Phone"] = business_data.get("phone", "")
    data["Mobile"] = business_data.get("mobile", "")
    data["Website"] = business_data.get("website", "")
    data["Address"] = business_data.get("address", "")
    data["City"] = business_data.get("city", "")
    data["Zip Code"] = business_data.get("zipcode", "")
    data["Claimed"] = convert_bool(business_data.get("claimed", ""))
    data["Claim Verified"] = convert_bool(business_data.get("claim_verified", ""))
    data["Country"] = business_data.get("country_code", "")
    data["Facebook"] = business_data.get("facebook", "")
    data["Instagram"] = business_data.get("instagram", "")
    data["Linkedin"] = business_data.get("linkedin", "")
    data["Tiktok"] = business_data.get("tiktok", "")
    data["Twitter"] = business_data.get("twitter", "")
    data["URL"] = f'/{business_data.get("id", "")}{business_data.get("link", "")}'
    return data


def get_business_data(business_id, keyword):
    url = BUSINESS_API.format(business_id=business_id)
    response = request_page(url)
    try:
        data = parse_business_data(response, keyword)
        return data
    except Exception as e:
        logger.debug(e)
        return None


def write_to_csv(data):
    filename = os.path.join(WRK_DIR, OUTPUT_FILENAME)
    columns = list(data[0].keys())

    with open(filename, mode="w", newline='', encoding="UTF-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns)
        writer.writeheader()

        for row in data:
            writer.writerow(row)

    return filename


def clean_actions(**kwargs):
    global THREAD_STATUS
    start_button.config(state=kwargs.get("button_status", tk.NORMAL))
    THREAD_STATUS = kwargs.get("thread_status", False)
    app.update_idletasks()


def scrape_brownbook():
    global THREAD_STATUS

    start_button.config(state=tk.DISABLED)
    keywords = keyword_entry.get()
    locations = location_entry.get()
    proxy = True

    if not (keywords and locations):
        messagebox.showinfo("Missing Info", "Keyword or location field is missing")
        print_ui_logs("Keyword or location field is missing")
        clean_actions()
        return

    keywords = [quote(i.strip()) for i in keywords.split(",,")]
    locations = [quote(i.strip()) for i in locations.split(",,")]

    if len(keywords) != len(locations):
        messagebox.showinfo("Incomplete Info", "keyword and location should have the same length")
        print_ui_logs("keyword and location should have the same length")
        clean_actions()
        return

    proxies = None
    try:
        if proxy:
            proxies = get_proxy()
            print_ui_logs("Checking live proxies.")
            app.update_idletasks()
            next(proxies)
    except AttributeError:
        messagebox.showinfo("Proxy Error", "No Live proxy found, Press ok to scrape without proxy.")
        print_ui_logs("No Live proxy found, please use new proxies and try again")
        proxy = False
        # clean_actions()
        # return
    except ValueError:
        messagebox.showerror("Proxy Error", "Proxy csv file not found.")
        print_ui_logs("Proxy csv file not found.")
        logger.error("Proxy csv file not found.")
        clean_actions()
        return

    # create entry point for scraping to start
    total_records = 0
    for keyword, location in zip(keywords, locations):
        url = BASE_URL.format(location=location, keyword=keyword, page=1)
        total_count = get_total_count(url)
        total_records += total_count
        logger.debug(f"Found {total_count}")

    logger.debug(f"total records to scrape {total_records}")
    print_ui_logs(f"Total records to scrape {total_records}")

    # progress_bar["maximum"] = total_records
    app.update_idletasks()

    # start the scraping.
    for keyword, location in zip(keywords, locations):
        if not THREAD_STATUS:
            log_status.set("Scraper stopped..")
            clean_actions()
            return

        logger.debug(f"getting business ids for {unquote(keyword)}")

        print_ui_logs(f"getting business ids for {unquote(keyword)}")
        app.update_idletasks()

        page = 1
        business_ids_to_scrape = []
        failed_requests = 0
        while True:
            if not THREAD_STATUS:
                log_status.set("Scraper stopped..")
                clean_actions()
                return

            url = BASE_URL.format(location=location, keyword=keyword, page=page)
            page += 1

            try:
                if proxy:
                    response = request_page(url, proxy=proxies)
                else:
                    response = request_page(url)
            except Exception as e:
                logger.error("exception occurred.." + str(e))
                print_ui_logs(f"exception occurred.. {e}")
                app.update_idletasks()
                if failed_requests > 3:
                    logger.error("max retries reached..")
                    print_ui_logs(f"max retries reached.. {url}")
                    break
                failed_requests += 1
                continue

            if not response.ok:
                logger.error("Received an error" + str(response.status_code))
                print_ui_logs(f"Received bad response from server.. {response.status_code}")
                app.update_idletasks()
                if failed_requests > 3:
                    logger.error(f"Error, received bad response {response.status_code}")
                    print_ui_logs(f"Error, received bad response {response.status_code}")
                    break
                failed_requests += 1
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            if not is_next_page(soup):
                logger.error("Next Page not found..")
                print_ui_logs(f"Reached to last page for {unquote(keyword)} keyword")
                break

            business_ids_to_scrape.extend(parse_business_ids(soup))
            current_status.set(f"Scraping master page: {page}/{total_records / 30:.0f} pages")
            app.update_idletasks()

        print_ui_logs(f"Data Scraping started for {unquote(keyword)}")
        current_status.set("")
        app.update_idletasks()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_business_data, business_id, keyword)
                       for business_id in business_ids_to_scrape]

            master_data = []
            for future in as_completed(futures):

                if not THREAD_STATUS:
                    log_status.set("Stopping scraper..")
                    break

                result = future.result()
                if not result:
                    logger.debug("No data")
                    continue
                master_data.append(result)
                # progress_bar["value"] = len(master_data)
                current_status.set(f"Scrapped {len(master_data)}/{total_records} records..")
                app.update_idletasks()

    logger.debug(len(master_data))
    if master_data:
        try:
            csv_filepath = write_to_csv(master_data)
            messagebox.showinfo("Success", "Data scrapping is completed..")
            print_ui_logs(f"Data Scraping completed and saved to {csv_filepath}")
            logger.info(f"Data Scraping completed and saved to {csv_filepath}")
        except Exception as e:
            logger.error("Error writing to csv file " + str(e))
            messagebox.showerror("CSV Write Error", "Error while writing to csv file!")
            print_ui_logs(f"Error writing to csv file {e}")
    else:
        print_ui_logs(f"No data.")
        messagebox.showerror("No Data", "Unable to scrape data.")

    # progress_bar["value"] = 0
    # progress_bar["maximum"] = 100
    print_ui_logs(f"Scraping process complete")
    clean_actions()


def action_file_button(upload=False):
    source = os.path.join(WRK_DIR, OUTPUT_FILENAME)
    destination = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("Csv files", "*.csv"), ("All files", "*.*")],
    )

    if not destination:
        return

    success_message = ("Download Successful", f"File Downloaded to: {destination}")
    failed_message = ("Download Failed", f"File does not exists")

    if upload:
        # source, destination = destination, source
        success_message = ("Upload Successful", f"File Uploaded to: {destination}")
        failed_message = ("Upload Failed", f"File does not exists")

    if os.path.isfile(source):
        # Open the CSV file using the default application
        shutil.copy(source, destination)
        messagebox.showinfo(*success_message)
    else:
        messagebox.showwarning(*failed_message)


def edit_proxy():
    popup = tk.Toplevel()
    popup.title("Proxy Settings")
    popup.iconphoto(False, tk.PhotoImage(file=os.path.join(WRK_DIR, "fevicon.png")))

    proxy_filepath = os.path.join(WRK_DIR, PROXY_FILENAME)
    if not os.path.exists(proxy_filepath):
        with open(proxy_filepath, "w") as f:
            f.write("")

    # Add a Text widget for multi-line text entry
    text_entry = tk.Text(popup, height=20, width=50)
    text_entry.pack(padx=10, pady=10)

    with open(proxy_filepath, "r", encoding="utf-8") as fp:
        default_proxies = fp.read()
    text_entry.insert("1.0", default_proxies)

    # Function to handle save button click
    def save_text():
        # Retrieve text from text_entry; you can process and save the text here
        input_text = text_entry.get("1.0", tk.END)
        rows = input_text.split("\n")

        # validation
        for row in rows:

            if not row:
                continue

            cols = row.split(":")
            if len(cols) < 2 or len(cols) > 4:
                messagebox.showerror("Incorrect Config", "Some fields were invalid. Make sure you follow"
                                                         " the format: <ip>:<port>:<username>:<password>")
                return

        popup.destroy()
        with open(proxy_filepath, "w", encoding="utf-8") as fp:
            fp.write(input_text)
        messagebox.showinfo("Success", "Proxy Settings Saved!")

    # Add a save button to the popup
    save_button = tk.Button(popup, text="Save", command=save_text, width=15, height=2, bg='#039700', fg='white',
                            font=("Arial", 10))
    save_button.pack(padx=10, pady=10, side=tk.RIGHT)

    # Function to copy selected text to the clipboard
    def copy(event):
        popup.clipboard_clear()
        text = text_entry.get("sel.first", "sel.last")
        popup.clipboard_append(text)

    # Function to paste text from the clipboard
    def paste(event):
        try:
            text = popup.clipboard_get()
            text_entry.insert("insert", text)
        except:
            pass

    # Bind copy and paste functions to keyboard shortcuts
    text_entry.bind("<Control-c>", copy)
    text_entry.bind("<Control-v>", paste)


def scrape_brownbook_thread():
    global THREAD_STATUS
    thread = Thread(target=scrape_brownbook, args=(), daemon=True)
    thread.start()
    THREAD_STATUS = True


class EntryWithPlaceholder(tk.Entry):
    def __init__(self, master=None, placeholder="PLACEHOLDER", color='grey', font=("Times New Roman", 12)):
        super().__init__(master)

        self.placeholder = placeholder
        self.placeholder_color = color
        self.font = font
        self.default_fg_color = self['fg']

        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)

        self.put_placeholder()

    def put_placeholder(self):
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color
        self['font'] = self.font

    def foc_in(self, *args):
        if self['fg'] == self.placeholder_color:
            self.delete('0', 'end')
            self['fg'] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()


def stop_scraper():
    global THREAD_STATUS
    THREAD_STATUS = False


if __name__ == "__main__":
    app = tk.Tk()
    app.title("Business Leads Scraper v1.0")
    app.iconphoto(False, tk.PhotoImage(file=os.path.join(WRK_DIR, "fevicon.png")))
    app.geometry('750x450')

    # style
    style = ttk.Style()
    style.configure("TLabel", font=("Arial", 12))
    style.configure("TButton", font=("Arial", 12), width=15)
    style.configure("TCheckbutton", font=("Arial", 12))

    proxy_frame = tk.Frame(app)
    proxy_frame.pack(padx=10, pady=10, fill="x")
    tk.Button(proxy_frame, text="PROXY SETTINGS", command=edit_proxy,
              width=20, bg='#424242', fg='white', font=("Arial", 10)).pack(padx=5, side=tk.RIGHT)

    keyword_frame = ttk.Frame(app)
    keyword_frame.pack(padx=10, pady=10, fill="x")
    keyword_entry = EntryWithPlaceholder(keyword_frame, placeholder="Keywords", font=TEXT_FONTS)
    keyword_entry.pack(side=tk.RIGHT, expand=True, fill="x", padx=10)

    location_frame = ttk.Frame(app)
    location_frame.pack(padx=10, pady=10, fill="x")
    location_entry = EntryWithPlaceholder(location_frame, placeholder="Locations", font=TEXT_FONTS)
    location_entry.pack(side=tk.RIGHT, expand=True, fill="x", padx=10, pady=5)

    # use_proxy = tk.BooleanVar(value=False)
    # checkbox = tk.Checkbutton(app, text="Use Proxy", variable=use_proxy, font=('Arial', 12))
    # checkbox.pack()
    button_frame = tk.Frame(app)
    button_frame.pack(padx=10, pady=10, fill="x")

    # save as button
    tk.Button(button_frame, text="SAVE FILE AS", command=action_file_button,
              width=15, height=2, bg='#0F52BA', fg='white', font=("Arial", 10)).pack(padx=5, side=tk.LEFT)

    # Stop button
    tk.Button(button_frame, text="STOP", command=stop_scraper, width=15, height=2, bg='#CB0000', fg='white',
              font=("Arial", 10)).pack(padx=5, side=tk.RIGHT)

    # Start button
    start_button = tk.Button(button_frame, text="START", command=scrape_brownbook_thread, width=15, height=2,
                             bg='#039700', fg='white', font=("Arial", 10))
    start_button.pack(padx=5, side=tk.RIGHT)

    main_frame = tk.Frame(app, bg='black', height=200, padx=10, pady=10)
    main_frame.pack_propagate(False)  # This prevents the frame from resizing to fit its contents
    main_frame.pack(padx=20, pady=10, fill=tk.X, expand=True)

    # # Create a label with white text against the black background
    # label = tk.Label(main_frame, text="Progress", bg='black', fg='white')
    # label.pack()  # You can also use pack(side=tk.TOP) if needed

    current_status = tk.StringVar()
    current_status.set("Scrapped 0/0 records..")
    task_label = tk.Label(main_frame, textvariable=current_status, bg='black', fg='white')
    task_label.pack(padx=10, pady=10)
    #
    # progress_bar = ttk.Progressbar(main_frame, orient='horizontal', length=200, mode='determinate', bg='black', fg='white')
    # progress_bar.pack()  # You could configure the progress bar further if needed

    #
    # progress_frame = ttk.Frame(app)
    # progress_frame.pack(padx=10, pady=10, fill="x")
    # progress_label = ttk.Label(progress_frame, text="Download Progress")
    # progress_label.pack(side=tk.LEFT)
    # progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL, length=300, maximum=100)
    # progress_bar.pack(padx=10, pady=10, side=tk.BOTTOM, fill="x")

    log_status = tk.StringVar()
    log_field = tk.Entry(main_frame, textvariable=log_status, bg='black', fg='white')
    log_field.pack(expand=True, fill="both", padx=10, pady=10)

    app.mainloop()

# nuitka --standalone --disable-console --windows-icon-from-ico=fevicon.png --enable-plugin=tk-inter main.py
