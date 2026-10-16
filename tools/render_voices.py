#!/usr/bin/env python3
"""전자키보드 음색 샘플 만들기.

FluidR3 GM 사운드폰트(Frank Wen, MIT 라이선스)의 악기로 지구 연주가 쓰는 음(라단조 5음 음계,
A1~D7)을 하나씩 연주해 악기마다 MP3 한 개(음 하나당 칸 하나)로 저장한다.

필요: fluidsynth, ffmpeg, FluidR3_GM.sf2
    Ubuntu: sudo apt install fluidsynth fluid-soundfont-gm ffmpeg
    python3 tools/render_voices.py          # voices/*.mp3, voices/voices.json
    python3 tools/render_voices.py harp     # 하프만 다시
"""
import json, os, re, struct, subprocess, sys, tempfile

SF2 = os.environ.get("SF2", "/usr/share/sounds/sf2/FluidR3_GM.sf2")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "voices")
NOTES = [m for m in range(33, 99) if (m - 33) % 12 in (0, 3, 5, 7, 10)]  # A C D E G, A1..D7
LEAD = 0.12  # 칸마다 음 앞에 두는 무음

# key, GM 프로그램 번호, 칸 길이(초), 누르고 있는 시간(초, None이면 칸 끝 직전까지), 세기[, 음 목록]
VOICES = [
    ("piano",     0,   2.6, None, 100),
    ("epiano",    4,   2.4, None, 100),
    ("harpsi",    6,   1.9, None, 100),
    ("celesta",   8,   1.9, None, 105),
    ("musicbox",  10,  2.1, None, 105),
    ("vibes",     11,  2.6, None, 100),
    ("marimba",   12,  1.3, None, 110),
    ("bells",     14,  3.0, None, 100),
    ("organ",     19,  2.0, 1.3,  96),
    ("guitar",    24,  2.2, None, 105),
    ("harp",      46,  2.4, None, 105),
    ("strings",   48,  2.4, 1.5,  96),
    ("cello",     42,  2.4, 1.5,  100),
    ("choir",     52,  2.4, 1.5,  96),
    ("brass",     61,  1.7, 1.0,  100),
    ("trumpet",   56,  1.7, 1.0,  100),
    ("flute",     73,  1.9, 1.2,  100),
    ("kalimba",   108, 1.7, None, 110),
    # 심장 박자용: 라(A1)·미(E2)·라(A2)만
    ("timpani",   47,  2.2, None, 112, [33, 40, 45]),
    ("bass",      32,  1.6, None, 115, [33, 40, 45]),
]

TPS = 960  # 480 ppq at 120 bpm → 960 ticks per second


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def midi_bytes(program, slot, hold, vel, notes):
    ev = [(0, bytes([0xC0, program]))]
    for i, m in enumerate(notes):
        on = i * slot + LEAD
        off = on + (hold if hold else slot - LEAD - 0.32)
        ev.append((round(on * TPS), bytes([0x90, m, vel])))
        ev.append((round(off * TPS), bytes([0x80, m, 0])))
    ev.sort(key=lambda e: e[0])
    trk, last = b"", 0
    trk += vlq(0) + b"\xff\x51\x03" + (500000).to_bytes(3, "big")  # 120 bpm
    for t, data in ev:
        trk += vlq(t - last) + data
        last = t
    trk += vlq(round(len(notes) * slot * TPS) - last) + b"\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480) + b"MTrk" + struct.pack(">I", len(trk)) + trk


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def main():
    only = set(sys.argv[1:])  # 악기 이름을 주면 그것만 다시 만든다
    os.makedirs(OUT, exist_ok=True)
    meta_path = os.path.join(OUT, "voices.json")
    meta = {"notes": NOTES, "lead": LEAD, "voices": {}}
    if only and os.path.exists(meta_path):
        with open(meta_path) as f:
            meta["voices"] = json.load(f)["voices"]
    with tempfile.TemporaryDirectory() as tmp:
        for key, prog, slot, hold, vel, *rest in VOICES:
            if only and key not in only:
                continue
            notes = rest[0] if rest else NOTES
            mid, wav = os.path.join(tmp, key + ".mid"), os.path.join(tmp, key + ".wav")
            with open(mid, "wb") as f:
                f.write(midi_bytes(prog, slot, hold, vel, notes))
            run(["fluidsynth", "-ni", "-R", "0", "-C", "0", "-g", "0.5", "-r", "44100", "-T", "wav", "-F", wav, SF2, mid])
            det = run(["ffmpeg", "-hide_banner", "-i", wav, "-af", "pan=mono|c0=0.5*c0+0.5*c1,volumedetect", "-f", "null", "-"]).stderr
            peak = float(re.search(r"max_volume: (-?[\d.]+) dB", det).group(1))
            mp3 = os.path.join(OUT, key + ".mp3")
            run(["ffmpeg", "-hide_banner", "-y", "-i", wav, "-af", f"pan=mono|c0=0.5*c0+0.5*c1,volume={-1.0 - peak:.2f}dB",
                 "-t", f"{len(notes) * slot:.3f}", "-ar", "32000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
            meta["voices"][key] = {"program": prog, "slot": slot}
            if rest:
                meta["voices"][key]["notes"] = notes
            print(f"{key:9s} GM {prog:3d}  peak {peak:6.1f} dB  {os.path.getsize(mp3)/1024:6.0f} KB", file=sys.stderr)
    with open(meta_path, "w") as f:
        json.dump(meta, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
