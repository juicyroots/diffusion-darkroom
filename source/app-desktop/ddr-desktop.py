import argparse
import importlib.util
import json
import os
import sys

try:
    import webview
except Exception:
    print("ERROR: PyWebView is required for desktop mode. Install with: pip install pywebview", file=sys.stderr)
    raise

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_MEIPASS = getattr(sys, "_MEIPASS", "")
_ENGINE_CANDIDATES = [
    os.path.join(_BASE_DIR, "ddr-engine.py"),
    os.path.join(_BASE_DIR, "app-desktop", "ddr-engine.py"),
    os.path.join(_MEIPASS, "ddr-engine.py") if _MEIPASS else "",
    os.path.join(_MEIPASS, "app-desktop", "ddr-engine.py") if _MEIPASS else "",
]
ENGINE_PATH = next((p for p in _ENGINE_CANDIDATES if p and os.path.exists(p)), "")
if not ENGINE_PATH:
    raise RuntimeError("Unable to locate ddr-engine.py for desktop launcher")

ENGINE_SPEC = importlib.util.spec_from_file_location("ddr_engine_module", ENGINE_PATH)
if ENGINE_SPEC is None or ENGINE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load engine module from {ENGINE_PATH}")
ENGINE_MODULE = importlib.util.module_from_spec(ENGINE_SPEC)
ENGINE_SPEC.loader.exec_module(ENGINE_MODULE)

bootstrap = ENGINE_MODULE.bootstrap
start_server_thread = ENGINE_MODULE.start_server_thread
stop_server = ENGINE_MODULE.stop_server
format_timestamp = ENGINE_MODULE.format_timestamp
APP_CONFIG = getattr(ENGINE_MODULE, "APP_CONFIG", {}) if hasattr(ENGINE_MODULE, "APP_CONFIG") else {}

WINDOW_STATE_FILENAME = "window-state.json"


def get_desktop_config_value(key, fallback):
    desktop_cfg = APP_CONFIG.get("desktop") if isinstance(APP_CONFIG, dict) else None
    if isinstance(desktop_cfg, dict) and key in desktop_cfg:
        return desktop_cfg[key]
    return fallback


def get_desktop_config_int(key, fallback):
    value = get_desktop_config_value(key, fallback)
    try:
        return int(value)
    except Exception:
        return int(fallback)


def get_window_state_path():
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    state_dir = os.path.join(base_dir, "DiffusionDarkroom")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, WINDOW_STATE_FILENAME)


def load_window_state():
    state_path = get_window_state_path()
    if not os.path.exists(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_window_state(state):
    state_path = get_window_state_path()
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        print(f"{format_timestamp()}DARKROOM: Could not save window state: {exc}", file=sys.stderr)


def read_window_bounds(window):
    width = None
    height = None
    x_pos = None
    y_pos = None

    try:
        width = int(getattr(window, "width"))
        height = int(getattr(window, "height"))
    except Exception:
        try:
            size = window.get_size()
            if size and len(size) == 2:
                width, height = int(size[0]), int(size[1])
        except Exception:
            pass

    try:
        x_pos = int(getattr(window, "x"))
        y_pos = int(getattr(window, "y"))
    except Exception:
        try:
            pos = window.get_position()
            if pos and len(pos) == 2:
                x_pos, y_pos = int(pos[0]), int(pos[1])
        except Exception:
            pass

    result = {}
    if width and height:
        result["width"] = max(1000, width)
        result["height"] = max(700, height)
    if x_pos is not None and y_pos is not None:
        result["x"] = x_pos
        result["y"] = y_pos
    return result


class DesktopBridge:
    def set_title(self, title):
        try:
            if webview.windows:
                webview.windows[0].title = str(title)
                return True
        except Exception:
            pass
        return False


def parse_args():
    default_title = str(get_desktop_config_value("title", "Diffusion Darkroom"))
    default_width = get_desktop_config_int("width", 1600)
    default_height = get_desktop_config_int("height", 1000)
    parser = argparse.ArgumentParser(description="Diffusion Darkroom desktop launcher")
    parser.add_argument("--port", type=int, default=None, help="Optional fixed port")
    parser.add_argument("--title", default=default_title, help="Desktop window title")
    parser.add_argument("--width", type=int, default=default_width, help="Initial window width")
    parser.add_argument("--height", type=int, default=default_height, help="Initial window height")
    return parser.parse_args()


def main():
    args = parse_args()
    httpd = None
    server_thread = None

    try:
        httpd, _, url = bootstrap(mode="desktop", port=args.port)
        server_thread = start_server_thread(httpd)
        print(f"{format_timestamp()}DARKROOM: Launching desktop window at {url}", file=sys.stderr)

        bridge = DesktopBridge()
        state = load_window_state()
        window_kwargs = {
            "url": url,
            "width": int(state.get("width", args.width)),
            "height": int(state.get("height", args.height)),
            "min_size": (1000, 700),
            "js_api": bridge,
        }
        if "x" in state and "y" in state:
            window_kwargs["x"] = int(state["x"])
            window_kwargs["y"] = int(state["y"])

        try:
            window = webview.create_window(args.title, **window_kwargs)
        except TypeError:
            # Some runtimes don't support explicit x/y.
            window_kwargs.pop("x", None)
            window_kwargs.pop("y", None)
            window = webview.create_window(args.title, **window_kwargs)

        def persist_bounds(*_):
            bounds = read_window_bounds(window)
            if bounds:
                save_window_state(bounds)

        try:
            window.events.resized += persist_bounds
        except Exception:
            pass
        try:
            window.events.moved += persist_bounds
        except Exception:
            pass
        try:
            window.events.closing += persist_bounds
        except Exception:
            pass
        try:
            window.events.closed += persist_bounds
        except Exception:
            pass

        webview.start()

    except KeyboardInterrupt:
        print(f"\n{format_timestamp()}DARKROOM: Desktop launcher interrupted.", file=sys.stderr)
    except Exception as exc:
        print(f"{format_timestamp()} ERROR: Desktop launcher failed: {type(exc).__name__} - {exc}", file=sys.stderr)
        raise
    finally:
        if httpd:
            stop_server(httpd)
            print(f"{format_timestamp()}DARKROOM: Desktop server stopped.", file=sys.stderr)
        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=2)


if __name__ == "__main__":
    main()
