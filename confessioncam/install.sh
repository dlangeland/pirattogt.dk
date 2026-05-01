#!/bin/bash
# ConfessionCam — one-shot setup script for Raspberry Pi OS (Bookworm)
set -e

echo "==> Updating package lists..."
sudo apt update

echo "==> Installing system dependencies..."
sudo apt install -y \
    python3-picamera2 \
    python3-gpiozero \
    python3-numpy \
    python3-pil \
    python3-pil.imagetk \
    python3-tk \
    mpv \
    ffmpeg

# The apt Pillow package splits ImageTk into a separate package that can be
# shadowed by older pip versions. Upgrading Pillow via pip ensures ImageTk
# works reliably regardless of what the system package provides.
echo "==> Upgrading Pillow (required for ImageTk support)..."
pip3 install --break-system-packages --upgrade Pillow

echo "==> Creating required directories..."
mkdir -p media recordings

echo "==> Installing systemd user service..."
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"
cp confessioncam.service "$SERVICE_DIR/confessioncam.service"
systemctl --user daemon-reload
systemctl --user enable confessioncam

# Allow the service to start automatically without an interactive login session
loginctl enable-linger "$USER"

echo ""
echo "Installation complete."
echo ""
echo "Next steps:"
echo "  1. Copy your default loop video to:  media/default_video.mp4"
echo "  2. Wire the buttons (connect other leg to GND, BCM numbering):"
echo "       Start : GPIO 17"
echo "       Stop  : GPIO 27"
echo "       Quit  : GPIO 22  (hold 3 s to shut down the app)"
echo "  3. Edit config.py to adjust pins, resolution, timeout, or bitrate."
echo ""
echo "Service control:"
echo "  Start now  : systemctl --user start confessioncam"
echo "  Stop now   : systemctl --user stop confessioncam"
echo "  View logs  : journalctl --user -u confessioncam -f"
echo "  Disable    : systemctl --user disable confessioncam"
echo ""
echo "The app will start automatically on next reboot (auto-login must be enabled)."
