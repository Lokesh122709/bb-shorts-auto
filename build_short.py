#!/usr/bin/env python3
"""BB20 news Short builder: 1080x1920, 30fps, animated captions + synth beat.

Usage: build_short.py OUT.mp4 [voice_audio_file]
If a voice file is given, chunk timings are stretched to its length and it is mixed over the beat.
"""
import math, subprocess, sys, wave, random, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
import json
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
OUT = sys.argv[2]
VOICE = sys.argv[3] if len(sys.argv) > 3 else None
SP = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(SP, "fonts", "Poppins-Bold.ttf")
MED = os.path.join(SP, "fonts", "Poppins-Medium.ttf")

# ---------------------------------------------------------------- script
# (text, seconds, style)
CHUNKS = [(c[0], float(c[1]), c[2] if len(c) > 2 else "") for c in CFG["chunks"]]
SPEED = 1.0
if VOICE:
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", VOICE]).decode())
    SPEED = (dur + 0.6) / sum(c[1] for c in CHUNKS)
TOTAL = sum(c[1] for c in CHUNKS) * SPEED + 0.4

# chunk start times
starts, t = [], 0.0
for c in CHUNKS:
    starts.append(t)
    t += c[1] * SPEED

# ---------------------------------------------------------------- helpers
_fc = {}
def font(size, path=FONT):
    k = (max(4, int(size)), path)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, k[0])
    return _fc[k]

def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3

BPM = 128.0
BEAT = 60.0 / BPM

# precomputed layout per chunk (base size 86) -> list of lines of (word, w)
BASE = 88
def layout(text, size):
    f = font(size)
    words = text.split()
    lines, cur = [], []
    def wid(ws):
        return f.getlength(" ".join(ws))
    for w in words:
        if cur and wid(cur + [w]) > 930:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- background
random.seed(7)
PARTS = [(random.random(), random.random(), random.uniform(0.02, 0.08), random.uniform(2, 6)) for _ in range(46)]
SW, SH = W // 4, H // 4
yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
yy /= SH; xx /= SW

def background(t):
    beat_ph = (t % BEAT) / BEAT
    pulse = math.exp(-beat_ph * 5.0)
    # vertical gradient
    top = np.array([16, 6, 36], np.float32)
    bot = np.array([70, 6, 30], np.float32)
    img = top[None, None, :] * (1 - yy[..., None]) + bot[None, None, :] * yy[..., None]
    # moving glows
    for (cx, cy, rad, col, k) in [
        (0.5 + 0.35 * math.sin(t * 0.7), 0.30 + 0.12 * math.cos(t * 0.5), 0.55, (255, 60, 40), 70),
        (0.5 + 0.40 * math.cos(t * 0.55), 0.72 + 0.10 * math.sin(t * 0.9), 0.60, (90, 60, 255), 60),
    ]:
        d = ((xx - cx) ** 2 + ((yy - cy) * 1.8) ** 2) ** 0.5
        g = np.clip(1 - d / rad, 0, 1) ** 2
        img += g[..., None] * np.array(col, np.float32)[None, None, :] * (k + 25 * pulse) / 255.0
    # diagonal light streaks
    s = np.sin((xx * 1.0 + yy * 0.6) * 18 - t * 1.2)
    img += np.clip(s, 0, 1)[..., None] * 5.0
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(im)
    for (px, py, sp, r) in PARTS:
        y = (py - t * sp) % 1.0
        x = px + 0.02 * math.sin(t * 1.3 + px * 9)
        a = 0.5 + 0.5 * math.sin(t * 2 + px * 20)
        c = int(120 + 100 * a)
        d.ellipse((x * SW - r / 2, y * SH - r / 2, x * SW + r / 2, y * SH + r / 2), fill=(c, c, c))
    return im.resize((W, H), Image.BICUBIC)

