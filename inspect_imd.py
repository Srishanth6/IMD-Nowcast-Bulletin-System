import requests

URL = "http://117.203.102.123:8088/tlng/wx/dist_nowcast.php"

print("Connecting to IMD server...")

response = requests.get(URL, timeout=15)

print("Status:", response.status_code)
print("Received:", len(response.text), "characters")

with open("imd_response.html", "w", encoding="utf-8") as file:
    file.write(response.text)

print("Saved: imd_response.html")