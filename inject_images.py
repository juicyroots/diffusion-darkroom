import os
import json
import sys
import http.server
import socketserver
import webbrowser

# Find an available port starting from 8000
def find_available_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socketserver.TCPServer(("", port), None):
                return port
        except OSError:
            continue
    raise Exception("Could not find an available port")

# Get the image list
image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
image_files = []

# First, check for images in the current directory
for f in os.listdir('.'):
    if os.path.isfile(f):
        ext = os.path.splitext(f)[1].lower()
        if ext in image_exts and f.lower() != 'ddg.png':
            image_files.append(f)

# Then, check for images in subdirectories
for folder in os.listdir('.'):
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in image_exts:
                image_files.append(f"{folder}/{f}")

# Read the HTML template
html_file = 'gallery.html'
if not os.path.exists(html_file):
    print(f"Error: {html_file} not found", file=sys.stderr)
    sys.exit(1)

with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

# Generate JavaScript array
js_array = json.dumps(image_files, indent=2)

# Replace the embedded image list - handle both empty array and existing array
# Pattern 1: Empty array placeholder
placeholder1 = 'const embeddedImageList = []; // Will be replaced with actual list'
replacement = f'const embeddedImageList = {js_array};'

# Pattern 2: Existing array (match from "const embeddedImageList = [" to "];" across multiple lines)
import re

if placeholder1 in html_content:
    # Replace empty placeholder
    html_content = html_content.replace(placeholder1, replacement)
else:
    # Try to find and replace existing array (handles multi-line arrays)
    # Match from "const embeddedImageList = [" to the matching "];" (non-greedy, across newlines)
    pattern = r'const embeddedImageList = \[.*?\];'
    match = re.search(pattern, html_content, re.DOTALL)
    if match:
        html_content = html_content[:match.start()] + replacement + html_content[match.end():]
    else:
        print(f"Error: Could not find embeddedImageList in {html_file}", file=sys.stderr)
        sys.exit(1)

# Write the updated HTML
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Successfully injected {len(image_files)} images into {html_file}")

# Find available port
port = find_available_port()
print(f"Starting server on port {port}...")

# Change to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Create server
Handler = http.server.SimpleHTTPRequestHandler
httpd = socketserver.TCPServer(("", port), Handler)

# Open browser
url = f"http://localhost:{port}/gallery.html"
print(f"Opening {url}")
webbrowser.open(url)

# Start server (this will block)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down server...")
    httpd.shutdown()

