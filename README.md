# Diffusion Darkroom - Image Gallery - Metadata Viewer

A fast, feature-rich image gallery for AI-generated images with full metadata support.

## Description

A standalone web based image gallery viewer for AI-generated images. Automatically scans folders and sub-folders for images and provides a feature-rich viewing experience with full metadata access. Requires Python to be installed and available in your system PATH. 

## Gallery Features
- Masonry layout with intelligent loading, paging, and image recalculations
- Auto-hiding controls that appear when mouse moves near top or bottom edges, maximizing image viewing space

## Thumbnail Features
- **Hover to show info:** Filename, Model, Sampler/Scheduler, Dimensions
- **Hover to show buttons:** Copy Prompt, Download, Open Image in New Tab
- **Left-click thumbnail:** Opens image in lightbox (click again to close)
- **Right-click thumbnail:** View metadata table (click again to close)
- **Scroll:** Use mouse wheel or click-hold-drag to scroll through images

## Top Nav Bar
- **Thumbnail size control:** Adjust size (small, medium, large, huge)
- **Search bar:** Search by filename and prompt
- **Sort buttons:** Sort by filename or created date (click again to reverse ascending/descending)

## Bottom Nav Bar
- **Images per page selector:** Choose 50, 100, 250, or 500 images per page
- **Paging controls:** Navigate between pages with arrow buttons or page numbers
- **Loading indicator:** Shows progress while images load
- **Image count:** Displays total number of filtered images

## Lightbox Controls
- **Zoom:** Click-and-hold to zoom, move mouse to pan
- **Scroll zoom:** Mouse wheel zooms relative to cursor position
- **Navigation:** Left/right arrow buttons or keyboard arrow keys to navigate between images

## Diffusion Parameter Detail Table (Right Click)
- View full metadata table showing: Prompt, Model, Sampler, Schedule Type, Size, Steps, CFG Scale, LoRAs, etc.
- Copy any metadata parameter value with a single click

## Installation

1. Clone the repository and place `darkroom.html`, `process_images.py`, and `launch-darkroom.bat` in your image generation output folder.
2. Run `launch-darkroom.bat` (Windows only) or run `process_images.py` directly.

The script will:
- Search the current folder and all sub-folders for images
- Build a list of image files
- Inject the image list into the gallery HTML
- Start a local web server
- Open the gallery in your default browser 

**Note:** `launch-darkroom.bat` is Windows-specific. On other operating systems, run `process_images.py` directly:

```bash
python process_images.py
```

## Requirements

- **Windows:** Required to run the `.bat` files (easily modified for other platforms)
- **Python 3.x:** Required for initial image injection and metadata extraction

## Standalone Operation

After the initial image processing, the `darkroom.html` file is completely standalone and can be opened directly in a browser. However, metadata extraction (right-click parameters) requires a web server due to browser security restrictions. The `process_images.py` script handles this automatically by starting a local server.

You can run multiple instances in different folders simultaneously—each uses its own port (8000, 8001, etc.).

## Supported Formats

PNG, JPG/JPEG, GIF, WebP
