import os
import sys
import time
import hashlib
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta


# ============================================================
# IMD RADAR PAGE
# ============================================================

URL = "https://mausam.imd.gov.in/hyderabad/index_radar.php?id=Hyderabad"


# ============================================================
# SAVE LOCATION
# ============================================================

SAVE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "radar_images")

os.makedirs(SAVE_FOLDER, exist_ok=True)

LATEST_FILE = os.path.join(
    SAVE_FOLDER,
    "latest_radar.png"
)


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Referer": URL,
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}


# ============================================================
# DOWNLOAD SCHEDULE
#
# Every 3 hours
# ============================================================

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


# ============================================================
# REQUEST SESSION
# ============================================================

session = requests.Session()

session.headers.update(HEADERS)


# ============================================================
# GET CURRENT FILE HASH
# ============================================================

def get_current_file_hash():

    if not os.path.exists(LATEST_FILE):
        return None

    try:

        with open(
            LATEST_FILE,
            "rb"
        ) as f:

            data = f.read()

        return hashlib.md5(data).hexdigest()

    except Exception:

        return None


# ============================================================
# CHECK WHETHER IMAGE IS MAX (Z)
# ============================================================

def is_max_z_image(img):

    # --------------------------------------------------------
    # Image attributes
    # --------------------------------------------------------

    alt = (
        img.get("alt") or ""
    ).lower()

    title = (
        img.get("title") or ""
    ).lower()

    img_class = " ".join(
        img.get("class") or []
    ).lower()

    src = (
        img.get("src") or ""
    ).lower()


    # --------------------------------------------------------
    # Parent text
    # --------------------------------------------------------

    parent_text = ""

    if img.parent:

        parent_text = (
            img.parent.get_text(
                " ",
                strip=True
            ) or ""
        ).lower()


    # --------------------------------------------------------
    # Parent HTML
    # --------------------------------------------------------

    parent_html = ""

    try:

        if img.parent:

            parent_html = str(
                img.parent
            ).lower()

    except Exception:

        pass


    # --------------------------------------------------------
    # Combine all available information
    # --------------------------------------------------------

    combined_text = " ".join([
        alt,
        title,
        img_class,
        src,
        parent_text,
        parent_html
    ])


    # --------------------------------------------------------
    # MAX (Z) patterns
    # --------------------------------------------------------

    patterns = [
        "max (z)",
        "max(z)",
        "max z",
        "max_z",
        "max-z",
        "maxz"
    ]


    for pattern in patterns:

        if pattern in combined_text:

            return True


    return False


# ============================================================
# FIND MAX (Z) RADAR IMAGE
# ============================================================

def find_max_z_image(soup):

    images = soup.find_all("img")

    print(
        f"Found {len(images)} images on IMD page."
    )


    for img in images:

        if not img.get("src"):

            continue


        if is_max_z_image(img):

            print(
                "✅ MAX (Z) radar image identified."
            )

            return img


    return None


# ============================================================
# VALIDATE AND CONVERT RADAR BYTES
# ============================================================

RADAR_RETRIES = 4
RADAR_RETRY_DELAY_SECONDS = 2
MIN_RADAR_BYTES = 64

GIF_HEADERS = (b"GIF87a", b"GIF89a")
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff"


def previous_radar_is_valid():
    if not os.path.exists(LATEST_FILE):
        return False
    try:
        if os.path.getsize(LATEST_FILE) < MIN_RADAR_BYTES:
            return False
        from PIL import Image
        with Image.open(LATEST_FILE) as image:
            image.load()
            return image.size[0] >= 8 and image.size[1] >= 8
    except Exception:
        return False


def looks_like_image_bytes(data):
    if not data or len(data) < MIN_RADAR_BYTES:
        return False
    return data.startswith(GIF_HEADERS + (PNG_HEADER, JPEG_HEADER))


def radar_bytes_to_png(data):
    from io import BytesIO
    from PIL import Image, ImageFile

    ImageFile.LOAD_TRUNCATED_IMAGES = True
    with Image.open(BytesIO(data)) as image:
        image.load()
        if image.size[0] < 8 or image.size[1] < 8:
            raise ValueError("radar image is too small")
        if image.mode in ("P", "RGBA", "LA"):
            converted = image.convert("RGBA")
        else:
            converted = image.convert("RGB")
        output = BytesIO()
        converted.save(output, format="PNG")
        png_data = output.getvalue()
    if not png_data.startswith(PNG_HEADER):
        raise ValueError("PNG conversion did not produce a PNG file")
    return png_data


def fetch_max_z_image(image_url, attempt):
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": URL,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept": "image/gif,image/png,image/jpeg,image/*,*/*;q=0.8",
    }
    params = None
    if attempt > 1:
        params = {"_": str(int(time.time() * 1000))}
    return session.get(
        image_url,
        params=params,
        headers=headers,
        timeout=30,
    )


# ============================================================
# DOWNLOAD LATEST MAX (Z) RADAR
# ============================================================

