import os
import time
import hashlib
import requests
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

SAVE_FOLDER = "radar_download/radar_images"

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
        # DOWNLOAD IMAGE WITH CACHE BUSTER
        # ----------------------------------------------------

        image_response = session.get(
            image_url,
            params={
                "_": cache_buster
            },
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Referer": URL,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            },
            timeout=30
        )


        print(
            "Image status:",
            image_response.status_code
        )


        if image_response.status_code != 200:

            print(
                "❌ Failed to download radar image."
            )

            return


        # ----------------------------------------------------
        # Get image data
        # ----------------------------------------------------

        image_data = (
            image_response.content
        )


        if not image_data:

            print(
                "❌ Empty image received."
            )

            return


        # ----------------------------------------------------
        # Check content type
        # ----------------------------------------------------

        content_type = (
            image_response.headers.get(
                "Content-Type",
                ""
            )
        )


        print(
            "Content type:",
            content_type
        )


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

            return


        # ----------------------------------------------------
        # Save latest radar image
        # ----------------------------------------------------

        with open(
            LATEST_FILE,
            "wb"
        ) as f:

            f.write(image_data)


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


    except requests.exceptions.RequestException as e:

        print(
            "❌ Network error:",
            e
        )


    except Exception as e:

        print(
            "❌ Error:",
            e
        )


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