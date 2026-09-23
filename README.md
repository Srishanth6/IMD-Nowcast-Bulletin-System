# IMD Nowcast Bulletin System

An automated system for generating a Telangana IMD Nowcast Bulletin by integrating the latest Hyderabad IMD radar image with the Telangana district warning map and generating the final bulletin as both an image and a DOCX document.

## Project Overview

The IMD Nowcast Bulletin System automates the collection, processing, integration, and generation of weather nowcast bulletin data.

The system retrieves the latest available IMD radar product and Telangana district warning map, processes the required images, combines them into a single bulletin layout, and generates the final bulletin document.

The overall workflow is:

1. Retrieve the latest IMD metadata/source response.
2. Download the latest Hyderabad IMD `MAX (Z)` radar image.
3. Download and extract the Telangana district warning map.
4. Render the warning map into a usable image format.
5. Integrate the radar image and warning map into a single bulletin image.
6. Generate the final IMD Nowcast Bulletin as a DOCX document.

## Objective

The primary objective of this project is to automate the preparation of an IMD-style Telangana nowcast bulletin by integrating current weather data sources into a standardized bulletin format.

The system is designed to reduce repetitive manual processing and provide a structured workflow for:

- Radar data acquisition
- Warning-map acquisition
- Image processing
- Bulletin integration
- Document generation

## System Workflow

