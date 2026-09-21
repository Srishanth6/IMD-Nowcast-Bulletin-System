# IMD-Nowcast-Bulletin-System
Automated District-Level Nowcast Bulletin Generation System 

## Download the live warning map

Run this from the repository root:

```text
py download_warning_map.py
```

The script fetches the IMD page, extracts `svgMap1` without rewriting its SVG
attributes, and uses installed Google Chrome in headless mode to render the
map. It writes `latest_warning_map.svg` and `latest_warning_map.png` (650x750).
Google Chrome and the Python `requests` package are required.
