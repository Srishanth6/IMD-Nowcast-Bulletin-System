import cv2
import glob
import os

# Find latest radar image
files = glob.glob("radar_download/radar_images/*.png")

if not files:
    print("No radar images found!")
    exit()

latest_image = max(files, key=os.path.getmtime)

print("Using:", latest_image)

image = cv2.imread(latest_image)

if image is None:
    print("Failed to read image!")
    exit()

# Show image size
print("Image shape:", image.shape)

# Display image
cv2.imshow("Radar Image", image)

print("Press any key after checking the image...")
cv2.waitKey(0)
cv2.destroyAllWindows()