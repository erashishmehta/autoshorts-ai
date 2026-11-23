from pathlib import Path

import cv2


_face_cascade = None


def _report(message, progress_callback=None):
    print(f"[AutoShorts] {message}", flush=True)
    if progress_callback:
        progress_callback(message)


def get_face_cascade():
    """Load OpenCV's bundled Haar face detector once."""
    global _face_cascade

    if _face_cascade is None:
        cascade_path = (
            Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        )
        if not cascade_path.is_file():
            raise FileNotFoundError(
                f"OpenCV face-detection model was not found: {cascade_path}"
            )

        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            raise RuntimeError("OpenCV could not load its face-detection model.")

        _face_cascade = cascade

    return _face_cascade


def detect_face_crop_x(video_path, clip, progress_callback=None):
    """
    Detect faces at intervals in a clip and return the horizontal crop offset
    after scaling to a 1080x1920 canvas.

    The largest detected face in each sampled frame is used. The median face
    centre across samples reduces sudden crop jumps. Returns None when face
    detection is unavailable or no face is found, allowing centre-crop fallback.
    """
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        _report("OpenCV could not open the video; using centre crop.", progress_callback)
        return None

    try:
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        duration = max(0.0, float(clip["end"]) - float(clip["start"]))

        if frame_width <= 0 or frame_height <= 0:
            _report(
                "Could not read video dimensions; using centre crop.", progress_callback
            )
            return None

        scale_factor = max(1080 / frame_width, 1920 / frame_height)
        scaled_width = int(round(frame_width * scale_factor))
        max_crop_x = max(0, scaled_width - 1080)

        if max_crop_x == 0:
            _report(
                "Source is already portrait; no horizontal crop needed.",
                progress_callback,
            )
            return 0

        cascade = get_face_cascade()
        face_centres = []

        # Sample at roughly one-second intervals, capped to keep processing fast.
        sample_count = min(20, max(1, int(duration) + 1))
        sample_times = [
            float(clip["start"]) + (duration * index / max(1, sample_count - 1))
            for index in range(sample_count)
        ]

        for sample_time in sample_times:
            if fps > 0:
                frame_number = max(0, int(sample_time * fps))
                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            else:
                capture.set(cv2.CAP_PROP_POS_MSEC, sample_time * 1000)

            success, frame = capture.read()
            if not success or frame is None:
                continue

            detection_width = 640
            resize_ratio = detection_width / frame.shape[1]
            detection_height = max(1, int(frame.shape[0] * resize_ratio))
            small_frame = cv2.resize(
                frame,
                (detection_width, detection_height),
                interpolation=cv2.INTER_AREA,
            )
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )

            if len(faces) == 0:
                continue

            x, y, width, height = max(
                faces,
                key=lambda face: int(face[2]) * int(face[3]),
            )

            centre_x_small = float(x) + float(width) / 2
            centre_x_original = centre_x_small / resize_ratio
            face_centres.append(centre_x_original)

        if not face_centres:
            _report(
                "No face detected in this clip; using centre crop.", progress_callback
            )
            return None

        face_centre_original = sorted(face_centres)[len(face_centres) // 2]
        face_centre_scaled = face_centre_original * scale_factor
        crop_x = int(round(face_centre_scaled - 1080 / 2))
        crop_x = max(0, min(crop_x, max_crop_x))

        _report(
            f"Face detected in {len(face_centres)}/{sample_count} samples. "
            f"Using smart crop (x={crop_x}).",
            progress_callback,
        )
        return crop_x

    except Exception as error:
        print(
            f"[AutoShorts] Face detection failed; using centre crop: {error}",
            flush=True,
        )
        return None

    finally:
        capture.release()