def download_latest_radar():

    print("\n" + "=" * 60)

    print(
        "Checking IMD website...",
        datetime.now().strftime(
            "%d-%m-%Y %H:%M:%S"
        )
    )

    print("=" * 60)


    try:

        # ----------------------------------------------------
        # CACHE-BUSTING VALUE
        # ----------------------------------------------------

        cache_buster = str(
            int(time.time())
        )


        # ----------------------------------------------------
        # Open IMD radar page
        # ----------------------------------------------------

        response = session.get(
            URL,
            params={
                "_": cache_buster
            },
            timeout=30
        )


        print(
            "Website status:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                "❌ Failed to access IMD website."
            )

            return


        # ----------------------------------------------------
        # Parse HTML
        # ----------------------------------------------------

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # ----------------------------------------------------
        # Find MAX (Z)
        # ----------------------------------------------------

        max_z_image = find_max_z_image(
            soup
        )


        if max_z_image is None:

            print(
                "❌ MAX (Z) radar image not found."
            )

            return


        # ----------------------------------------------------
        # Get image source
        # ----------------------------------------------------

        src = max_z_image.get(
            "src"
        )


        image_url = urljoin(
            URL,
            src
        )


        print(
            "MAX (Z) image URL:"
        )

        print(
            image_url
        )


        # ----------------------------------------------------
        # DOWNLOAD IMAGE (exact URL first, then retries)
        # ----------------------------------------------------

        png_data = None
        validation_succeeded = False

        for attempt in range(1, RADAR_RETRIES + 1):
            print(f"Radar download attempt {attempt}/{RADAR_RETRIES}")
            image_response = fetch_max_z_image(image_url, attempt)
            content_type = image_response.headers.get("Content-Type", "")
            image_data = image_response.content or b""
            print("HTTP status:", image_response.status_code)
            print("response byte count:", len(image_data))
            print("content type:", content_type or "(missing)")

            if image_response.status_code != 200:
                print("Image validation succeeded: no")
                time.sleep(RADAR_RETRY_DELAY_SECONDS)
                continue

            if not looks_like_image_bytes(image_data):
                print("❌ Empty or invalid radar bytes received.")
                print("Image validation succeeded: no")
                time.sleep(RADAR_RETRY_DELAY_SECONDS)
                continue

            try:
                png_data = radar_bytes_to_png(image_data)
                validation_succeeded = True
                print("Image validation succeeded: yes")
                break
            except Exception as error:
                print(f"❌ Radar bytes could not be opened as an image: {error}")
                print("Image validation succeeded: no")
                png_data = None
                time.sleep(RADAR_RETRY_DELAY_SECONDS)

        if not validation_succeeded or not png_data:
            if previous_radar_is_valid():
                print("⚠️ New MAX (Z) download was empty or invalid.")
                print("Preserving previous valid radar image.")
                print("final saved file path:", LATEST_FILE)
                return LATEST_FILE
            print("❌ No valid radar image could be downloaded.")
            return

        image_data = png_data


        # ----------------------------------------------------
        # Calculate new image hash
        # ----------------------------------------------------

        new_hash = hashlib.md5(
            image_data
        ).hexdigest()


        # ----------------------------------------------------
        # Calculate existing image hash
        # ----------------------------------------------------

        old_hash = (
            get_current_file_hash()
        )


        # ----------------------------------------------------
        # Check if image is unchanged
        # ----------------------------------------------------

        if old_hash == new_hash:

            print(
                "⚠️ Same radar image already saved."
            )

            print(
                "No update required."
            )

            print("final saved file path:", LATEST_FILE)

            return LATEST_FILE


        # ----------------------------------------------------
        # Save latest radar image as PNG (never write empty bytes)
        # ----------------------------------------------------

        if not image_data:
            print("❌ Refusing to save an empty radar file.")
            if previous_radar_is_valid():
                print("final saved file path:", LATEST_FILE)
                return LATEST_FILE
            return

        tmp_file = LATEST_FILE + ".tmp"
        with open(tmp_file, "wb") as f:
            f.write(image_data)
        os.replace(tmp_file, LATEST_FILE)


        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        print("\n" + "=" * 60)

        print(
            "✅ NEW MAX (Z) RADAR IMAGE DOWNLOADED"
        )

        print(
            "Saved as:",
            LATEST_FILE
        )

        print("final saved file path:", LATEST_FILE)

        print(
            "Image size:",
            len(image_data),
            "bytes"
        )

        print(
            "Downloaded:",
            datetime.now().strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        )

        print("=" * 60)

        return LATEST_FILE


    except requests.exceptions.RequestException as e:

        print(
            "❌ Network error:",
            e
        )
        if previous_radar_is_valid():
            print("Preserving previous valid radar image.")
            print("final saved file path:", LATEST_FILE)
            return LATEST_FILE


    except Exception as e:

        print(
            "❌ Error:",
            e
        )
        if previous_radar_is_valid():
            print("Preserving previous valid radar image.")
            print("final saved file path:", LATEST_FILE)
            return LATEST_FILE


# ============================================================
# WAIT FOR NEXT SCHEDULE
# ============================================================

def wait_until_next_schedule():

    now = datetime.now()

    next_time = None


    # --------------------------------------------------------
    # Find next scheduled time
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # If today's schedule is finished,
    # schedule tomorrow
    # --------------------------------------------------------

    if next_time is None:

        next_time = (
            now + timedelta(days=1)
        ).replace(
            hour=DOWNLOAD_TIMES[0][0],
            minute=DOWNLOAD_TIMES[0][1],
            second=0,
            microsecond=0
        )


    # --------------------------------------------------------
    # Calculate waiting time
    # --------------------------------------------------------

    wait_seconds = (
        next_time - now
    ).total_seconds()


    print("\n" + "-" * 60)

    print(
        "Next download at:",
        next_time.strftime(
            "%d-%m-%Y %H:%M:%S"
        )
    )

    print(
        "Waiting:",
        int(wait_seconds / 60),
        "minutes..."
    )

    print("-" * 60)


    time.sleep(
        wait_seconds
    )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    print("=" * 60)

    print(
        " IMD RADAR AUTO DOWNLOADER "
    )

    print(
        " Product: MAX (Z)"
    )

    print(
        " Output: latest_radar.png"
    )

    print("=" * 60)


    # ============================================================
    # MAIN LOOP
    # ============================================================

    while True:

        download_latest_radar()

        wait_until_next_schedule()