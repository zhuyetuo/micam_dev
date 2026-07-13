#!/usr/bin/env python3
"""Pull frames from a go2rtc RTSP stream for custom AI / motion-detection work.

Example:
    python scripts/capture_frame.py --stream cam0
"""
import argparse
import time

import cv2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument("--stream", required=True, help="go2rtc stream name, e.g. cam0")
    parser.add_argument("--motion-threshold", type=float, default=25.0,
                         help="mean pixel diff above which a frame is flagged as motion")
    args = parser.parse_args()

    url = f"rtsp://{args.host}:{args.port}/{args.stream}"
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise SystemExit(f"cannot open stream: {url}")

    prev_gray = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.5)
                continue

            ts_ms = int(time.time() * 1000)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_gray is not None:
                score = cv2.absdiff(prev_gray, gray).mean()
                if score > args.motion_threshold:
                    print(f"[{ts_ms}] motion detected, score={score:.2f}")
            prev_gray = gray
    finally:
        cap.release()


if __name__ == "__main__":
    main()
