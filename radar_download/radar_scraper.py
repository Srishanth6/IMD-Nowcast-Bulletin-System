import os
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta

# IMD Radar Page
URL = "https://mausam.imd.gov.in/hyderabad/index_radar.php?id=Hyderabad"

# Save folder
SAVE_FOLDER = "radar_download/radar_images"
os.makedirs(SAVE_FOLDER, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Fixed schedule (Hour, Minute)
DOWNLOAD_TIMES = [
    (1, 5),
    (4, 5),
    (7, 5),
    (10, 5),
    (13, 5),
    (16, 5),
    (19, 5),
    (22, 5)
]

LAST_HASH = None


def download_latest_radar():
    global LAST_HASH

    print(f"\nChecking IMD website... {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}")

    try:
        response = requests.get(URL, headers=HEADERS, timeout=20)

        if response.status_code != 200:
            print("Failed to access IMD website.")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        for img in soup.find_all("img"):

            src = img.get("src")

            if not src:
                continue

            img_url = urljoin(URL, src)

            if "radar" not in img_url.lower():
                continue

            img_data = requests.get(img_url, headers=HEADERS, timeout=20)

            if img_data.status_code != 200:
                continue

            current_hash = hashlib.md5(img_data.content).hexdigest()

            if current_hash == LAST_HASH:
                print("No new radar image available.")
                return

            LAST_HASH = current_hash

            filename = os.path.join(
                SAVE_FOLDER,
                "latest_radar.png"
            )

            with open(filename, "wb") as f:
                f.write(img_data.content)

            print("✅ New radar image downloaded.")
            print("Saved as:", filename)
            return

        print("Radar image not found.")

    except Exception as e:
        print("Error:", e)


def wait_until_next_schedule():

    now = datetime.now()

    next_time = None

    for hour, minute in DOWNLOAD_TIMES:

        candidate = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        if candidate > now:
            next_time = candidate
            break

    if next_time is None:

        next_time = (now + timedelta(days=1)).replace(
            hour=DOWNLOAD_TIMES[0][0],
            minute=DOWNLOAD_TIMES[0][1],
            second=0,
            microsecond=0
        )

    wait_seconds = (next_time - now).total_seconds()

    print(f"\nNext download at: {next_time.strftime('%d-%m-%Y %H:%M:%S')}")
    print(f"Waiting {int(wait_seconds/60)} minutes...")

    time.sleep(wait_seconds)


print("=" * 50)
print(" IMD Radar Auto Downloader Started ")
print("=" * 50)

while True:
    download_latest_radar()
    wait_until_next_schedule()