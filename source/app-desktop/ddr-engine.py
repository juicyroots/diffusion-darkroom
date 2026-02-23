import os
import json
import sys
import re
import argparse
import http.server
import socketserver
import webbrowser
import shutil
import threading
import time
import subprocess
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:
    tk = None
    filedialog = None

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
    """Format timestamp as Month/Day/Year HH:MMam/pm - """
    now = datetime.now()
    date_str = now.strftime('%m.%d.%Y')
    time_str = now.strftime('%I:%M%p').lower()
    return f"{date_str} {time_str} - "

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
    
    # Metadata actions use "DARKROOM:" prefix, others use "UI CHANGE:"
    is_metadata = action in ['metadata_fetch_start', 'metadata_fetch_complete', 'metadata_background_start', 'reload_complete']
    prefix = "DARKROOM: " if is_metadata else "UI CHANGE: "
    
    if details_str:
        return f"{format_timestamp()}{prefix}{action_name} 🢒 {details_str}"
    else:
        return f"{format_timestamp()}{prefix}{action_name}"


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = get_app_dir()
RUNTIME_CONFIG_PATH = os.path.join(APP_DIR, 'ddr-runtime.json')
CURRENT_BASE_DIR = None
WEB_TEMPLATE_PATH = None
APP_CONFIG = None

DEFAULT_APP_CONFIG = {
    "web": {
        "modelFilters": [
            {"label": "Flux", "containsText": "flux"},
            {"label": "Qwen", "containsText": "qwen"},
            {"label": "ZIT", "containsText": "z_image"},
            {"label": "Wan", "containsText": "wan"},
            {"label": "XL", "containsText": "xl"},
            {"label": "Pony", "containsText": "pony"},
        ],
        "imageSize": {
            "min": 300,
            "max": 1800,
            "default": 900,
            "step": 0.1,
        },
        "paging": {
            "options": [50, 100, 250, 500],
            "default": 100,
        },
        "zoom": {
            "default": 2.5,
        },
        "debugMode": False,
    },
    "desktop": {
        "title": "Diffusion Darkroom",
        "width": 1600,
        "height": 1000,
    },
}


def deep_merge_dict(base, override):
    if not isinstance(base, dict):
        return override
    if not isinstance(override, dict):
        return dict(base)
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def resolve_project_root():
    normalized = os.path.normpath(APP_DIR)
    parent = os.path.dirname(normalized)
    grandparent = os.path.dirname(parent)
    if os.path.basename(normalized) == 'app-desktop' and os.path.basename(parent) == 'source':
        return grandparent
    return normalized


