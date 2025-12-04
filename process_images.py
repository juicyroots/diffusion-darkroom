import os
import json
import sys
import re
import http.server
import socketserver
import webbrowser
import shutil
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Action name mapping for better display
ACTION_NAME_MAP = {
    'metadata_fetch_start': 'Metadata Processing',
    'metadata_fetch_complete': 'Metadata Loaded',
    'metadata_background_start': 'Metadata Processing',
    'page_size_change': 'Page Size Change',
    'size_change': 'Image Size Change',
    'favorites_filter': 'Favorites Filter',
    'model_filter': 'Model Filter',
    'model_filter_result': 'Model Filter',
    'reload_complete': 'Images Folders Re-Scanned and Loaded',
    'filter_applied': 'Filter Applied',
    'sort': 'Sort',
    'page_change': 'Page Change',
}

def format_timestamp():
    """Format timestamp as Month/Day/Year HH:MM:SS AM/PM"""
    now = datetime.now()
    date_str = now.strftime('%m.%d.%Y')
    time_str = now.strftime('%I:%M:%S %p')
    return f"{date_str} {time_str}"

def format_action_name(action):
    """Convert action name to Title Case with proper mapping"""
    # Check if we have a mapped name
    if action in ACTION_NAME_MAP:
        return ACTION_NAME_MAP[action]
    # Otherwise convert to Title Case
    return action.replace('_', ' ').title()

def format_log_message(action, details):
    """Format log message with proper spacing and symbols"""
    action_name = format_action_name(action)
    details_str = ' 🢒 '.join(f"{k.replace('_', ' ').title()} = {v}" for k, v in details.items()) if details else ''
    if details_str:
        return f"{format_timestamp()} UI: {action_name} 🢒 {details_str}"
    else:
        return f"{format_timestamp()} UI: {action_name}"

