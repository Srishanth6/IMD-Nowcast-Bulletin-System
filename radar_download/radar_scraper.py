import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from PIL import Image
from io import BytesIO

URL = "https://mausam.imd.gov.in/hyderabad/index_radar.php?id=Hyderabad"

SAVE_FOLDER = "radar_images"
os.makedirs(SAVE_FOLDER, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0"
}

response = requests.get(URL, headers=headers)

if response.status_code == 200:

    soup = BeautifulSoup(response.text, "html.parser")
    images = soup.find_all("img")

    radar_count = 1

    for img in images:

        src = img.get("src")

        if not src:
            continue

        img_url = urljoin(URL, src)

        try:
            image = requests.get(img_url, headers=headers)

            pil_image = Image.open(BytesIO(image.content))
            width, height = pil_image.size

            # Ignore small images/icons
            if width != 880 or height !=720:
                continue

            filename = os.path.join(
                SAVE_FOLDER,
                f"radar_{radar_count}.png"
            )

            with open(filename, "wb") as file:
                file.write(image.content)

            print(f"Radar Image {radar_count} Saved ({width}x{height})")

            radar_count += 1

        except Exception:
            continue

else:
    print("Website cannot be accessed.")