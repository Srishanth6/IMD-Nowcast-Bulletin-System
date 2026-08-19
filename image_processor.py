import cv2
import os


# ============================================================
# RADAR IMAGE LOCATION
# ============================================================

RADAR_IMAGE = "radar_download/radar_images/latest_radar.png"


# ============================================================
# CHECK WHETHER RADAR IMAGE EXISTS
# ============================================================

if not os.path.exists(RADAR_IMAGE):

    print("❌ Radar image not found:")
    print(RADAR_IMAGE)

    exit()


# ============================================================
# LOAD RADAR IMAGE
# ============================================================

print("Using:", RADAR_IMAGE)

image = cv2.imread(RADAR_IMAGE)


# ============================================================
# CHECK IMAGE
# ============================================================

if image is None:

    print("❌ Failed to read radar image.")

    exit()


# ============================================================
# SHOW IMAGE SIZE
# ============================================================

print(
    "Image shape:",
    image.shape
)


# ============================================================
# DISPLAY RADAR IMAGE
# ============================================================

cv2.imshow(
    "Radar Image",
    image
)


print(
    "Press any key after checking the image..."
)


cv2.waitKey(0)

cv2.destroyAllWindows()
