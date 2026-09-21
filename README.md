# IMD Nowcast Bulletin System

Automated generation of a Telangana IMD nowcast bulletin by combining the latest Hyderabad radar image with the Telangana district warning map and saving the result as a DOCX document.

## Project Overview

The project downloads current IMD source data, prepares the radar and warning-map images, integrates them into a single bulletin image, and generates the final Word document:

1. Download the latest radar image.
2. Download and extract the Telangana district warning map.
3. Convert the warning map when an inspection or alternate rendering is required.
4. Integrate the radar image and warning map into `final_bulletin.png`.
5. Generate the IMD Nowcast Bulletin document.
6. Save the final bulletin as `IMD_Nowcast_Bulletin.docx`.

All commands below are intended to be run from the repository root.

## Features

- Downloads the Hyderabad IMD `MAX (Z)` radar product into `radar_download/radar_images/latest_radar.png`.
- Downloads the Telangana warning-map page and extracts the `svgMap1` SVG.
- Renders the warning map to `latest_warning_map.png` using headless Google Chrome.
- Stores the downloaded warning map as `latest_warning_map.svg`.
- Combines the radar image and warning map into `final_bulletin.png`.
- Reads bulletin metadata from `imd_response.html`.
- Generates `IMD_Nowcast_Bulletin.docx` with the integrated bulletin image and metadata.

## Project Structure

```text
.
├── radar_download/
│   ├── radar_scraper.py                         # Required: radar downloader and scheduler
│   └── radar_images/
│       └── latest_radar.png                     # Generated radar image
├── download_warning_map.py                      # Required: download and render warning map
├── inspect_imd.py                               # Required: save IMD response metadata source
├── integrate_bulletin.py                        # Required: combine radar and warning map
├── generate_bulletin.py                         # Required: create the DOCX bulletin
├── extract_warning_map.py                       # Optional inspection/debugging SVG renderer
├── convert_warning_map.py                       # Optional inspection/debugging SVG renderer
├── image_processor.py                            # Optional radar-image inspection utility
├── server_integration                             # Project notes for server integration work
├── imd_response.html                             # Generated IMD response used for metadata
├── latest_warning_map.svg                        # Generated extracted warning map
├── latest_warning_map.png                        # Generated rendered warning map
├── final_bulletin.png                            # Generated integrated bulletin image
├── IMD_Nowcast_Bulletin.docx                    # Generated final bulletin document
└── test_warning_map.png                          # Generated optional warning-map test image
```

### File categories

- **Required production files:** `radar_download/radar_scraper.py`, `inspect_imd.py`, `download_warning_map.py`, `integrate_bulletin.py`, and `generate_bulletin.py`.
- **Optional inspection/debugging files:** `extract_warning_map.py`, `convert_warning_map.py`, and `image_processor.py`. They are not required for the normal production workflow.
- **Generated output files:** `radar_download/radar_images/latest_radar.png`, `imd_response.html`, `latest_warning_map.svg`, `latest_warning_map.png`, `final_bulletin.png`, `IMD_Nowcast_Bulletin.docx`, and `test_warning_map.png`.

## Requirements

- Python with the packages imported by the repository scripts:
  - `requests`
  - `beautifulsoup4`
  - `cairosvg`
  - `opencv-python`
  - `Pillow`
  - `python-docx`
- Google Chrome installed and discoverable by `download_warning_map.py`.
- Network access to the IMD radar page and Telangana warning-map endpoint.
- A graphical environment if you run `image_processor.py`, because it opens a window with OpenCV.

## Installation

1. Clone or download this repository.
2. Open a terminal in the repository root.
3. Install the packages imported by the repository scripts:

```text
py -m pip install requests beautifulsoup4 cairosvg opencv-python pillow python-docx
```

4. Confirm that Google Chrome is installed. `download_warning_map.py` checks the `chrome` command and the standard Windows Chrome installation paths.

## How to Run

Run the required production steps in this order:

```text
py inspect_imd.py
```

```text
py download_warning_map.py
```

In a second terminal, or after stopping the scheduler when the current radar image has been downloaded:

