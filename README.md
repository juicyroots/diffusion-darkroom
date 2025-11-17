# Diffusion Darkroom Gallery

I got tired of other web-based image viewers, or opening PNGs in other apps to get metadata and parameter details, so I created this app.

## Description

A standalone image gallery viewer for AI-generated images. Automatically scans for images and provides a feature-rich viewing experience with full metadata access.

## Major Features

### Loading Screen
- Real-time percentage display while images load
- Gallery visible in background during loading

### Zoom & Pan
- Click-and-hold to zoom in lightbox
- Scroll wheel zoom (relative to mouse position)
- Pan when zoomed by clicking and dragging
- Click to unzoom

### Navigation
- Left/right arrow buttons in lightbox
- Keyboard arrow keys for navigation
- Click image to open in lightbox

### Scrolling
- Click-and-hold to scroll through gallery
- Drag up/down to navigate

### Right-Click Parameter Details
- View full metadata table with AI generation parameters
- Copy any metadata value with one click
- Shows Model, Sampler, Prompt, CFG Scale, Seed, dimensions, etc.

### Image Information
- Filename, model, sampler, and dimensions displayed on each image
- Metadata automatically extracted from PNG files

### Masonry Layout
- Images load in columns to maintain the masonry grid layout
- Row-based loading would break the nice visual layout

### Action Buttons
- Copy Prompt: Copies AI prompt to clipboard
- Download: Downloads the image
- Open: Opens in new browser tab

### Search & Filter
- Real-time search by filename or model name
- Image count display

### Sorting
- Sort by filename or date
- Ascending/descending toggle

## Installation

1. Place `gallery.html`, `inject_images.py`, and `launch.bat` in your image folder
2. Run `launch.bat` (Windows only)

The script scans for images, injects the list into HTML, starts a web server, and opens the gallery.

**Note:** `launch.bat` is Windows-specific. On other operating systems, run `inject_images.py` directly:
```bash
python inject_images.py
```

## Requirements

- Windows to run the .bat files, easily modified for another platform
- Python 3.x (only needed for initial image injection and meta-data extraction)
- Modern web browser

## Standalone Operation

After the initial image injection, the `gallery.html` file is completely standalone and can be opened directly in a browser. However, metadata extraction (right-click parameters) requires a web server due to browser security restrictions. The `inject_images.py` script handles this automatically by starting a local server.

You can run multiple instances in different folders simultaneously - each uses its own port (8000, 8001, etc.).

## Supported Formats

PNG, JPG/JPEG, GIF, WebP
