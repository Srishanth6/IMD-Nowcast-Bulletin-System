import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests


URL = "http://117.203.102.123:8088/tlng/wx/dist_nowcast.php"
ROOT = Path(__file__).resolve().parent
SVG_PATH = ROOT / "latest_warning_map.svg"
PNG_PATH = ROOT / "latest_warning_map.png"


def find_chrome():
    candidates = [
        shutil.which("chrome"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("Google Chrome was not found")


def extract_svg(html):
    match = re.search(
        r"<svg\b(?=[^>]*\bid\s*=\s*['\"]svgMap1['\"])[^>]*>.*?</svg>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise RuntimeError("svgMap1 was not found in the IMD response")
    return match.group(0)


def render_svg(svg):
    with tempfile.TemporaryDirectory(prefix="imd-warning-map-") as directory:
        directory_path = Path(directory)
        html_path = directory_path / "map.html"
        profile_path = directory_path / "chrome-profile"
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>html,body{margin:0;width:650px;height:750px;overflow:hidden}</style>"
            f"</head><body>{svg}</body></html>"
        )
        html_path.write_text(html, encoding="utf-8")

        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--run-all-compositor-stages-before-draw",
            "--window-size=650,750",
            f"--user-data-dir={profile_path}",
            f"--screenshot={PNG_PATH}",
            f"file:///{html_path.as_posix()}",
        ]
        subprocess.run(command, check=True, timeout=60, capture_output=True)


def main():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    svg = extract_svg(response.text)
    SVG_PATH.write_text(svg, encoding="utf-8")
    render_svg(svg)
    print(f"Saved {SVG_PATH.name} and {PNG_PATH.name}")


if __name__ == "__main__":
    main()