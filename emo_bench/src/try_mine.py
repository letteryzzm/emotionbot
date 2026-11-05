"""自录视频试跑慢层（qwen3.8-omni-flash，百炼）：每条视频带音轨发过去，要 JSON（标签、7 类概率、V/A、转写、三模态依据）。

python src/try_mine.py /Volumes/Video/voiceemotion/*.MOV [--model qwen3.8-omni-flash]
原视频不动，转成 640 宽 mp4 放 data/mine/vid_av/；结果追加到 results/mine.jsonl。
"""
import argparse
import json
import os
import subprocess
import time

from api_eval import LABEL7, ROOT, call_dashscope, load_env

PROMPT = f"""You are an emotion recognition system. Watch the video (face) and listen to its audio track (tone of voice and words).
Return ONLY a JSON object, no markdown:
{{"transcript": "<what the person says, verbatim>",
 "label": "<one of: {', '.join(LABEL7)}>",
 "probs": {{<each of the 7 labels>: <probability, sum to 1>}},
 "valence": <-1..1>, "arousal": <-1..1>,
 "face": "<facial cues you see and the emotion they suggest>",
 "voice": "<tone / prosody cues and the emotion they suggest>",
 "words": "<emotion implied by the words alone>",
 "conflict": <true if face, voice and words disagree>,
 "reason": "<one sentence: how you combined them>"}}"""


def to_mp4(src, out_dir):
    dst = f"{out_dir}/{os.path.splitext(os.path.basename(src))[0]}.mp4"
    if not os.path.exists(dst):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=640:-2,fps=30", "-c:v", "libx264",
                        "-crf", "23", "-c:a", "aac", "-ac", "1", "-ar", "16000", "-map_metadata", "-1", dst], check=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--model", default="qwen3.8-omni-flash")
    a = ap.parse_args()
    load_env()
    out_dir = f"{ROOT}/data/mine/vid_av"
    os.makedirs(out_dir, exist_ok=True)
    max_tok = 600

    for src in sorted(a.videos):
        mp4 = to_mp4(src, out_dir)
        t0 = time.time()
        ans = call_dashscope(a.model, [("video", mp4)], PROMPT, max_tokens=max_tok)
        dt = time.time() - t0
        try:
            res = json.loads(ans[ans.find("{"):ans.rfind("}") + 1])
        except ValueError:
            res = {"raw": ans}
        rec = {"file": os.path.basename(src), "model": a.model, "latency_s": round(dt, 2), **res}
        with open(f"{ROOT}/results/mine.jsonl", "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
