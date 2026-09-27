import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests


URL = "http://117.203.102.123:8088/tlng/wx/dist_nowcast.php"
ROOT = Path(__file__).resolve().parent
SVG_PATH = ROOT / "latest_warning_map.svg"
PNG_PATH = ROOT / "latest_warning_map.png"


def _windows_path(path: Path) -> str:
    return os.fspath(Path(path).resolve())


def atomic_replace(source: Path, destination: Path) -> Path:
    """Replace destination without truncating it first (avoids Windows EINVAL/locks)."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for _attempt in range(3):
        try:
            os.replace(_windows_path(source), _windows_path(destination))
            return destination
        except OSError as error:
            last_error = error
            time.sleep(0.2)
    fallback = destination.with_name(f"{destination.stem}_latest{destination.suffix}")
    try:
        os.replace(_windows_path(source), _windows_path(fallback))
        print(
            f"WARNING: {destination.name} is locked or not replaceable; "
            f"saved as {fallback.name}"
        )
        return fallback
    except OSError as error:
        raise OSError(
            f"could not write {_windows_path(destination)}: {last_error or error}"
        ) from error


def write_bytes_atomic(destination: Path, data: bytes) -> Path:
    destination = Path(destination)
    tmp_path = destination.with_name(destination.name + ".tmp")
    tmp_path.write_bytes(data)
    return atomic_replace(tmp_path, destination)


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
        # IMD sometimes emits the map SVG with a blank id after PHP warnings.
        match = re.search(
            r"<svg\b[^>]*width=['\"]650['\"][^>]*height=['\"]750['\"][^>]*>.*?</svg>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if not match:
        raise RuntimeError("svgMap1 was not found in the IMD response")
    return match.group(0)


def render_svg(svg) -> Path:
    with tempfile.TemporaryDirectory(prefix="imd-warning-map-") as directory:
        directory_path = Path(directory)
        html_path = directory_path / "map.html"
        profile_path = directory_path / "chrome-profile"
        screenshot_tmp = ROOT / "latest_warning_map.tmp.png"
        html = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>html,body{margin:0;width:650px;height:750px;overflow:hidden}</style>"
            f"</head><body>{svg}</body></html>"
        )
        html_path.write_bytes(html.encode("utf-8"))

        command = [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--run-all-compositor-stages-before-draw",
            "--window-size=650,750",
            f"--user-data-dir={_windows_path(profile_path)}",
            f"--screenshot={_windows_path(screenshot_tmp)}",
            Path(html_path).resolve().as_uri(),
        ]
        subprocess.run(command, check=True, timeout=60, capture_output=True)
        if not screenshot_tmp.is_file():
            raise RuntimeError("Chrome did not write the warning-map PNG")
        return atomic_replace(screenshot_tmp, PNG_PATH)


def save_warning_map(html: str) -> Path:
    svg = extract_svg(html).replace("\x00", "")
    svg_saved = write_bytes_atomic(SVG_PATH, svg.encode("utf-8"))
    if svg_saved != SVG_PATH:
        print(f"WARNING: warning map SVG saved as {svg_saved.name}")
    png_saved = render_svg(svg)
    if not png_saved.is_file():
        raise RuntimeError("the latest warning map PNG was not saved")
    return png_saved


def main():
    response = requests.get(
        URL,
        timeout=30,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
    response.raise_for_status()
    save_warning_map(response.text)
    print(f"Saved {SVG_PATH.name} and {PNG_PATH.name}")


if __name__ == "__main__":
    main()