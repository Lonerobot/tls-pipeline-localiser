"""FFmpeg encode helpers — standalone, no external dependencies.

The ffmpeg executable path is always passed in explicitly so this module has
zero dependency on the parent playblast_plus package or its settings.
"""

import os
import subprocess
import sys
from pathlib import Path


# Default encode settings — can be overridden per call
DEFAULT_INPUT_ARGS = "-c:v libx264 -crf 21 -preset ultrafast -pix_fmt yuv420p"


def open_media_file(filepath: str, player_path: str = "") -> None:
    """Open *filepath* in the preferred viewer, or the OS default if none is set.

    Args:
        filepath (str): Path to a video or image file.
        player_path (str): Optional path to a preferred viewer executable (e.g. DJV2).
                           When non-empty and the executable exists, it is used instead
                           of the OS default.  DJV2 accepts files via:
                           ``djv <file>``
    """
    path = Path(filepath)
    if not path.is_file():
        print(f"[PlayblastPlus] open_media_file: file not found: {filepath}")
        return

    if player_path:
        player = Path(player_path)
        if player.is_file():
            try:
                subprocess.Popen([str(player), str(path)])
                return
            except Exception as exc:
                print(f"[PlayblastPlus] open_media_file: failed to launch {player_path!r}: {exc}, falling back to OS default")
        else:
            print(f"[PlayblastPlus] open_media_file: preferred player not found at {player_path!r}, falling back to OS default")

    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def mp4_from_image_sequence(
    ffmpeg_path: str,
    image_seq_path: str,
    output_path: str,
    framerate: int = 24,
    start_frame: int = 0,
    end_frame: int = 0,
    audio_path: str = None,
    post_open: bool = False,
    add_burnin: bool = False,
    burnin_text: str = "",
    burnin_font_size: int = 24,
    input_args: str = DEFAULT_INPUT_ARGS,
    player_path: str = "",
) -> bool:
    """Encode a PNG image sequence to MP4 using FFmpeg.

    Args:
        ffmpeg_path (str): Absolute path to the ffmpeg executable.
        image_seq_path (str): ffmpeg-style input path, e.g.
                              ``/tmp/shot_%04d.png``.
        output_path (str): Destination MP4 path.
        framerate (int): Output frame rate.
        start_frame (int): First frame number in the sequence.
        end_frame (int): Total number of frames to encode.
        audio_path (str): Optional path to an audio file to mux in.
        post_open (bool): Open the output file after encoding.
        add_burnin (bool): Draw a timecode / name burnin overlay.
        burnin_text (str): Text to render in the burnin.
        burnin_font_size (int): Font size for the burnin.
        input_args (str): FFmpeg video codec arguments string.
        player_path (str): Optional path to a preferred viewer executable.

    Returns:
        bool: True if the output file was created.
    """
    if not ffmpeg_path or not Path(ffmpeg_path).is_file():
        print(f"[PlayblastPlus] ffmpeg not found at: {ffmpeg_path!r}")
        return False

    burnin = ""
    if add_burnin:
        burnin = (
            f'-vf "drawtext=font=Consolas: fontsize={burnin_font_size}: '
            f"fontcolor=white@0.5: text='{burnin_text} | %{{eif\\:n\\:d\\:4}}': "
            f"start_number={start_frame}: r=24: x=(w-tw-20): y=h-lh-20: "
            f'box=1: boxcolor=black@0.5: boxborderw=2"'
        )

    audio_input = f' -i "{audio_path}" ' if audio_path else ""
    audio_params = (
        ' -c:a aac -filter_complex "[1:0] apad" -shortest '
        if audio_path
        else ""
    )

    cmd = (
        f'"{ffmpeg_path}" '
        f"-framerate {framerate} "
        f"-y "
        f"-start_number {start_frame} "
        f"-loglevel quiet "
        f'-i "{image_seq_path}" '
        f"{burnin} "
        f"{audio_input}"
        f"{input_args} "
        f"{audio_params}"
        f"-frames:v {end_frame} "
        f'"{output_path}"'
    )

    print(f"[PlayblastPlus] encode: {cmd}")
    subprocess.call(cmd, shell=True)

    output = Path(output_path)
    if output.is_file():
        if post_open:
            open_media_file(output_path, player_path=player_path)
        return True

    print(f"[PlayblastPlus] encode failed — output not found: {output_path}")
    return False


def apng_from_image_sequence(
    ffmpeg_path: str,
    image_seq_path: str,
    output_path: str,
    framerate: int = 24,
    start_frame: int = 0,
    end_frame: int = 0,
    post_open: bool = False,
    timeout: int = 300,
    player_path: str = "",
) -> bool:
    """Encode a PNG image sequence to APNG using FFmpeg.

    Args:
        ffmpeg_path (str): Absolute path to the ffmpeg executable.
        image_seq_path (str): ffmpeg-style input path, e.g. ``/tmp/shot_%04d.png``.
        output_path (str): Destination .apng path for the APNG.
        framerate (int): Output frame rate.
        start_frame (int): First frame number in the sequence.
        end_frame (int): Total number of frames to encode.
        post_open (bool): Open the output file after encoding.
        timeout (int): Maximum seconds to wait for encoding.
        player_path (str): Optional path to a preferred viewer executable.

    Returns:
        bool: True if the output file was created.
    """
    if not ffmpeg_path or not Path(ffmpeg_path).is_file():
        print(f"[PlayblastPlus] ffmpeg not found at: {ffmpeg_path!r}")
        return False

    cmd = (
        f'"{ffmpeg_path}" '
        f"-framerate {framerate} "
        f"-y "
        f"-start_number {start_frame} "
        f"-loglevel quiet "
        f'-i "{image_seq_path}" '
        f"-c:v png -plays 0 "
        f"-frames:v {end_frame} "
        f'"{output_path}"'
    )

    print(f"[PlayblastPlus] APNG encode: {cmd}")
    try:
        subprocess.call(cmd, shell=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"[PlayblastPlus] APNG encode timed out after {timeout}s — increase 'APNG Encode Timeout' in add-on preferences")
        return False

    output = Path(output_path)
    if output.is_file():
        if post_open:
            open_media_file(output_path, player_path=player_path)
        return True

    print(f"[PlayblastPlus] APNG encode failed — output not found: {output_path}")
    return False
