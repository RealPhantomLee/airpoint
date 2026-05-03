"""Platform detection and compatibility utilities."""

import platform
import sys


def get_os() -> str:
    """Return 'linux', 'macos', 'windows', or 'unknown'."""
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    elif system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    return "unknown"


def get_screen_size() -> tuple[int, int]:
    """Get screen resolution cross-platform."""
    try:
        if get_os() == "linux":
            try:
                from pynput import mouse
                c = mouse.Controller()
                if c.screen:
                    return c.screen.width, c.screen.height
            except Exception:
                pass

            import subprocess
            try:
                result = subprocess.run(
                    ["xdpyinfo"], capture_output=True, text=True, timeout=2
                )
                for line in result.stdout.split("\n"):
                    if "dimensions:" in line:
                        dims = line.split(":")[1].strip().split("x")
                        return int(dims[0]), int(dims[1].split()[0])
            except Exception:
                pass

        elif get_os() == "macos":
            import subprocess
            try:
                result = subprocess.run(
                    ["system_profiler", "SPDisplaysDataType"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    line = line.strip()
                    if "Resolution" in line:
                        import re
                        match = re.search(r"(\d+)\s*x\s*(\d+)", line)
                        if match:
                            return int(match.group(1)), int(match.group(2))
            except Exception:
                pass

        elif get_os() == "windows":
            import ctypes
            user32 = ctypes.windll.user32
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    except Exception:
        pass

    return (1920, 1080)


def is_wayland() -> bool:
    """Check if running under Wayland."""
    if get_os() != "linux":
        return False
    return "wayland" in platform.system().lower() or \
           "WAYLAND_DISPLAY" in __import__("os").environ


def get_default_camera_index() -> int:
    """Return default camera index for the platform."""
    return 0


def get_camera_device_path(index: int = 0) -> str:
    """Get platform-specific camera device path."""
    if get_os() == "windows":
        return str(index)  # OpenCV uses 0,1,2 on Windows
    elif get_os() == "macos":
        return str(index)  # OpenCV uses AVFoundation indices
    return f"/dev/video{index}"
