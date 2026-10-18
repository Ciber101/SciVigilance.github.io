#!/usr/bin/env python3
"""Read-aloud audio for the homepage "Top stories, explained" article (data/top_stories.json).
Voice: the SAME Chatterbox pipeline as the videos (voice_cb.py, sample-4 settings, pronunciations.json),
run on marc's PC GPU (machine 32b67f55-bb01-4250-8e32-bfc73e242055). Never reads URLs, sources or the AI-transparency text.

  python3 scripts/top_stories_audio.py script <dir>   -> writes <dir>/script.json for voice_cb.py (+ prints the text hash)
  python3 scripts/top_stories_audio.py finish <voice.wav>  -> encodes audio/top_stories-<hash>.mp3 (64 kbps mono),
                                                          sets "audio" in top_stories.json, deletes older mp3s
  python3 scripts/top_stories_audio.py clear          -> removes the "audio" field + mp3s (button hides)
  python3 scripts/top_stories_audio.py hash           -> prints the current text hash
  /workspace/tts/v/bin/python scripts/top_stories_audio.py kokoro
                                                      -> BOX ONLY, CPU (Oct 17+ default): Kokoro af_heart (kokoro-onnx,
                                                         models in /workspace/tts) -> wav -> same as finish. ~1.5 min.

PC steps (between script and finish), see OPERATIONS.md §3b:
  GPU check -> CopyFromBox script.json to C:\\Users\\robbi\\ShortsRender\\voicetest\\runs\\top-stories\\script.json ->
  cd C:\\Users\\robbi\\ShortsRender\\voicetest; $env:PYTHONIOENCODING="utf-8"; venv\\Scripts\\python.exe voice_cb.py runs\\top-stories ->
  CopyToBox runs\\top-stories\\voice.wav -> finish.
The hash is SHA-1 of the spoken text (lines joined with "\\n"); js/main.js recomputes it and hides the button if it differs."""
import hashlib, json, os, subprocess, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TS = os.path.join(ROOT, 'data', 'top_stories.json'); AUD = os.path.join(ROOT, 'audio')
INTRO = 'Top stories, explained.'

def lines(d):
    out = [INTRO]
    for s in d.get('stories', []):
        out.append(s['title'].rstrip('.') + '.')
        out += s.get('paragraphs', [])
    return out

def text_hash(d): return hashlib.sha1('\n'.join(lines(d)).encode('utf-8')).hexdigest()

TTS_DIR = os.environ.get('KOKORO_DIR', '/workspace/tts')
PRON_PATHS = [os.path.join(ROOT, 'pronunciations.json'), '/workspace/shorts/pc/pronunciations.json']

def respell(line):
    """Apply pronunciations.json 'say' (word respellings) and 'spell' (acronyms read letter by letter)."""
    import re
    p = next((x for x in PRON_PATHS if os.path.exists(x)), None)
    if not p: return line
    pr = json.load(open(p, encoding='utf-8')); say = pr.get('say', {}); spell = set(pr.get('spell', []))
    def fix(w):
        m = re.match(r"^(\W*)(.*?)(\W*)$", w); pre, core, post = m.groups()
        if core in say: return pre + say[core] + post
        if core in spell: return pre + ' '.join(core) + post
        return w
    return ' '.join(fix(w) for w in line.split())

def kokoro_wav(d, out, voice='af_heart'):
    import numpy as np, soundfile as sf
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(TTS_DIR, 'kokoro-v1.0.onnx'), os.path.join(TTS_DIR, 'voices-v1.0.bin'))
    parts, sr = [], 24000
    for ln in lines(d):
        a, sr = k.create(respell(ln), voice=voice, speed=1.0, lang='en-us')
        parts += [a, np.zeros(int(sr * 0.6), dtype=a.dtype)]
    sf.write(out, np.concatenate(parts), sr)

VOICE = 'Chatterbox (sample 4)'

def main():
    global VOICE
    cmd = (sys.argv[1:] or ['hash'])[0]; d = json.load(open(TS, encoding='utf-8'))
    if cmd == 'hash': print(text_hash(d)); return
    if cmd == 'script':
        o = sys.argv[2]; os.makedirs(o, exist_ok=True)
        json.dump({'lines': lines(d), 'pause': 0.6}, open(os.path.join(o, 'script.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(text_hash(d), len(lines(d)), 'lines'); return
    if cmd == 'kokoro':
        wav = '/tmp/tsaudio/kokoro.wav'; os.makedirs('/tmp/tsaudio', exist_ok=True)
        kokoro_wav(d, wav); sys.argv[2:] = [wav]; cmd = 'finish'; VOICE = 'Kokoro (af_heart)'
    if cmd in ('finish', 'clear'):
        for f in glob.glob(os.path.join(AUD, 'top_stories-*.mp3')): os.remove(f)
        d.pop('audio', None)
    if cmd == 'finish':
        h = text_hash(d); os.makedirs(AUD, exist_ok=True); mp3 = os.path.join(AUD, f'top_stories-{h[:10]}.mp3')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', sys.argv[2], '-ac', '1', '-ar', '24000',
                        '-af', 'loudnorm=I=-16:TP=-1.5', '-c:a', 'libmp3lame', '-b:a', '64k', mp3], check=True)
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp3],
                                   capture_output=True, text=True, check=True).stdout)
        d['audio'] = {'src': 'audio/' + os.path.basename(mp3), 'hash': h, 'duration': round(dur, 1), 'voice': VOICE}
        print(d['audio'])
    json.dump(d, open(TS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__': main()