```text
py radar_download/radar_scraper.py
```

The radar scraper is a continuous scheduler. It downloads `latest_radar.png`, then waits for the next scheduled time. Stop it with `Ctrl+C` after the required radar image is available, or leave it running for scheduled updates.

Then integrate the images and generate the DOCX:

```text
py integrate_bulletin.py
```

```text
py generate_bulletin.py
```

## Complete Workflow

### 1. Download the IMD metadata response

Run the existing `inspect_imd.py` script:

```text
py inspect_imd.py
```

This creates `imd_response.html`. The file is used by `integrate_bulletin.py` and is required by `generate_bulletin.py`.

### 2. Download the latest radar image

Run the existing radar scraper:

```text
py radar_download/radar_scraper.py
```

The script checks the Hyderabad radar page for the `MAX (Z)` product and saves the latest image to:

```text
radar_download/radar_images/latest_radar.png
```

Because the script contains an infinite scheduling loop, stop it with `Ctrl+C` once the desired image has been saved if continuous downloading is not needed.

### 3. Download and extract the Telangana warning map

Run:

```text
py download_warning_map.py
```

The script downloads the warning-map page, extracts the SVG element with ID `svgMap1`, writes `latest_warning_map.svg`, and renders `latest_warning_map.png` through headless Google Chrome.

### 4. Convert or inspect the warning map when required

The normal production downloader already creates `latest_warning_map.png`. If you need to test SVG rendering separately, either existing inspection script can be run:

```text
py extract_warning_map.py
```

or:

```text
py convert_warning_map.py
```

Both scripts read `latest_warning_map.svg` and create `test_warning_map.png`. These scripts are optional and are not required before integration when `download_warning_map.py` has completed successfully.

### 5. Integrate the radar image and warning map

Run:

```text
py integrate_bulletin.py
```

The script reads `radar_download/radar_images/latest_radar.png` and `latest_warning_map.png`, then creates the combined bulletin image:

```text
final_bulletin.png
```

### 6. Generate the final DOCX bulletin

Run:

```text
py generate_bulletin.py
```

The script reads `final_bulletin.png` and metadata from `imd_response.html`, then saves:

```text
IMD_Nowcast_Bulletin.docx
```

## Output

The final production document is:

```text
IMD_Nowcast_Bulletin.docx
```

Intermediate generated files are:

- `radar_download/radar_images/latest_radar.png`
- `imd_response.html`
- `latest_warning_map.svg`
- `latest_warning_map.png`
- `final_bulletin.png`

The optional warning-map inspection scripts generate:

- `test_warning_map.png`

The repository currently includes sample or previously generated versions of these output files. Running the workflow updates the files in place where the scripts write them.

## Troubleshooting

### `Radar image not found`

Run `py radar_download/radar_scraper.py` from the repository root and confirm that `radar_download/radar_images/latest_radar.png` exists before running `py integrate_bulletin.py`.

### The radar scraper does not exit

This is expected. `radar_download/radar_scraper.py` contains a continuous loop that waits for the next scheduled download. Press `Ctrl+C` after the current radar image has been saved if you do not want it to continue running.

### `Google Chrome was not found`

Install Google Chrome or make the `chrome` executable available on `PATH`. The warning-map downloader checks the `chrome` command and the standard Windows installation locations.

### Warning-map rendering fails

Confirm that `latest_warning_map.svg` was created by `py download_warning_map.py`. You can test the SVG renderer with `py extract_warning_map.py` or `py convert_warning_map.py`; both commands require that `latest_warning_map.svg` already exists.

### `Warning map not found`

Run `py download_warning_map.py` and confirm that `latest_warning_map.png` exists in the repository root before running `py integrate_bulletin.py`.

### `IMD metadata file not found`

Run:

```text
py inspect_imd.py
```

This creates the required `imd_response.html` file.

### `Integrated bulletin image not found`

Run:

```text
py integrate_bulletin.py
```

before running `py generate_bulletin.py`.

### A dependency import fails

Install the packages listed in [Requirements](#requirements) using the installation command. The package names correspond to the imports used by the repository scripts.