# ---------------------------------------------------------------- drawing pieces
def rrect(d, box, r, fill=None, outline=None, width=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def center_text(d, xy, text, f, fill, stroke=0, stroke_fill=(0, 0, 0), anchor="mm"):
    d.text(xy, text, font=f, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=stroke_fill)

def draw_header(im, d, t):
    beat_ph = (t % BEAT) / BEAT
    pulse = math.exp(-beat_ph * 6.0)
    # BREAKING badge
    slide = ease_out(t / 0.35)
    bx = int(-460 + slide * 520)
    rrect(d, (bx, 190, bx + 400, 270), 18, fill=(225, 18, 40))
    blink = int(t * 2.5) % 2 == 0
    d.ellipse((bx + 26, 217, bx + 52, 243), fill=(255, 255, 255) if blink else (255, 150, 150))
    center_text(d, (bx + 235, 231), "BREAKING", font(44), (255, 255, 255))
    # right label
    lab = CFG["badge"]
    f = font(34, MED)
    tw = f.getlength(lab)
    rx = int(W + 40 - slide * (tw + 100))
    rrect(d, (rx - 24, 196, rx + tw + 24, 264), 16, fill=(0, 0, 0))
    center_text(d, (rx + tw / 2, 230), lab, f, (255, 255, 255))

def draw_vs(im, d, t):
    beat_ph = (t % BEAT) / BEAT
    pulse = math.exp(-beat_ph * 6.0)
    a = ease_out_back((t - 0.25) / 0.6)
    off = int((1 - a) * 560)
    y0, y1 = 340, 700
    # left card
    for (x0, x1, col, big, sub, s) in [
        (50 - off, 480 - off, (0, 200, 255), CFG["left"][0], CFG["left"][1], -1),
        (600 + off, 1030 + off, (255, 140, 0), CFG["right"][0], CFG["right"][1], 1),
    ]:
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle((x0, y0, x1, y1), 36, fill=(8, 8, 20, 205), outline=col + (255,), width=6)
        im.paste(Image.alpha_composite(im.convert("RGBA"), sh).convert("RGB"))
        d = ImageDraw.Draw(im)
        cx = (x0 + x1) / 2
        # initial letter ghost
        d.text((cx, (y0 + y1) / 2 + 10), big[0], font=font(330), fill=tuple(int(c * 0.28) for c in col), anchor="mm")
        center_text(d, (cx, y0 + 215), big, font(86), (255, 255, 255), stroke=0)
        center_text(d, (cx, y0 + 290), sub, font(40 if len(sub) < 8 else 32), col)
    d = ImageDraw.Draw(im)
    # VS badge
    sc = 1 + 0.12 * pulse
    r = int(78 * sc)
    sx = 540 + random.uniform(-2, 2) * pulse
    sy = (y0 + y1) / 2
    d.ellipse((sx - r - 8, sy - r - 8, sx + r + 8, sy + r + 8), fill=(255, 255, 255))
    d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(225, 18, 40))
    center_text(d, (sx, sy + 2), "VS", font(int(74 * sc)), (255, 255, 255))
    # context pill
    pill = CFG["pill"]
    f = font(34, MED)
    tw = f.getlength(pill)
    pa = ease_out((t - 0.8) / 0.4)
    if pa > 0:
        px0 = 540 - tw / 2 - 30
        rrect(d, (px0, 760, px0 + tw + 60, 826), 33, fill=(255, 255, 255))
        center_text(d, (540, 793), pill, f, (20, 10, 40))