# Custom handler to support file moving and image rescanning
class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def handle_one_request(self):
        """Override to gracefully handle connection errors"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError) as e:
            # These are common, non-critical errors when clients disconnect
            # Log them but don't crash the server
            error_code = getattr(e, 'winerror', getattr(e, 'errno', None))
            if error_code in (10053, 10054, 32, 104):  # Connection aborted/reset errors
                print(f"{format_timestamp()} INFO: Client disconnected during request (normal behavior)", file=sys.stderr)
            else:
                print(f"{format_timestamp()} WARNING: Connection error: {type(e).__name__} - {str(e)}", file=sys.stderr)
        except Exception as e:
            # Log unexpected errors but don't crash
            print(f"{format_timestamp()} ERROR: Unexpected error in request handler: {type(e).__name__} - {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
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
                print(f"{format_timestamp()} Images Folders Re-Scanned and Loaded: {len(image_files)} images", file=sys.stderr)
            except Exception as e:
                error_msg = f'Failed to rescan images: {str(e)}'
                print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                    pass  # Client disconnected
        else:
            # Default behavior for other GET requests (serve files)
            try:
                return super().do_GET()
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError) as e:
                # Client disconnected while serving file - this is normal
                error_code = getattr(e, 'winerror', getattr(e, 'errno', None))
                if error_code in (10053, 10054, 32, 104):
                    # Silently handle common connection errors
                    pass
                else:
                    print(f"{format_timestamp()} WARNING: Connection error serving file '{self.path}': {type(e).__name__}", file=sys.stderr)
            except Exception as e:
                print(f"{format_timestamp()} ERROR: Error serving file '{self.path}': {type(e).__name__} - {str(e)}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    self.send_error(500, f"Internal server error: {str(e)}")
                except:
                    pass  # Connection may already be closed
    
    def do_POST(self):
        if self.path == '/log-action':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                action = data.get('action', 'unknown')
                details = data.get('details', {})
                
                # Format and print the log message
                log_message = format_log_message(action, details)
                print(log_message, file=sys.stderr)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode())
            except Exception as e:
                print(f"{format_timestamp()} ERROR: Failed to process log action: {type(e).__name__} - {str(e)}", file=sys.stderr)
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': str(e)}).encode())
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                    pass  # Client disconnected
        elif self.path == '/move-file':
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
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(403)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    return
                
                # Check if source file exists
                if not os.path.exists(old_abs):
                    error_msg = f'Source file not found: {old_abs}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(404)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    return
                
                # Create destination directory if it doesn't exist
                new_dir = os.path.dirname(new_abs)
                if not os.path.exists(new_dir):
                    try:
                        os.makedirs(new_dir)
                        print(f"{format_timestamp()} INFO: Created directory: {new_dir}", file=sys.stderr)
                    except Exception as e:
                        error_msg = f'Failed to create directory {new_dir}: {str(e)}'
                        print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                        try:
                            self.send_response(500)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': error_msg}).encode())
                        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                            pass
                        return
                
                # Move the file
                try:
                    shutil.move(old_abs, new_abs)
                    print(f"{format_timestamp()} INFO: Successfully moved file: {os.path.basename(old_abs)} -> {os.path.basename(new_abs)}", file=sys.stderr)
                    try:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': True, 'message': 'File moved successfully'}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                except Exception as e:
                    error_msg = f'Failed to move file: {str(e)}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    
            except Exception as e:
                error_msg = f'Server error: {str(e)}'
                print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                    pass
        elif self.path == '/delete-file':
            try:
                # Read the request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                file_path = data.get('filePath', '')
                
                if not file_path:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Missing filePath'}).encode())
                    return
                
                # Get the current working directory (where the server is running)
                script_dir = os.getcwd()
                
                # Normalize paths - handle both forward and backslashes
                file_path = file_path.replace('\\', '/')
                
                # Build absolute path
                file_abs = os.path.abspath(os.path.join(script_dir, file_path))
                
                # Normalize the path to handle any .. or . components
                file_abs = os.path.normpath(file_abs)
                
                # Ensure path is within the script directory (security check)
                script_dir_abs = os.path.abspath(script_dir)
                if not file_abs.startswith(script_dir_abs):
                    error_msg = f'Path outside allowed directory. Script dir: {script_dir_abs}, File: {file_abs}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(403)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    return
                
                # Check if file exists
                if not os.path.exists(file_abs):
                    error_msg = f'File not found: {file_abs}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(404)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    return
                
                # Delete the file
                try:
                    os.remove(file_abs)
                    print(f"{format_timestamp()} INFO: Successfully deleted file: {os.path.basename(file_abs)}", file=sys.stderr)
                    try:
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': True, 'message': 'File deleted successfully'}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                except Exception as e:
                    error_msg = f'Failed to delete file: {str(e)}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(500)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    
            except Exception as e:
                error_msg = f'Server error: {str(e)}'
                print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                try:
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': error_msg}).encode())
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                    pass
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default HTTP request logging for cleaner output
        # We handle our own logging with timestamps
        pass
    
    def log_error(self, format, *args):
        # Override to format errors with timestamp
        message = format % args
        print(f"{format_timestamp()} ERROR: {message}", file=sys.stderr)

# Find available port starting from 8000
def find_available_port(start_port=8000, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        try:
            with socketserver.TCPServer(("", port), None):
                return port
        except OSError:
            continue
    raise Exception("Could not find an available port")

# Function to scan for images in current directory and all subdirectories
def scan_images():
    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    image_files = []
    
    # Exclude 'samples' folder (contains README images)
    excluded_folders = {'samples'}
    
    # Recursively walk through all directories
    for root, dirs, files in os.walk('.'):
        # Remove excluded folders from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in excluded_folders]
        
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in image_exts:
                # Skip darkroom.png in the root directory
                if root == '.' and f.lower() == 'darkroom.png':
                    continue
                
                # Build relative path
                if root == '.':
                    image_files.append(f)
                else:
                    # Remove leading './' from the path
                    rel_path = os.path.join(root, f)[2:]
                    # Use forward slashes for consistency
                    image_files.append(rel_path.replace('\\', '/'))
    
    return image_files

# Startup message
print(f"{format_timestamp()} Diffusion Darkroom Starting...", file=sys.stderr)

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

print(f"{format_timestamp()} Successfully injected {len(image_files)} images into {html_file}", file=sys.stderr)

# Find available port
port = find_available_port()
print(f"{format_timestamp()} Starting Web Server on Port {port}", file=sys.stderr)

# Change to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Create server with custom handler
Handler = CustomHTTPRequestHandler
httpd = socketserver.TCPServer(("", port), Handler)

# Open browser
url = f"http://localhost:{port}/darkroom.html"
print(f"{format_timestamp()} Launching Darkroom: Opening {url}", file=sys.stderr)
webbrowser.open(url)

# Server ready message
print(f"{format_timestamp()} Server Ready: Listening on port {port}", file=sys.stderr)
print(f"{format_timestamp()} INFO: Server is running. Press Ctrl+C to stop.", file=sys.stderr)

# Start server (this will block)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print(f"\n{format_timestamp()} INFO: Shutting down server...", file=sys.stderr)
    httpd.shutdown()
    print(f"{format_timestamp()} Server stopped.", file=sys.stderr)
except Exception as e:
    print(f"{format_timestamp()} ERROR: Server error: {type(e).__name__} - {str(e)}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    httpd.shutdown()
