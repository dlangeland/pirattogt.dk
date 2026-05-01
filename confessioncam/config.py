import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Video files
DEFAULT_VIDEO = os.path.join(BASE_DIR, "media", "default_video.mp4")
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")

# Recording limits
MAX_RECORDING_DURATION = 180  # seconds (configurable)

# GPIO BCM pin numbers
GPIO_START_PIN = 17
GPIO_STOP_PIN = 27
GPIO_QUIT_PIN = 22   # hold for QUIT_HOLD_TIME seconds to shut down the app

QUIT_HOLD_TIME = 3   # seconds to hold the quit button

# Camera — 2304×1296 is the IMX708 native high-quality 16:9 video mode
CAMERA_RESOLUTION = (2304, 1296)
PREVIEW_RESOLUTION = (960, 540)   # lores stream for live preview (CPU-friendly)
RECORDING_BITRATE = 15_000_000    # bits/s for H264 encoder (~15 Mbps at 2304×1296)

# Preview frame rate during recording
PREVIEW_FPS = 25

# Brightness boost for the idle video (-100 to 100, default 0)
IDLE_VIDEO_BRIGHTNESS = 30
