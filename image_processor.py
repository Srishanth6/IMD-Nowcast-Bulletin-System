import cv2
import numpy as np

# Read radar image
import os
import glob

files = glob.glob("radar_download/radar_images/*.png")
latest_image = max(files, key=os.path.getmtime)

print("Using:", latest_image)

image = cv2.imread(latest_image)

if image is None:
    print("Image not found!")
    exit()

# ----------------------------
# Crop only the radar region
# ----------------------------

# Format: image[y1:y2, x1:x2]
radar = image[80:700, 20:660]

# Display cropped radar
cv2.imshow("Cropped Radar", radar)

# Convert to HSV
hsv = cv2.cvtColor(radar, cv2.COLOR_BGR2HSV)

# Blue
blue_mask = cv2.inRange(hsv, (100,100,50), (140,255,255))

# Green
green_mask = cv2.inRange(hsv, (40,50,50), (80,255,255))

# Yellow
yellow_mask = cv2.inRange(hsv, (20,100,100), (35,255,255))

# Orange
orange_mask = cv2.inRange(hsv, (10,100,100), (20,255,255))

# Red
red_mask1 = cv2.inRange(hsv, (0,100,100), (10,255,255))
red_mask2 = cv2.inRange(hsv, (170,100,100), (180,255,255))
red_mask = red_mask1 + red_mask2

print("Blue   :", cv2.countNonZero(blue_mask))
print("Green  :", cv2.countNonZero(green_mask))
print("Yellow :", cv2.countNonZero(yellow_mask))
print("Orange :", cv2.countNonZero(orange_mask))
print("Red    :", cv2.countNonZero(red_mask))

cv2.imshow("Blue", blue_mask)
cv2.imshow("Green", green_mask)
cv2.imshow("Yellow", yellow_mask)
cv2.imshow("Orange", orange_mask)
cv2.imshow("Red", red_mask)

cv2.waitKey(0)
cv2.destroyAllWindows()
# Create circular mask
mask = np.zeros(radar.shape[:2], dtype=np.uint8)

center = (320, 310)   # Approximate center of radar
radius = 300          # Approximate radar radius

cv2.circle(mask, center, radius, 255, -1)

# Apply mask
radar = cv2.bitwise_and(radar, radar, mask=mask)

cv2.imshow("Radar Circle", radar)
