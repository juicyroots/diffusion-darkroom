import os
import json
import sys
import http.server
import socketserver
import webbrowser
import shutil
from urllib.parse import urlparse, parse_qs

# Custom handler to support file moving and image rescanning
class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/rescan-images':
            try:
                # Rescan images
                image_files = scan_images()
                
                # Send response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'images': image_files, 'count': len(image_files)}).encode())
                print(f"Rescanned and returned {len(image_files)} images", file=sys.stderr)
            except Exception as e:
                error_msg = f'Failed to rescan images: {str(e)}'
                print(f"ERROR: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': error_msg}).encode())
        else:
            # Default behavior for other GET requests (serve files)
            return super().do_GET()
    
    def do_POST(self):
        if self.path == '/move-file':
            try:
                # Read the request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                old_path = data.get('oldPath', '')
                new_path = data.get('newPath', '')
                
                if not old_path or not new_path:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Missing oldPath or newPath'}).encode())
                    return
                
                # Get the current working directory (where the server is running)
                # This should be the gallery directory
                script_dir = os.getcwd()
                
                # Normalize paths - handle both forward and backslashes
                old_path = old_path.replace('\\', '/')
                new_path = new_path.replace('\\', '/')
                
                # Build absolute paths
                old_abs = os.path.abspath(os.path.join(script_dir, old_path))
                new_abs = os.path.abspath(os.path.join(script_dir, new_path))
                
                # Normalize the paths to handle any .. or . components
                old_abs = os.path.normpath(old_abs)
                new_abs = os.path.normpath(new_abs)
                
                # Ensure paths are within the script directory (security check)
                script_dir_abs = os.path.abspath(script_dir)
                if not old_abs.startswith(script_dir_abs) or not new_abs.startswith(script_dir_abs):
                    error_msg = f'Path outside allowed directory. Script dir: {script_dir_abs}, Old: {old_abs}, New: {new_abs}'
                    print(f"ERROR: {error_msg}", file=sys.stderr)
                    self.send_response(403)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                    return
                
                # Check if source file exists
                if not os.path.exists(old_abs):
                    error_msg = f'Source file not found: {old_abs}'
                    print(f"ERROR: {error_msg}", file=sys.stderr)
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                    return
                
                # Create destination directory if it doesn't exist
                new_dir = os.path.dirname(new_abs)
                if not os.path.exists(new_dir):
                    try:
                        os.makedirs(new_dir)
                        print(f"Created directory: {new_dir}", file=sys.stderr)
                    except Exception as e:
                        error_msg = f'Failed to create directory {new_dir}: {str(e)}'
                        print(f"ERROR: {error_msg}", file=sys.stderr)
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                        return
                
                # Move the file
                try:
                    shutil.move(old_abs, new_abs)
                    print(f"Successfully moved: {old_abs} -> {new_abs}", file=sys.stderr)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': True, 'message': 'File moved successfully'}).encode())
                except Exception as e:
                    error_msg = f'Failed to move file: {str(e)}'
                    print(f"ERROR: {error_msg}", file=sys.stderr)
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                    
            except Exception as e:
                error_msg = f'Server error: {str(e)}'
                print(f"ERROR: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': error_msg}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging for cleaner output
        pass

# Find available port starting from 8000
def find_available_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socketserver.TCPServer(("", port), None):
                return port
        except OSError:
            continue
    raise Exception("Could not find an available port")

# Function to scan for images in current directory and subdirectories
def scan_images():
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    image_files = []
    
    # First, check for images in the current directory
    for f in os.listdir('.'):
        if os.path.isfile(f):
            ext = os.path.splitext(f)[1].lower()
            if ext in image_exts and f.lower() != 'darkroom.png':
                image_files.append(f)
    
    # Then, check for images in subdirectories
    for folder in os.listdir('.'):
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                ext = os.path.splitext(f)[1].lower()
                if ext in image_exts:
                    image_files.append(f"{folder}/{f}")
    
    return image_files

# Get the image list
image_files = scan_images()

# Read the HTML template
html_file = 'darkroom.html'
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

# Create server with custom handler
Handler = CustomHTTPRequestHandler
httpd = socketserver.TCPServer(("", port), Handler)

# Open browser
url = f"http://localhost:{port}/darkroom.html"
print(f"Opening {url}")
webbrowser.open(url)

# Start server (this will block)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down server...")
    httpd.shutdown()
