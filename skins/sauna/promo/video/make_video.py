"""Montage of the Sauna Stove day-to-night clip recorded in the Rust Workshop editor.

One recording (preview mode, see HOWTO.md) -> two videos in out/:
  sauna_stove_day_to_night_16x9.mp4  1920x1080  Workshop page / YouTube / Reddit / X
  sauna_stove_day_to_night_9x16.mp4  1080x1920  YouTube Shorts

The editor draws its own UI over the scene (title "SAUNA STOVE / AKEELOW" with buttons top right, a tab on the
left, a toolbar bottom left, SKYBOX/TIME sliders bottom right). Crops are measured on the 1920x1080 editor shots of
22.11.2026 (electric-furnace/screenshots/v3.1) and scaled to the recording's size:
  16:9  x 163..1625, y 162..984  (the upload_v3 frame moved 10 px left, clear of the buttons)
  9:16  y 0..984, 554 wide around --cx (must stay right of the tab and left of the title: centre 313..938 px)

Usage (from the repo root):
  .venv/Scripts/python skins/sauna/promo/video/make_video.py --preview      # frames with crop boxes -> out/
  .venv/Scripts/python skins/sauna/promo/video/make_video.py --start 2 --end 38 --fit 26
  ... --ambient        quiet brown-noise bed instead of silence
  ... --music FILE     quiet music bed (volume 0.12) instead of silence
  ... --dry-run --size 1920x1080 --duration 40   print the ffmpeg commands without ffmpeg

Input: the newest .mp4/.mkv/.mov in raw/ unless a path is given.
ffmpeg: from PATH, or $FFMPEG, or the imageio-ffmpeg package.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
OUT = HERE / "out"
NAME = "sauna_stove_day_to_night"

REF_W, REF_H = 1920, 1080
WIDE = dict(x0=163, x1=1625, y0=162, y1=984)  # 1462x822, 16:9; 10 px clear of the buttons
TALL_Y1 = 984                                 # tall crop: y 0..984
TALL_W = round(TALL_Y1 * 9 / 16)              # 554
TALL_CX_MIN = 36 + TALL_W // 2                # right of the left tab
TALL_CX_MAX = 1215 - TALL_W // 2              # left of the title
FPS = 30
FADE_IN, FADE_OUT = 0.4, 0.8


def find_ffmpeg() -> str:
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found. Install: scoop install ffmpeg  (or: winget install Gyan.FFmpeg)")


def probe(ffmpeg: str, src: Path) -> tuple[int, int, float]:
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.search(r"Stream #.*Video:.*?(\d{3,5})x(\d{3,5})", r.stderr)
    d = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m or not d:
        sys.exit(f"cannot read video size/duration of {src}:\n{r.stderr[-800:]}")
    dur = int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3])
    return int(m[1]), int(m[2]), dur


def even(v: float) -> int:
    return int(round(v / 2)) * 2


def crops(w: int, h: int, cx: float) -> tuple[str, str]:
    sx, sy = w / REF_W, h / REF_H
    wx, wy = even(WIDE["x0"] * sx), even(WIDE["y0"] * sy)
    ww = even((WIDE["x1"] - WIDE["x0"]) * sx)
    wh = even(ww * 9 / 16)
    cxp = cx * REF_W
    if not TALL_CX_MIN <= cxp <= TALL_CX_MAX:
        print(f"warning: --cx {cx} puts the 9:16 crop over the editor UI; clamped to "
              f"{TALL_CX_MIN / REF_W:.3f}..{TALL_CX_MAX / REF_W:.3f}")
        cxp = min(max(cxp, TALL_CX_MIN), TALL_CX_MAX)
    th = even(TALL_Y1 * sy)
    tw = even(th * 9 / 16)
    tx = even(cxp * sx - tw / 2)
    return f"crop={ww}:{wh}:{wx}:{wy}", f"crop={tw}:{th}:{tx}:0"


def run(cmd: list[str], dry: bool) -> None:
    print(" ".join(f'"{c}"' if " " in c or ";" in c else c for c in cmd))
    if not dry:
        subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", help="recording (default: newest video in raw/)")
    ap.add_argument("--start", type=float, default=0.0, help="cut from, s")
    ap.add_argument("--end", type=float, help="cut to, s (default: end of file)")
    ap.add_argument("--fit", type=float, help="speed the cut up/down to this length, s (e.g. 26)")
    ap.add_argument("--cx", type=float, default=0.45, help="stove centre x as a fraction of the width, for 9:16")
    ap.add_argument("--ambient", action="store_true", help="quiet brown-noise bed")
    ap.add_argument("--music", help="quiet music bed from this file")
    ap.add_argument("--only", choices=["16x9", "9x16"], help="render one format")
    ap.add_argument("--preview", action="store_true", help="only write first/middle/last frames with crop boxes")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--size", help="WxH, with --dry-run when there is no ffmpeg")
    ap.add_argument("--duration", type=float, help="s, with --dry-run when there is no ffmpeg")
    a = ap.parse_args()

    if a.src:
        src = Path(a.src)
    else:
        vids = sorted((p for p in RAW.glob("*") if p.suffix.lower() in {".mp4", ".mkv", ".mov"}),
                      key=lambda p: p.stat().st_mtime)
        src = vids[-1] if vids else RAW / "recording.mp4"
    if not src.exists() and not a.dry_run:
        sys.exit(f"no recording: put it into {RAW}")

    if a.dry_run and a.size and a.duration:
        ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
        w, h = map(int, a.size.lower().split("x"))
        dur = a.duration
    else:
        ffmpeg = find_ffmpeg()
        w, h, dur = probe(ffmpeg, src)
    end = min(a.end, dur) if a.end else dur
    length = end - a.start
    out_len = a.fit or length
    wide, tall = crops(w, h, a.cx)
    print(f"{src.name}: {w}x{h}, {dur:.1f} s; cut {a.start:.1f}..{end:.1f} s -> {out_len:.1f} s")
    OUT.mkdir(exist_ok=True)

    if a.preview:
        ww, wh, x, y = map(int, wide.split("=")[1].split(":"))
        tw, th, tx, _ = map(int, tall.split("=")[1].split(":"))
        boxes = (f"drawbox=x={x}:y={y}:w={ww}:h={wh}:color=yellow@0.9:t=4,"
                 f"drawbox=x={tx}:y=0:w={tw}:h={th}:color=cyan@0.9:t=4")
        for tag, t in (("first", a.start + 0.5), ("middle", a.start + length / 2), ("last", end - 0.5)):
            run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src),
                 "-frames:v", "1", "-vf", boxes, "-q:v", "3", str(OUT / f"preview_{tag}.jpg")], a.dry_run)
        print("yellow = 16:9, cyan = 9:16")
        return

    speed = f"setpts=PTS*{out_len / length:.5f}," if a.fit else ""
    fades = f"fade=t=in:st=0:d={FADE_IN},fade=t=out:st={out_len - FADE_OUT:.2f}:d={FADE_OUT}"
    jobs = {
        "16x9": f"{wide},scale=1920:1080:flags=lanczos",
        "9x16": f"{tall},scale=1080:1920:flags=lanczos,unsharp=5:5:0.5",
    }
    for tag, geo in jobs.items():
        if a.only and a.only != tag:
            continue
        vf = f"[0:v]{speed}{geo},fps={FPS},{fades},format=yuv420p[v]"
        cmd = [ffmpeg, "-hide_banner", "-y", "-ss", f"{a.start:.2f}", "-to", f"{end:.2f}", "-i", str(src)]
        if a.music or a.ambient:
            if a.music:
                cmd += ["-stream_loop", "-1", "-i", a.music]
                bed = "[1:a]volume=0.12"
            else:
                cmd += ["-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.6:sample_rate=48000"]
                bed = "[1:a]lowpass=f=500,volume=0.05"
            af = (f"{bed},atrim=0:{out_len:.2f},afade=t=in:st=0:d=1.5,"
                  f"afade=t=out:st={out_len - 2:.2f}:d=2[a]")
            cmd += ["-filter_complex", f"{vf};{af}", "-map", "[v]", "-map", "[a]",
                    "-c:a", "aac", "-b:a", "128k", "-t", f"{out_len:.2f}"]
        else:
            cmd += ["-filter_complex", vf, "-map", "[v]", "-an"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", str(FPS),
                "-movflags", "+faststart", str(OUT / f"{NAME}_{tag}.mp4")]
        run(cmd, a.dry_run)
    print(f"done -> {OUT}")


if __name__ == "__main__":
    main()
