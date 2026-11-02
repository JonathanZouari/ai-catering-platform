# Builds the README walkthrough from Stitch screenshots (tracker.png, pitwall.png).
# uv run --no-project --with pillow --with imageio-ffmpeg python make_video.py <img_dir> <out_dir>
"""Render a phone-simulator style walkthrough of the Stitch F1 screens to MP4 + GIF."""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

D = Path(sys.argv[1])
OUT = Path(sys.argv[2])
W, H, FPS = 1280, 720, 24
BG, RED, MUTED = (11, 15, 23), (255, 30, 0), (148, 163, 184)
font = lambda s, mono=False: ImageFont.truetype(
    "/System/Library/Fonts/SFNSMono.ttf" if mono else "/System/Library/Fonts/HelveticaNeue.ttc", s, index=0) \
    if not mono else ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", s)
F_T, F_S, F_M = font(46), font(24), font(18, True)

tracker = Image.open(D / "tracker.png").convert("RGB")
pit = Image.open(D / "pitwall.png").convert("RGB")
# phone screen 300x650 (iPhone-ish ratio); tracker scaled to 300 wide
SW, SH = 300, 650
trk = tracker.resize((SW, round(tracker.height * SW / tracker.width)), Image.LANCZOS)
# browser viewport 880x470; pit wall scaled to 880 wide
BW, BH = 880, 470
pw = pit.resize((BW, round(pit.height * BW / pit.width)), Image.LANCZOS)

def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)

def base():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # chequered strip along the bottom
    for i in range(0, W, 16):
        for r in range(2):
            if (i // 16 + r) % 2 == 0:
                d.rectangle([i, H - 16 + r * 8, i + 15, H - 9 + r * 8], fill=(40, 44, 56))
    d.rectangle([0, 0, W, 4], fill=RED)
    return im, d

def phone(im, scroll):
    x0, y0 = 120, (H - SH) // 2 - 6
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([x0 - 14, y0 - 14, x0 + SW + 14, y0 + SH + 14], 46, fill=(30, 32, 40), outline=(70, 74, 86), width=2)
    screen = trk.crop((0, scroll, SW, scroll + SH))
    mask = Image.new("L", (SW, SH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SW, SH], 34, fill=255)
    im.paste(screen, (x0, y0), mask)
    d.rounded_rectangle([x0 + SW // 2 - 50, y0 + 10, x0 + SW // 2 + 50, y0 + 36], 13, fill=(0, 0, 0))

def browser(im, scroll, alpha=1.0):
    x0, y0 = (W - BW) // 2, 150
    layer = im.copy()
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0 - 2, y0 - 38, x0 + BW + 2, y0 + BH + 2], 12, fill=(30, 32, 40), outline=(70, 74, 86), width=2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([x0 + 14 + i * 20, y0 - 25, x0 + 26 + i * 20, y0 - 13], fill=c)
    d.rounded_rectangle([x0 + 90, y0 - 30, x0 + BW - 90, y0 - 8], 6, fill=(15, 18, 26))
    d.text((x0 + 104, y0 - 28), "caterking · /admin  —  Pit Wall", font=F_M, fill=MUTED)
    layer.paste(pw.crop((0, scroll, BW, scroll + BH)), (x0, y0))
    return Image.blend(im, layer, alpha) if alpha < 1 else layer

def caption(d, x, y, title, lines):
    d.text((x, y), title, font=F_T, fill=(255, 255, 255))
    for i, l in enumerate(lines):
        d.text((x, y + 70 + i * 36), l, font=F_S, fill=MUTED)

frames = []
def add(fn, seconds):
    n = int(seconds * FPS)
    for i in range(n):
        frames.append(fn(i / max(1, n - 1)))

def title(t):
    im, d = base()
    a = ease(t * 3)
    col = tuple(int(BG[k] + (255 - BG[k]) * a) for k in range(3))
    d.text((120, 250), "CATERKING", font=font(84), fill=col)
    d.text((124, 360), "F1 Pit Wall redesign  ·  concept", font=F_S, fill=RED)
    d.text((124, 400), "Designed in Stitch — Box Box  →  Flying Lap  →  Chequered Flag", font=F_S, fill=MUTED)
    return im

def scene_phone(t):
    im, d = base()
    phone(im, int(ease(t) * (trk.height - SH)))
    caption(d, 520, 170, "Customer tracker", [
        "Sector Times: S1 kitchen · S2 on track · S3 flag",
        "DRS badge when the kitchen is ahead of plan",
        "Safety Car ticker when the kitchen is paced",
        "Hebrew · Arabic · English, right-to-left",
    ])
    d.text((520, 520), "LAP %d/4" % (1 + int(ease(t) * 3.99)), font=F_M, fill=(168, 85, 247))
    return im

def scene_pit(t):
    im, d = base()
    d.text((200, 50), "Pit Wall  —  owner dashboard", font=F_T, fill=(255, 255, 255))
    return browser(im, int(ease(t) * (pw.height - BH)), alpha=ease(t * 6))

def outro(t):
    im, d = base()
    d.text((120, 280), "Until the next Grand Prix!", font=font(60), fill=(255, 255, 255))
    d.text((124, 370), "Concept preview — not live yet", font=F_S, fill=MUTED)
    sq = 22
    for r in range(4):
        for c in range(10):
            if (r + c) % 2 == 0 and c < int(ease(t * 2) * 10) + 1:
                d.rectangle([900 + c * sq, 280 + r * sq, 900 + c * sq + sq - 1, 280 + r * sq + sq - 1], fill=(255, 255, 255))
    return im

add(title, 2.5)
add(scene_phone, 8)
add(scene_pit, 7)
add(outro, 2.5)

exe = imageio_ffmpeg.get_ffmpeg_exe()
mp4 = OUT / "caterking-f1-sim.mp4"
p = subprocess.Popen([exe, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", "-movflags", "+faststart", str(mp4)],
                     stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
for f in frames:
    p.stdin.write(f.tobytes())
p.stdin.close(); p.wait()
# GIF for inline README playback: half size, 12 fps, shared palette
gif = OUT / "caterking-f1-sim.gif"
subprocess.run([exe, "-y", "-i", str(mp4), "-vf",
                "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                str(gif)], check=True, stderr=subprocess.DEVNULL)
print(len(frames), "frames", mp4.stat().st_size // 1024, "KB mp4", gif.stat().st_size // 1024, "KB gif")
