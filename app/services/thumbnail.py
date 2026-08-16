from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def generate_thumbnail(video_path: Path, output_dir: Path) -> Path | None:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        return None

    thumbnail_path = output_dir / f"{video_path.stem}.jpg"
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(video_path),
        "-ss",
        "00:00:00.500",
        "-vframes",
        "1",
        str(thumbnail_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return None

    return thumbnail_path if thumbnail_path.exists() else None
