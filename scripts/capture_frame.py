#!/usr/bin/env python3
"""Minimal frame reader for a go2rtc RTSP stream.

Gives you a `frame` (BGR numpy array) + millisecond timestamp per loop
iteration -- plug your own OpenCV/AI logic into `process_frame`.

Example:
    python scripts/capture_frame.py --stream cam0            # shows a live window
    python scripts/capture_frame.py --stream cam0 --no-display # headless (e.g. on a server)
"""
import argparse
import time

import cv2


def process_frame(frame, ts_ms: int) -> None:
    # TODO: your own logic goes here (AI inference, saving, etc.)
    print(f"[{ts_ms}] frame {frame.shape[1]}x{frame.shape[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument("--stream", required=True, help="go2rtc stream name, e.g. cam0")
    parser.add_argument("--display", dest="display", action="store_true", default=True,
                         help="show a live preview window (default on)")
    parser.add_argument("--no-display", dest="display", action="store_false",
                         help="skip cv2.imshow, e.g. on a headless server")
    args = parser.parse_args()

    url = f"rtsp://{args.host}:{args.port}/{args.stream}"
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        raise SystemExit(f"cannot open stream: {url}")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.5)
                continue
            process_frame(frame, int(time.time() * 1000))

            if args.display:
                cv2.imshow(args.stream, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
