#!/usr/bin/env python3
"""news JSON -> free Hindi female voice -> finished Short mp4.
   python make_short.py news/x.json out/x.mp4
Voice: edge-tts hi-IN-SwaraNeural (free). Fallback: gTTS Hindi (free)."""
import asyncio, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def tts(text, path):
    try:
        import edge_tts
        asyncio.run(edge_tts.Communicate(text, "hi-IN-SwaraNeural", rate="+8%").save(path))
        if os.path.getsize(path) < 5000:
            raise RuntimeError("edge-tts output too small")
        print("voice: edge-tts Swara")
    except Exception as e:
        print("edge-tts failed (%r), falling back to gTTS" % (e,))
        from gtts import gTTS
        gTTS(text, lang="hi").save(path)
        print("voice: gTTS hi")

def main():
    cfg_path, out = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else None
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if not voice:
        voice = os.path.splitext(out)[0] + "_voice.mp3"
        tts(cfg["voice_text"], voice)
    subprocess.check_call([sys.executable, os.path.join(HERE, "build_short.py"), cfg_path, out, voice])
    print("DONE", out)

if __name__ == "__main__":
    main()
