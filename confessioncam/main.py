#!/usr/bin/env python3
"""ConfessionCam — kiosk app for Raspberry Pi 5.

Idle state : mpv plays default_video.mp4 embedded inside the tkinter window.
Recording  : camera preview shown fullscreen; footage saved to recordings/.
Transitions driven by three GPIO push-buttons and an optional auto-stop timer.

  GPIO_START_PIN — start recording
  GPIO_STOP_PIN  — stop recording, return to idle video
  GPIO_QUIT_PIN  — hold for QUIT_HOLD_TIME seconds to shut the application down
"""

import json
import os
import queue
import socket
import subprocess
import threading
from datetime import datetime

import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
from libcamera import Transform
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from gpiozero import Button

from config import (
    DEFAULT_VIDEO,
    RECORDINGS_DIR,
    MAX_RECORDING_DURATION,
    GPIO_START_PIN,
    GPIO_STOP_PIN,
    GPIO_QUIT_PIN,
    QUIT_HOLD_TIME,
    CAMERA_RESOLUTION,
    PREVIEW_RESOLUTION,
    RECORDING_BITRATE,
    PREVIEW_FPS,
    IDLE_VIDEO_BRIGHTNESS,
)

MPV_IPC_SOCKET = "/tmp/confessioncam_mpv.sock"


# ---------------------------------------------------------------------------
# YUV420 (I420 planar) → RGB conversion without OpenCV
# ---------------------------------------------------------------------------