def get_app_config_candidates():
    project_root = resolve_project_root()
    candidates = [
        os.path.join(project_root, 'config.json'),
        os.path.join(os.getcwd(), 'config.json'),
        os.path.join(APP_DIR, 'config.json'),
        os.path.join(os.path.dirname(APP_DIR), 'config.json'),
    ]
    # De-duplicate while preserving order.
    unique = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(os.path.abspath(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(candidate)
    return unique


def load_app_config():
    merged = json.loads(json.dumps(DEFAULT_APP_CONFIG))
    loaded_path = None
    for path in get_app_config_candidates():
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = deep_merge_dict(merged, data)
                loaded_path = path
                break
        except Exception as e:
            print(f"{format_timestamp()} ERROR: Failed to read config.json at {path}: {e}", file=sys.stderr)
    if loaded_path:
        print(f"{format_timestamp()}DARKROOM: Loaded app config from {loaded_path}", file=sys.stderr)
    else:
        print(f"{format_timestamp()} WARNING: config.json not found. Using built-in defaults.", file=sys.stderr)
    return merged


def resolve_web_template_path():
    candidates = [
        os.path.join(APP_DIR, 'app-web', 'ddr.html'),
        os.path.join(APP_DIR, 'web-app', 'ddr.html'),
        os.path.join(os.path.dirname(APP_DIR), 'app-web', 'ddr.html'),
        os.path.join(os.path.dirname(APP_DIR), 'web-app', 'ddr.html'),
        os.path.join(APP_DIR, 'ddr.html'),
        os.path.join(os.getcwd(), 'source', 'app-web', 'ddr.html'),
        os.path.join(os.getcwd(), 'web-app', 'ddr.html'),
        os.path.join(os.getcwd(), 'ddr.html'),
    ]
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.extend([
            os.path.join(meipass, 'app-web', 'ddr.html'),
            os.path.join(meipass, 'web-app', 'ddr.html'),
            os.path.join(meipass, 'ddr.html'),
        ])
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return os.path.join(APP_DIR, 'ddr.html')


WEB_TEMPLATE_PATH = resolve_web_template_path()
WEB_ASSET_DIR = os.path.dirname(WEB_TEMPLATE_PATH)
APP_CONFIG = load_app_config()


def load_runtime_config():
    if not os.path.exists(RUNTIME_CONFIG_PATH):
        return {}
    try:
        with open(RUNTIME_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_config(data):
    try:
        with open(RUNTIME_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"{format_timestamp()} ERROR: Failed to save runtime config: {e}", file=sys.stderr)


def get_active_base_dir():
    return CURRENT_BASE_DIR


def set_active_base_dir(path, persist=True):
    global CURRENT_BASE_DIR
    if not path:
        CURRENT_BASE_DIR = None
        if persist:
            cfg = load_runtime_config()
            cfg.pop('base_dir', None)
            save_runtime_config(cfg)
        return None

    normalized = os.path.abspath(path)
    if not os.path.isdir(normalized):
        raise ValueError(f"Selected folder does not exist: {normalized}")

    CURRENT_BASE_DIR = normalized
    if persist:
        cfg = load_runtime_config()
        cfg['base_dir'] = normalized
        save_runtime_config(cfg)
    return CURRENT_BASE_DIR


def pick_base_dir_dialog(initial_dir=None):
    if tk is not None and filedialog is not None:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            selected = filedialog.askdirectory(
                title='Select image root folder for Diffusion Darkroom',
                initialdir=initial_dir or APP_DIR,
                mustexist=True,
            )
        finally:
            root.destroy()
        return selected or None

    # Windows fallback when tkinter is unavailable (common in minimal Python builds).
    if os.name == 'nt':
        initial = (initial_dir or APP_DIR).replace("'", "''")
        ps_script = (
            "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$dlg.Description = 'Select image root folder for Diffusion Darkroom';"
            "$dlg.ShowNewFolderButton = $false;"
            f"$dlg.SelectedPath = '{initial}';"
            "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
            "  Write-Output $dlg.SelectedPath"
            "}"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
            selected = (result.stdout or "").strip()
            return selected or None
        except Exception as e:
            raise RuntimeError(f"Folder picker unavailable: {e}")

    raise RuntimeError("Folder picker unavailable on this runtime")


def is_path_within(base_dir, candidate_path):
    base = os.path.abspath(base_dir)
    candidate = os.path.abspath(candidate_path)
    try:
        return os.path.commonpath([base, candidate]) == base
    except Exception:
        return False

# Custom handler to support file moving and image rescanning
class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urlparse(path)
        request_path = unquote(parsed.path or '/')

        if request_path in ('/', '/ddr.html', '/darkroom.html'):
            return WEB_TEMPLATE_PATH

        relative_path = request_path.lstrip('/').replace('/', os.sep)

        # Serve static app assets from app folder if present.
        asset_candidates = [
            os.path.join(WEB_ASSET_DIR, relative_path),
            os.path.join(APP_DIR, relative_path),
            os.path.join(APP_DIR, 'app-web', relative_path),
            os.path.join(APP_DIR, 'web-app', relative_path),
        ]
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            asset_candidates.extend([
                os.path.join(meipass, relative_path),
                os.path.join(meipass, 'app-web', relative_path),
                os.path.join(meipass, 'web-app', relative_path),
            ])
        for candidate in asset_candidates:
            if os.path.exists(candidate):
                return os.path.normpath(candidate)

        base_dir = get_active_base_dir() or APP_DIR
        candidate = os.path.normpath(os.path.join(base_dir, relative_path))
        if not is_path_within(base_dir, candidate):
            return os.path.join(base_dir, '__invalid_path__')
        return candidate

    def handle_one_request(self):
        """Override to gracefully handle connection errors"""
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError) as e:
            # These are common, non-critical errors when clients disconnect
            # Log them but don't crash the server
            error_code = getattr(e, 'winerror', getattr(e, 'errno', None))
            if error_code in (10053, 10054, 32, 104):  # Connection aborted/reset errors
                print(f"{format_timestamp()} Client disconnected during request (normal behavior)", file=sys.stderr)
            else:
                print(f"{format_timestamp()} WARNING: Connection error: {type(e).__name__} - {str(e)}", file=sys.stderr)
        except Exception as e:
            # Log unexpected errors but don't crash
            print(f"{format_timestamp()} ERROR: Unexpected error in request handler: {type(e).__name__} - {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    def do_GET(self):
        # Parse path to handle query strings
        parsed_path = urlparse(self.path)
        path_without_query = parsed_path.path
        
        if path_without_query == '/app-config':
            try:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(json.dumps(APP_CONFIG).encode('utf-8'))
            except Exception as e:
                print(f"{format_timestamp()} ERROR: Failed to serve app config JSON: {e}", file=sys.stderr)
                self.send_response(500)
                self.end_headers()
        elif path_without_query == '/app-config.js':
            try:
                payload = "window.__DDR_APP_CONFIG__ = " + json.dumps(APP_CONFIG, ensure_ascii=False) + ";"
                self.send_response(200)
                self.send_header('Content-type', 'application/javascript; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(payload.encode('utf-8'))
            except Exception as e:
                print(f"{format_timestamp()} ERROR: Failed to serve app config script: {e}", file=sys.stderr)
                self.send_response(500)
                self.end_headers()
        elif path_without_query == '/rescan-images':
            try:
                # Rescan images
                image_files = scan_images()
                
                # Send response with cache-busting headers
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'images': image_files,
                    'count': len(image_files),
                    'baseFolder': get_active_base_dir()
                }).encode())
                print(f"{format_timestamp()}DARKROOM: Images Folders Re-Scanned and Loaded: {len(image_files)} images", file=sys.stderr)
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
        elif path_without_query == '/current-base-folder':
            try:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                base_dir = get_active_base_dir()
                self.wfile.write(json.dumps({
                    'baseFolder': base_dir,
                    'isSelected': bool(base_dir)
                }).encode())
            except Exception as e:
                print(f"{format_timestamp()} ERROR: Failed to get base folder: {e}", file=sys.stderr)
                self.send_response(500)
                self.end_headers()
        else:
            # Default behavior for other GET requests (serve files)
            try:
                # Handle HTML files with cache-busting headers
                if path_without_query.endswith('.html') or path_without_query in ('/darkroom.html', '/ddr.html', '/'):
                    file_path = WEB_TEMPLATE_PATH
                    
                    # Check if file exists before sending response
                    if not os.path.exists(file_path):
                        self.send_error(404, "File not found")
                        return
                    
                    # Send response with cache-busting headers
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                    self.end_headers()
                    
                    # Read and send the file
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                    return
                else:
                    # For other files, use parent class but we can't easily add headers
                    # The parent class will handle the response properly
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
        parsed_path = urlparse(self.path)
        path_without_query = parsed_path.path

        if path_without_query == '/log-action':
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
        elif path_without_query == '/move-file':
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
                
                # Resolve against selected image root folder.
                script_dir = get_active_base_dir() or APP_DIR
                
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
                        print(f"{format_timestamp()} Created directory: {new_dir}", file=sys.stderr)
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
                    
                    # Determine the type of operation for better log messages
                    old_basename = os.path.basename(old_abs)
                    new_basename = os.path.basename(new_abs)
                    new_path_str = new_abs.replace('\\', '/')
                    old_path_str = old_abs.replace('\\', '/')
                    
                    # Check if it's a favorite operation (moving TO Favorites folder)
                    is_favoriting = 'Favorites' in new_path_str and 'Favorites' not in old_path_str
                    
                    # Check if it's a rating operation (filename changes to include _0[1-5] pattern)
                    old_rating_match = re.search(r'_0([1-5])(\.[^.]+)$', old_basename)
                    new_rating_match = re.search(r'_0([1-5])(\.[^.]+)$', new_basename)
                    is_rating = (old_rating_match is not None) != (new_rating_match is not None) or (old_rating_match and new_rating_match and old_rating_match.group(1) != new_rating_match.group(1))
                    
                    if is_favoriting:
                        # Favorite operation - show simplified message (only when moving TO favorites)
                        print(f"{format_timestamp()}FILE: Image file favorited and moved to Favorites folder: {new_basename}", file=sys.stderr)
                    elif is_rating:
                        # Rating operation - extract rating and show message
                        if new_rating_match:
                            rating = int(new_rating_match.group(1))
                            print(f"{format_timestamp()}FILE: Image file set '{rating} Star{'s' if rating > 1 else ''}' and renamed to: {new_basename}", file=sys.stderr)
                        else:
                            # Rating removed
                            print(f"{format_timestamp()}FILE: Image file rating removed and renamed to: {new_basename}", file=sys.stderr)
                    else:
                        # Generic move operation (fallback)
                        print(f"{format_timestamp()} Successfully moved file: {old_basename} -> {new_basename}", file=sys.stderr)
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
        elif path_without_query == '/delete-file':
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
                
                # Resolve against selected image root folder.
                script_dir = get_active_base_dir() or APP_DIR
                
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
                    print(f"{format_timestamp()}FILE: Image file deleted: {os.path.basename(file_abs)}", file=sys.stderr)
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
        elif path_without_query == '/select-base-folder':
            try:
                content_length = int(self.headers.get('Content-Length', '0') or 0)
                post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
                data = json.loads(post_data.decode('utf-8') or '{}')
                requested_folder = (data.get('folder') or '').strip()

                selected_folder = None
                if requested_folder:
                    selected_folder = requested_folder
                else:
                    selected_folder = pick_base_dir_dialog(get_active_base_dir())

                if not selected_folder:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'selected': False, 'baseFolder': get_active_base_dir()}).encode())
                    return

                selected_folder = set_active_base_dir(selected_folder, persist=True)
                image_files = scan_images()
                print(f"{format_timestamp()}DARKROOM: Base folder selected: {selected_folder}", file=sys.stderr)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'selected': True,
                    'baseFolder': selected_folder,
                    'images': image_files,
                    'count': len(image_files)
                }).encode())
            except Exception as e:
                error_msg = f'Failed to select base folder: {str(e)}'
                print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': error_msg}).encode())
        elif path_without_query == '/update-embedded-list':
            try:
                # Read the request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                image_list = data.get('images', [])
                
                if not isinstance(image_list, list):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Missing or invalid images array'}).encode())
                    return
                
                # Update the source ddr template file.
                html_file = WEB_TEMPLATE_PATH
                
                if not os.path.exists(html_file):
                    error_msg = f'HTML file not found: {html_file}'
                    print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                    try:
                        self.send_response(404)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': error_msg}).encode())
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                        pass
                    return
                
                # Read the HTML file
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # Generate JavaScript array
                    js_array = json.dumps(image_list, indent=2)
                    replacement = f'const embeddedImageList = {js_array};'
                    
                    # Find and replace the embedded image list
                    pattern = r'const embeddedImageList = \[.*?\];'
                    match = re.search(pattern, html_content, re.DOTALL)
                    if match:
                        html_content = html_content[:match.start()] + replacement + html_content[match.end():]
                        
                        # Write the updated HTML
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        print(f"{format_timestamp()}DARKROOM: Updated embedded image list in {html_file} with {len(image_list)} images", file=sys.stderr)
                        
                        try:
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(json.dumps({'success': True, 'count': len(image_list)}).encode())
                        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                            pass
                    else:
                        error_msg = 'Could not find embeddedImageList in HTML file'
                        print(f"{format_timestamp()} ERROR: {error_msg}", file=sys.stderr)
                        try:
                            self.send_response(500)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': error_msg}).encode())
                        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                            pass
                except Exception as e:
                    error_msg = f'Failed to update HTML file: {str(e)}'
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
    base_dir = get_active_base_dir()
    if not base_dir:
        return []

    image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    image_files = []
    
    # Exclude 'samples' folder (contains README images)
    excluded_folders = {'samples'}
    
    # Recursively walk through all directories
    for root, dirs, files in os.walk(base_dir):
        # Remove excluded folders from dirs to prevent walking into them
        dirs[:] = [d for d in dirs if d not in excluded_folders]
        
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in image_exts:
                # Skip ddr.png in the root directory
                if os.path.abspath(root) == os.path.abspath(base_dir) and f.lower() == 'ddr.png':
                    continue
                
                rel_path = os.path.relpath(os.path.join(root, f), base_dir)
                image_files.append(rel_path.replace('\\', '/'))
    
    return image_files

