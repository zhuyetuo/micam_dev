#!/usr/bin/env python3
"""Minimal frame reader for a go2rtc RTSP stream.

Gives you a `frame` (BGR numpy array) + millisecond timestamp per loop
iteration -- plug your own OpenCV/AI logic into `process_frame`.

Example:
    python scripts/capture_frame.py --stream cam0                  # shows a live window
    python scripts/capture_frame.py --stream cam0 --no-display      # headless (e.g. on a server)
    python scripts/capture_frame.py --stream cam0 --low-latency     # always process the newest frame
"""
import argparse
import os
import threading
import time

# Must be set before cv2.VideoCapture opens the stream: tells the FFmpeg
# backend to skip its own internal buffering, which is most of the
# 1-2s lag you get with default settings (worse at high resolution).
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay",
)

import cv2  # noqa: E402


class LatestFrameReader:
    """Drains the capture in a background thread so `read()` always
    returns the newest frame instead of working through a backlog -
    trades "process every frame" for "always see what's happening now"."""

    def __init__(self, cap: cv2.VideoCapture) -> None:
        self._cap = cap
        self._frame = None
        self._ok = False
        self._lock = threading.Lock()
        self._stopped = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stopped:
            ok, frame = self._cap.read()
            with self._lock:
                self._ok, self._frame = ok, frame

    def read(self):
        with self._lock:
            return self._ok, self._frame

    def release(self) -> None:
        self._stopped = True
        self._thread.join(timeout=1)
        self._cap.release()


def process_frame(frame, ts_ms: int) -> None:
    # TODO: your own logic goes here (AI inference, saving, etc.)
    pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument("--stream", required=True, help="go2rtc stream name, e.g. cam0")
    parser.add_argument("--display", dest="display", action="store_true", default=True,
                         help="show a live preview window (default on)")
    parser.add_argument("--no-display", dest="display", action="store_false",
                         help="skip cv2.imshow, e.g. on a headless server")
    parser.add_argument("--resize", metavar="WxH", default=None,
                         help="downscale each frame to WxH before processing, e.g. 1280x720. "
                              "The camera only offers a few fixed quality tiers (subtype=0-5), "
                              "not arbitrary resolutions - use this for an exact target size.")
    parser.add_argument("--low-latency", action="store_true",
                         help="always process the newest frame, dropping any backlog, "
                              "instead of working through frames in arrival order")
    args = parser.parse_args()

    resize_to = None
    if args.resize:
        w, h = args.resize.lower().split("x")
        resize_to = (int(w), int(h))

    url = f"rtsp://{args.host}:{args.port}/{args.stream}"
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise SystemExit(f"cannot open stream: {url}")
    if args.low_latency:
        cap = LatestFrameReader(cap)

    frame_count = 0
    fps = 0.0
    stats_at = time.monotonic()

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01 if args.low_latency else 0.5)
                continue

            if resize_to:
                frame = cv2.resize(frame, resize_to)

            process_frame(frame, int(time.time() * 1000))

            frame_count += 1
            now = time.monotonic()
            if now - stats_at >= 1.0:
                fps = frame_count / (now - stats_at)
                print(f"{frame.shape[1]}x{frame.shape[0]} @ {fps:.1f} fps")
                frame_count = 0
                stats_at = now

            if args.display:
                label = f"{frame.shape[1]}x{frame.shape[0]} @ {fps:.1f} fps"
                cv2.putText(frame, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (0, 255, 0), 2)
                cv2.imshow(args.stream, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