def draw_caption(im, d, t, idx):
    text, dur, style = CHUNKS[idx]
    st = starts[idx]
    dd = dur * SPEED
    lt = t - st
    size = BASE
    if style == "big":
        size = 118
    elif style == "hook":
        size = 104
    lines = layout(text, size)
    n_words = sum(len(l) for l in lines)
    # per-word timing proportional to length
    allw = [w for l in lines for w in l]
    weights = np.array([len(w) + 2 for w in allw], float)
    cum = np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * dd * 0.94
    active = max(i for i in range(len(allw)) if lt >= cum[i] - 1e-6) if lt >= 0 else 0
    # pop in
    pop = ease_out_back(lt / 0.16)
    scale = 0.55 + 0.45 * pop
    f0 = font(size)
    lh = size * 1.25
    cy = 1230 if style != "hook" else 1100
    total_h = lh * len(lines)
    wi = 0
    for li, line in enumerate(lines):
        gapb = f0.getlength(" ") * 1.45
        line_w = sum(f0.getlength(w) for w in line) + gapb * (len(line) - 1)
        x = 540 - line_w * scale / 2
        y = cy - total_h * scale / 2 + lh * scale * (li + 0.5)
        for w in line:
            is_act = (wi == active)
            fs = size * scale * (1.05 if is_act else 1.0)
            f = font(fs)
            wl = f0.getlength(w) * scale
            sp_w = gapb * scale
            col = (255, 255, 255)
            if is_act:
                col = (255, 214, 0)
            if style == "big" and is_act:
                col = (255, 70, 70)
            if style == "cta" and is_act:
                col = (80, 255, 160)
            d.text((x + wl / 2, y), w, font=f, fill=col, anchor="mm",
                   stroke_width=max(4, int(size * 0.09 * scale)), stroke_fill=(0, 0, 0))
            x += wl + sp_w
            wi += 1

def draw_tag(im, d, t, t0):
    a = ease_out_back((t - t0) / 0.4)
    if a <= 0:
        return
    s = "REPORTS ONLY  •  NOT OFFICIALLY CONFIRMED"
    f = font(32)
    tw = f.getlength(s)
    h = 78 * min(a, 1.0)
    y = 1510
    rrect(d, (540 - tw / 2 - 40, y - h / 2, 540 + tw / 2 + 40, y + h / 2), 20, fill=(255, 193, 7))
    if a > 0.7:
        center_text(d, (540, y + 1), s, f, (30, 20, 0))

def draw_cta(im, d, t, t0):
    a = ease_out_back((t - t0) / 0.5)
    if a <= 0:
        return
    beat_ph = (t % BEAT) / BEAT
    pulse = math.exp(-beat_ph * 6.0)
    y = 1500
    for (x0, x1, col, label) in [(70, 520, (0, 200, 255), CFG["buttons"][0]), (560, 1010, (255, 140, 0), CFG["buttons"][1])]:
        sc = a * (1 + 0.03 * pulse)
        cx = (x0 + x1) / 2
        w2 = (x1 - x0) / 2 * sc
        rrect(d, (cx - w2, y - 62 * sc, cx + w2, y + 62 * sc), 34, fill=col)
        center_text(d, (cx, y + 2), label, font(int(46 * sc)), (10, 10, 25))
    # arrow hint "comment"
    f = font(36, MED)
    center_text(d, (540, 1610), CFG["comment_line"], f, (255, 255, 255))

def flash(im, t):
    if t < 0.14:
        a = (1 - t / 0.14) * 0.85
        ov = Image.new("RGB", (W, H), (255, 255, 255))
        return Image.blend(im, ov, a)
    return im

def frame(t):
    im = background(t)
    # chunk index
    idx = max(i for i in range(len(CHUNKS)) if t >= starts[i] - 1e-9)
    d = ImageDraw.Draw(im)
    draw_header(im, d, t)
    draw_vs(im, d, t)
    d = ImageDraw.Draw(im)
    tag_idx = next(i for i, c in enumerate(CHUNKS) if c[2] == "tag")
    cta_idx = next(i for i, c in enumerate(CHUNKS) if c[2] == "cta")
    if starts[tag_idx] <= t < starts[cta_idx] - 0.1:
        draw_tag(im, d, t, starts[tag_idx])
    if t >= starts[cta_idx]:
        draw_cta(im, d, t, starts[cta_idx])
    draw_caption(im, d, t, idx)
    # outro fade
    im = flash(im, t)
    if t > TOTAL - 0.25:
        a = (t - (TOTAL - 0.25)) / 0.25
        im = Image.blend(im, Image.new("RGB", (W, H), (0, 0, 0)), min(a, 1) * 0.9)
    return im