def _yuv420_to_rgb(frame: np.ndarray, width: int, height: int) -> Image.Image:
    y = frame[:height].astype(np.float32)

    u_raw = frame[height : height + height // 4]
    v_raw = frame[height + height // 4 : height + height // 2]

    u = u_raw.reshape(height // 2, width // 2).astype(np.float32) - 128
    v = v_raw.reshape(height // 2, width // 2).astype(np.float32) - 128

    u = np.repeat(np.repeat(u, 2, axis=0), 2, axis=1)
    v = np.repeat(np.repeat(v, 2, axis=0), 2, axis=1)

    r = np.clip(y + 1.402 * v, 0, 255).astype(np.uint8)
    g = np.clip(y - 0.344136 * u - 0.714136 * v, 0, 255).astype(np.uint8)
    b = np.clip(y + 1.772 * u, 0, 255).astype(np.uint8)

    return Image.fromarray(np.stack([r, g, b], axis=-1))


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class ConfessionCam:

    def __init__(self) -> None:
        os.makedirs(RECORDINGS_DIR, exist_ok=True)

        # --- Tkinter window — always visible, never withdrawn ---------------
        self.root = tk.Tk()
        self.root.title("ConfessionCam")
        self.root.configure(bg="black")
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", lambda _e: self.shutdown())
        self.root.update()

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # mpv is embedded in this frame during idle playback
        self.mpv_frame = tk.Frame(self.root, bg="black")
        self.mpv_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.root.update()  # ensure mpv_frame is mapped so winfo_id() is valid

        # Canvas: shown during recording, hidden during idle
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)

        # --- Camera ---------------------------------------------------------
        self.camera = Picamera2()
        cam_cfg = self.camera.create_video_configuration(
            main={"size": CAMERA_RESOLUTION},
            lores={"size": PREVIEW_RESOLUTION, "format": "YUV420"},
            transform=Transform(hflip=True, vflip=True),  # camera mounted 180°
        )
        self.camera.configure(cam_cfg)

        # --- GPIO buttons ---------------------------------------------------
        self.start_btn = Button(GPIO_START_PIN, pull_up=True, bounce_time=0.05)
        self.stop_btn = Button(GPIO_STOP_PIN, pull_up=True, bounce_time=0.05)
        self.quit_btn = Button(GPIO_QUIT_PIN, pull_up=True, hold_time=QUIT_HOLD_TIME)
        self.start_btn.when_pressed = lambda: self.root.after(0, self.start_recording)
        self.stop_btn.when_pressed = lambda: self.root.after(0, self.stop_recording)
        self.quit_btn.when_held = lambda: self.root.after(0, self.shutdown)

        # --- Internal state -------------------------------------------------
        self.is_recording = False
        self.recording_timer: threading.Timer | None = None
        self.preview_running = False
        self.preview_thread: threading.Thread | None = None
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._photo_ref = None
        self.idle_proc: subprocess.Popen | None = None
        self._resume_pos: float = 0.0  # playback position to resume after recording

    # -----------------------------------------------------------------------
    # mpv IPC — query playback position before killing the process
    # -----------------------------------------------------------------------

    def _query_mpv_position(self) -> float:
        """Return current mpv playback-time in seconds, or 0.0 on failure."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect(MPV_IPC_SOCKET)
            request = json.dumps({"command": ["get_property", "playback-time"]}) + "\n"
            sock.sendall(request.encode())
            data = b""
            while b"\n" not in data:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            sock.close()
            result = json.loads(data.decode().split("\n")[0])
            return float(result.get("data") or 0.0)
        except Exception:
            return 0.0

    # -----------------------------------------------------------------------
    # Idle mode
    # -----------------------------------------------------------------------

    def _launch_idle_video(self, start_pos: float = 0.0) -> None:
        # Remove stale IPC socket so mpv can create a fresh one
        try:
            os.unlink(MPV_IPC_SOCKET)
        except FileNotFoundError:
            pass

        # Show mpv frame, hide canvas
        self.canvas.place_forget()
        self.mpv_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.root.update()

        cmd = [
            "mpv",
            DEFAULT_VIDEO,
            f"--wid={self.mpv_frame.winfo_id()}",
            "--loop=inf",
            "--no-terminal",
            "--quiet",
            "--no-osc",
            "--no-input-default-bindings",
            "--no-keepaspect-window",
            f"--brightness={IDLE_VIDEO_BRIGHTNESS}",
            f"--start={start_pos:.3f}",
            f"--input-ipc-server={MPV_IPC_SOCKET}",
        ]
        # Unset WAYLAND_DISPLAY so mpv uses X11/XWayland (required for --wid)
        env = os.environ.copy()
        env.pop("WAYLAND_DISPLAY", None)
        self.idle_proc = subprocess.Popen(cmd, env=env)

    def _stop_idle_video(self) -> float:
        """Terminate mpv and return its playback position."""
        pos = self._query_mpv_position()
        if self.idle_proc and self.idle_proc.poll() is None:
            self.idle_proc.terminate()
            try:
                self.idle_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.idle_proc.kill()
        self.idle_proc = None
        return pos

    def start_idle(self) -> None:
        self.is_recording = False
        self._launch_idle_video(start_pos=self._resume_pos)
        self._resume_pos = 0.0

    # -----------------------------------------------------------------------
    # Recording mode
    # -----------------------------------------------------------------------

    def start_recording(self) -> None:
        if self.is_recording:
            return
        self.is_recording = True

        # Save position and stop idle video
        self._resume_pos = self._stop_idle_video()

        # Show canvas, hide mpv frame
        self.mpv_frame.place_forget()
        self.canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.root.update()

        # Build timestamped output path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(RECORDINGS_DIR, f"confession_{ts}.mp4")

        # Start H264 recording (hardware-accelerated on Pi 5)
        self.camera.start_recording(
            H264Encoder(bitrate=RECORDING_BITRATE), FfmpegOutput(out_path)
        )

        # Start background frame-capture thread
        self.preview_running = True
        self.frame_queue = queue.Queue(maxsize=2)
        self.preview_thread = threading.Thread(
            target=self._capture_loop, daemon=True
        )
        self.preview_thread.start()
        self._schedule_draw()

        # Auto-stop after MAX_RECORDING_DURATION seconds
        self.recording_timer = threading.Timer(
            MAX_RECORDING_DURATION,
            lambda: self.root.after(0, self.stop_recording),
        )
        self.recording_timer.start()

    def stop_recording(self) -> None:
        if not self.is_recording:
            return

        if self.recording_timer:
            self.recording_timer.cancel()
            self.recording_timer = None

        self.preview_running = False
        if self.preview_thread:
            self.preview_thread.join(timeout=2)

        self.camera.stop_recording()
        self.start_idle()

    # -----------------------------------------------------------------------
    # Camera preview
    # -----------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Background thread: push lores frames into the queue."""
        while self.preview_running:
            try:
                frame = self.camera.capture_array("lores")
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    pass
            except Exception:
                break

    def _schedule_draw(self) -> None:
        """Main-thread callback: pull a frame and update the canvas."""
        if not self.preview_running:
            return
        try:
            frame = self.frame_queue.get_nowait()
            # Derive actual buffer dimensions from the array shape.
            # The ISP may pad stride beyond the configured width, so
            # PREVIEW_RESOLUTION cannot be used directly here.
            buf_w = frame.shape[1]
            buf_h = frame.shape[0] * 2 // 3  # YUV420: total rows = h * 3/2
            img = _yuv420_to_rgb(frame, buf_w, buf_h)
            # Crop away stride padding before scaling; padding bytes have
            # U=V=0 which converts to green and appears as a right-edge bar.
            pw, ph = PREVIEW_RESOLUTION
            if buf_w > pw:
                img = img.crop((0, 0, pw, ph))
            img = img.resize((self.screen_w, self.screen_h), Image.NEAREST)
            photo = ImageTk.PhotoImage(img)
            self._photo_ref = photo
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=photo)
        except queue.Empty:
            pass
        except Exception as exc:
            import traceback
            traceback.print_exc()
        self.root.after(1000 // PREVIEW_FPS, self._schedule_draw)

    # -----------------------------------------------------------------------
    # Fan control
    # -----------------------------------------------------------------------

    def _fan_full(self) -> None:
        """Drive FAN_PWM low → full speed."""
        subprocess.run(["pinctrl", "FAN_PWM", "op", "dl"],
                       check=False, capture_output=True)

    def _fan_auto(self) -> None:
        """Restore FAN_PWM to a0 (PWM1_CHAN3) for thermal-daemon control."""
        subprocess.run(["pinctrl", "FAN_PWM", "a0"],
                       check=False, capture_output=True)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def shutdown(self) -> None:
        self.preview_running = False
        if self.recording_timer:
            self.recording_timer.cancel()
        if self.is_recording:
            try:
                self.camera.stop_recording()
            except Exception:
                pass
        self._stop_idle_video()
        try:
            self.camera.close()
        except Exception:
            pass
        self._fan_auto()
        self.root.destroy()

    def run(self) -> None:
        self._fan_full()
        self.start_idle()
        self.root.mainloop()


if __name__ == "__main__":
    app = ConfessionCam()
    app.run()