```text
                    IMD Data Sources
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
      Hyderabad Radar          Telangana Warning Map
       MAX (Z) Product               Source
             │                         │
             ▼                         ▼
      Latest Radar Image       Warning Map Extraction
             │                         │
             └────────────┬────────────┘
                          ▼
                 Image Integration
                          │
                          ▼
                 final_bulletin.png
                          │
                          ▼
                 DOCX Generation
                          │
                          ▼
             IMD_Nowcast_Bulletin.docx
Features
Downloads the latest Hyderabad IMD MAX (Z) radar product.
Stores the latest radar image as latest_radar.png.
Downloads the Telangana district warning-map source.
Extracts the required svgMap1 SVG element.
Renders the warning map into PNG format using headless Google Chrome.
Stores the extracted warning map as an SVG file.
Combines the radar image and warning map into a single bulletin image.
Reads required bulletin metadata from the IMD response.
Generates the final IMD Nowcast Bulletin in DOCX format.
Provides a modular workflow for radar acquisition, warning-map processing, integration, and document generation.
Technologies Used
Programming Language
Python
Python Libraries
requests
beautifulsoup4
cairosvg
opencv-python
Pillow
python-docx
Other Tools
Google Chrome
Git
GitHub
HTML
SVG
Microsoft Word or another DOCX-compatible application

PROJECT STRUCTURE
.
├── assets/
│
├── radar_download/
│   ├── radar_scraper.py
│   └── radar_images/
│       └── latest_radar.png
│
├── server_integration/
│
├── download_warning_map.py
├── inspect_imd.py
├── integrate_bulletin.py
├── generate_bulletin.py
│
├── imd_response.html
├── latest_warning_map.svg
├── latest_warning_map.png
├── final_bulletin.png
├── IMD_Nowcast_Bulletin.docx
│
├── .gitattributes
├── .gitignore
└── README.md
File Description
File / Directory
Description
assets/
Project assets used by the system
radar_download/
Radar data acquisition module
radar_scraper.py
Retrieves the latest Hyderabad IMD radar image
latest_radar.png
Latest downloaded radar image
server_integration/
Documentation and work related to server-side integration
download_warning_map.py
Downloads and processes the Telangana warning map
inspect_imd.py
Retrieves and stores the IMD response/metadata
integrate_bulletin.py
Combines the radar image and warning map
generate_bulletin.py
Generates the final DOCX bulletin
imd_response.html
Stored IMD response used during bulletin processing
latest_warning_map.svg
Extracted Telangana warning-map SVG
latest_warning_map.png
Rendered warning-map image
final_bulletin.png
Final integrated bulletin image
IMD_Nowcast_Bulletin.docx
Final generated bulletin document
README.md
Project documentation
Requirements
Before running the project, make sure the following are installed.
Software
Python 3.x
Google Chrome
Git
Microsoft Word or another DOCX-compatible application
Python Packages
Install the required packages using:
py -m pip install requests beautifulsoup4 cairosvg opencv-python pillow python-docx
Installation
1. Clone the Repository
git clone https://github.com/Srishanth6/IMD-Nowcast-Bulletin-System.git
Move into the project directory:
cd IMD-Nowcast-Bulletin-System
2. Install Python Dependencies
py -m pip install requests beautifulsoup4 cairosvg opencv-python pillow python-docx
3. Verify Google Chrome
The warning-map processing workflow uses Google Chrome for rendering the extracted SVG.
Make sure Google Chrome is installed and accessible on the system.
How to Run
The complete production workflow consists of four major stages:
1. Retrieve IMD metadata
2. Download radar and warning-map data
3. Integrate the images
4. Generate the DOCX bulletin
Step 1 — Retrieve IMD Metadata
Run:
py inspect_imd.py
This creates:
imd_response.html
The stored response is used during the bulletin processing workflow.
Step 2 — Download the Latest Radar Image
Run:
py radar_download/radar_scraper.py
The radar scraper checks the Hyderabad IMD radar source and identifies the required:
MAX (Z)
radar product.
The latest radar image is stored at:
radar_download/radar_images/latest_radar.png
The radar scraper contains a continuous scheduling mechanism.
If only one radar image is required, stop the scheduler after the required image has been successfully downloaded:
Ctrl + C
Step 3 — Download the Telangana Warning Map
Run:
py download_warning_map.py
The script:
Retrieves the Telangana warning-map source.
Identifies the required SVG map.
Extracts the svgMap1 element.
Saves the extracted SVG.
Renders the SVG into PNG format.
The resulting files are:
latest_warning_map.svg
latest_warning_map.png
Step 4 — Integrate the Bulletin Images
Run:
py integrate_bulletin.py
The integration script reads:
radar_download/radar_images/latest_radar.png
and:
latest_warning_map.png
The two components are processed and integrated into the final bulletin layout.
The resulting image is:
final_bulletin.png
Step 5 — Generate the Final DOCX Bulletin
Run:
py generate_bulletin.py
The document-generation script uses:
final_bulletin.png
along with the required metadata and generates:
IMD_Nowcast_Bulletin.docx
Complete Execution Sequence
Run the following commands from the repository root:
py inspect_imd.py
py download_warning_map.py
py radar_download/radar_scraper.py
After the latest radar image has been downloaded, stop the radar scheduler if continuous operation is not required:
Ctrl + C
Then run:
py integrate_bulletin.py
Finally:
py generate_bulletin.py
Generated Outputs
Radar Output
radar_download/radar_images/latest_radar.png
Contains the latest downloaded Hyderabad IMD radar image used by the bulletin.
Warning Map Output
latest_warning_map.svg
Contains the extracted Telangana district warning map in SVG format.
latest_warning_map.png
Contains the rendered warning map used during image integration.
Integrated Bulletin
final_bulletin.png
Contains the combined radar and Telangana warning-map bulletin layout.
Final Document
IMD_Nowcast_Bulletin.docx
Contains the generated IMD Nowcast Bulletin in Word document format.
Output Workflow
Latest Radar
     +
Telangana Warning Map
     │
     ▼
Image Processing & Integration
     │
     ▼
final_bulletin.png
     │
     ▼
Bulletin Metadata
     │
     ▼
IMD_Nowcast_Bulletin.docx
Team Contributions
The project was developed as a modular team system, with different components handled by different members.
Radar Data Acquisition
Developed the radar data extraction workflow.
Identified the required Hyderabad IMD MAX (Z) radar product.
Automated retrieval of the latest radar image.
Stored the processed radar image for bulletin integration.
Warning Map Integration
Developed the workflow for obtaining the Telangana district warning map.
Extracted the required SVG map.
Converted and rendered the warning map into PNG format for integration.
Bulletin Integration
Integrated the radar image and warning map.
Prepared the final bulletin image layout.
Generated the combined final_bulletin.png.
Document Generation
Developed the DOCX generation workflow.
Integrated the final bulletin image with the required metadata.
Generated the final IMD_Nowcast_Bulletin.docx.
Server Integration
Prepared the workflow and documentation for server-side integration.
Organized the project components for combining externally retrieved data with the bulletin-generation pipeline.
Error Handling and Troubleshooting
Radar Image Not Found
Run:
py radar_download/radar_scraper.py
Confirm that the following file exists:
radar_download/radar_images/latest_radar.png
Then run:
py integrate_bulletin.py
Radar Scraper Does Not Exit
This is expected behavior.
The radar scraper contains a continuous scheduling loop.
If continuous downloading is not required, press:
Ctrl + C
after the required radar image has been downloaded.
Google Chrome Not Found
If the warning-map downloader cannot locate Chrome:
Confirm that Google Chrome is installed.
Ensure the Chrome executable is available at a standard installation path.
If required, add Chrome to the system PATH.
Run:
py download_warning_map.py
again.
Warning Map Not Found
Run:
py download_warning_map.py
Confirm that:
latest_warning_map.svg
and:
latest_warning_map.png
exist in the repository root.
Then run:
py integrate_bulletin.py
IMD Metadata File Not Found
Run:
py inspect_imd.py
This creates:
imd_response.html
Then continue with the remaining workflow.
Integrated Bulletin Image Not Found
Run:
py integrate_bulletin.py
Confirm that:
final_bulletin.png
has been created.
Then run:
py generate_bulletin.py
Python Dependency Error
If an import error occurs, install the required packages:
py -m pip install requests beautifulsoup4 cairosvg opencv-python pillow python-docx
Project Advantages
The system provides a structured approach to bulletin preparation by:
Automating radar image retrieval.
Automating warning-map acquisition.
Reducing repetitive manual image processing.
Integrating multiple weather-data sources into a single output.
Generating a standardized bulletin image.
Generating a final DOCX document automatically.
Providing a modular architecture that can be extended for additional data sources.
Future Scope
The system can be further extended with:
Complete end-to-end automated bulletin generation at fixed time intervals.
Direct integration with the production server-side warning-map source.
Automated timestamp and data-validity verification.
Improved retry mechanisms for temporary network failures.
Automated validation of radar and warning-map availability.
Server-side deployment for unattended bulletin generation.
Support for additional IMD radar products.
Support for additional regional warning maps.
Automated archival of previously generated bulletins.
Web-based monitoring of bulletin generation status.
Project Status
The core implementation currently supports:
✓ IMD metadata retrieval
✓ Hyderabad radar image retrieval
✓ Telangana warning-map retrieval
✓ Warning-map rendering
✓ Radar and warning-map integration
✓ Final bulletin image generation
✓ DOCX bulletin generation
The generated outputs include:
final_bulletin.png
IMD_Nowcast_Bulletin.docx
Conclusion
The IMD Nowcast Bulletin System provides an automated workflow for collecting weather-related source data, processing radar and warning-map images, integrating the information into a standardized bulletin layout, and generating the final bulletin document.
The modular design allows individual components such as radar acquisition, warning-map processing, image integration, and document generation to be developed and maintained independently while working together as a complete bulletin-generation pipeline.

**That's the complete one.** Copy the entire block → replace everything inside `README.md` → **Commit changes**. ✅