# ---------------------------------------------------------------- audio bed
def make_bed(path, total):
    sr = 44100
    n = int(sr * (total + 0.3))
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)
    def add(sig, at):
        i = int(at * sr)
        if i >= n: return
        j = min(n, i + len(sig))
        out[i:j] += sig[: j - i]
    # impact at 0
    tt = np.arange(int(sr * 1.4)) / sr
    boom = np.sin(2 * np.pi * (38 * tt + 40 * (1 - np.exp(-6 * tt)) / 6)) * np.exp(-tt * 3.2) * 0.9
    add(boom, 0.0)
    nb = rng.standard_normal(int(sr * 0.9)).astype(np.float32)
    tt2 = np.arange(len(nb)) / sr
    add(nb * np.exp(-tt2 * 6) * 0.3, 0.0)
    # kick
    tk = np.arange(int(sr * 0.35)) / sr
    kick = np.sin(2 * np.pi * (48 * tk + 100 * (1 - np.exp(-28 * tk)) / 28)) * np.exp(-tk * 11) * 0.8
    # clap
    tc = np.arange(int(sr * 0.2)) / sr
    clap = np.diff(rng.standard_normal(len(tc) + 1)).astype(np.float32) * np.exp(-tc * 28) * 0.18
    # hat
    th = np.arange(int(sr * 0.07)) / sr
    hat = np.diff(rng.standard_normal(len(th) + 1)).astype(np.float32) * np.exp(-th * 80) * 0.12
    b = 0
    while b * BEAT < total + 0.2:
        at = b * BEAT
        if b >= 3:  # leave first beats to the impact
            add(kick, at)
            if b % 2 == 1:
                add(clap, at)
            add(hat, at + BEAT / 2)
            if b % 4 == 3:
                add(hat, at + BEAT * 0.75)
        b += 1
    # bass + pad
    t_all = np.arange(n) / sr
    ph = (t_all % BEAT) / BEAT
    duck = 1 - 0.75 * np.exp(-ph * 9)
    bar = (t_all / (BEAT * 4)).astype(int) % 4
    freqs = np.array([55.0, 55.0, 65.41, 49.0])[bar]
    phase = 2 * np.pi * np.cumsum(freqs) / sr
    bass = np.tanh(2.2 * np.sin(phase)) * 0.22 * duck
    bass[: int(sr * 0.5)] *= np.linspace(0, 1, int(sr * 0.5))
    pad = (np.sin(2 * np.pi * 220 * t_all) + np.sin(2 * np.pi * 261.63 * t_all) + np.sin(2 * np.pi * 329.63 * t_all)) / 3
    pad *= 0.06 * (0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * t_all)) * duck
    out += bass.astype(np.float32) + pad.astype(np.float32)
    # chunk tick/whoosh
    tw = np.arange(int(sr * 0.16)) / sr
    for s0 in starts:
        w = rng.standard_normal(len(tw)).astype(np.float32)
        w = np.convolve(w, np.ones(24) / 24, mode="same")
        add(w * np.sin(np.pi * tw / tw[-1]) * 0.35, max(0, s0 - 0.04))
    # fade
    f = int(sr * 0.35)
    out[-f:] *= np.linspace(1, 0, f)
    out /= max(0.01, np.abs(out).max()) / 0.85
    if VOICE:
        out *= 0.35  # sit under the voice
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

bed = os.path.join(os.path.dirname(os.path.abspath(OUT)), "bed_" + os.path.basename(OUT) + ".wav")
make_bed(bed, TOTAL)

# ---------------------------------------------------------------- render
cmd = ["ffmpeg", "-y", "-loglevel", "error",
       "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
       "-i", bed]
if VOICE:
    cmd += ["-i", VOICE, "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest:normalize=0[a]", "-map", "0:v", "-map", "[a]"]
else:
    cmd += ["-map", "0:v", "-map", "1:a"]
cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{TOTAL:.2f}", "-movflags", "+faststart", OUT]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
nfr = int(TOTAL * FPS)
for i in range(nfr):
    random.seed(i)
    p.stdin.write(frame(i / FPS).tobytes())
    if i % 120 == 0:
        print(f"frame {i}/{nfr}", flush=True)
p.stdin.close()
p.wait()
if p.returncode != 0:
    sys.exit("ffmpeg failed")
print("done", OUT, f"{TOTAL:.1f}s")