def inject_embedded_image_list(html_file=None):
    html_file = html_file or WEB_TEMPLATE_PATH
    image_files = scan_images()
    if not os.path.exists(html_file):
        print(f"Error: {html_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    js_array = json.dumps(image_files, indent=2)
    placeholder = 'const embeddedImageList = []; // Will be replaced with actual list'
    replacement = f'const embeddedImageList = {js_array};'

    if placeholder in html_content:
        html_content = html_content.replace(placeholder, replacement)
    else:
        pattern = r'const embeddedImageList = \[.*?\];'
        match = re.search(pattern, html_content, re.DOTALL)
        if match:
            html_content = html_content[:match.start()] + replacement + html_content[match.end():]
        else:
            print(f"Error: Could not find embeddedImageList in {html_file}", file=sys.stderr)
            sys.exit(1)

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(
        f"{format_timestamp()}DARKROOM: Successfully injected {len(image_files)} images into {html_file}",
        file=sys.stderr,
    )
    return image_files


def create_server(port):
    return socketserver.TCPServer(("", port), CustomHTTPRequestHandler)


def start_server_thread(httpd):
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return thread


def stop_server(httpd):
    try:
        shutdown_thread = threading.Thread(target=httpd.shutdown, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=2)
    except Exception:
        pass
    try:
        httpd.server_close()
    except Exception:
        pass


def build_ddr_url(port):
    timestamp = int(time.time())
    return f"http://localhost:{port}/ddr.html?v={timestamp}"


def bootstrap(mode='web', host='localhost', port=None, base_dir=None):
    print(f"{format_timestamp()}DARKROOM: Starting...", file=sys.stderr)
    os.chdir(APP_DIR)

    configured_base_dir = load_runtime_config().get('base_dir')
    initial_base_dir = base_dir or configured_base_dir
    if initial_base_dir:
        try:
            set_active_base_dir(initial_base_dir, persist=True)
        except Exception as e:
            print(f"{format_timestamp()} WARNING: Could not set initial base folder: {e}", file=sys.stderr)
            set_active_base_dir(None, persist=False)
    else:
        set_active_base_dir(None, persist=False)
    if get_active_base_dir():
        print(f"{format_timestamp()}DARKROOM: Active image root folder: {get_active_base_dir()}", file=sys.stderr)
    else:
        print(f"{format_timestamp()}DARKROOM: No image root folder selected yet", file=sys.stderr)

    selected_port = int(port) if port else find_available_port()
    print(f"{format_timestamp()}DARKROOM: Starting Web Server on Port {selected_port}", file=sys.stderr)

    httpd = create_server(selected_port)
    url = build_ddr_url(selected_port).replace('localhost', host, 1)

    if mode == 'web':
        print(f"{format_timestamp()}DARKROOM: Opening {url}", file=sys.stderr)
        webbrowser.open(url)

    print(f"{format_timestamp()}DARKROOM: Server Ready: Listening on port {selected_port}", file=sys.stderr)
    return httpd, selected_port, url


def run_web_mode(port=None, base_dir=None):
    httpd = None
    try:
        httpd, selected_port, _ = bootstrap(mode='web', port=port, base_dir=base_dir)
        print(f"{format_timestamp()}DARKROOM: Server is running. Press Ctrl+C to stop.", file=sys.stderr)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{format_timestamp()}DARKROOM: Shutting down server...", file=sys.stderr)
    except Exception as e:
        print(f"{format_timestamp()} ERROR: Server error: {type(e).__name__} - {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
    finally:
        if httpd:
            stop_server(httpd)
            print(f"{format_timestamp()}DARKROOM: Server stopped.", file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser(description="Diffusion Darkroom server launcher")
    parser.add_argument(
        '--mode',
        choices=['web', 'desktop'],
        default='web',
        help='web: open browser automatically, desktop: server only (for PyWebView shell)',
    )
    parser.add_argument('--port', type=int, default=None, help='Optional fixed port')
    parser.add_argument('--base-dir', default=None, help='Optional runtime folder for scanning/serving')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.mode == 'desktop':
        # Desktop mode keeps this process as server-only; the desktop shell owns the window.
        httpd = None
        try:
            httpd, _, _ = bootstrap(mode='desktop', port=args.port, base_dir=args.base_dir)
            print(f"{format_timestamp()}DARKROOM: Desktop server running. Press Ctrl+C to stop.", file=sys.stderr)
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n{format_timestamp()}DARKROOM: Shutting down desktop server...", file=sys.stderr)
        finally:
            if httpd:
                stop_server(httpd)
    else:
        run_web_mode(port=args.port, base_dir=args.base_dir)
