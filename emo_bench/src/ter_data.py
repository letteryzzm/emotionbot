"""文本数据：构建 CPED 的 meta.csv（MELD 的文本已在 prep.py 的 meta 里）。

CPED 13 类 -> 7 类：relaxed / positive-other / negative-other 语义不在 7 类里，记为 other（7 类指标里排除）。
"""
import os

import pandas as pd

from common import WORK

CPED7 = {"neutral": "neutral", "happy": "happy", "grateful": "happy", "anger": "angry", "sadness": "sad",
         "depress": "sad", "fear": "fear", "worried": "fear", "disgust": "disgust", "astonished": "surprise",
         "relaxed": "other", "positive-other": "other", "negative-other": "other"}

if __name__ == "__main__":
    root = os.path.expanduser("~/emo/data/cped/data/CPED")
    rows = []
    for sp in ["train", "valid", "test"]:
        d = pd.read_csv(f"{root}/{sp}_split.csv")
        for r in d.itertuples():
            rows.append(dict(key=r.Utterance_ID, split=sp, dialogue=r.Dialogue_ID, utt=int(r.Utterance_ID.split("_")[-1]),
                             speaker=r.Speaker, native=r.Emotion, sentiment=r.Sentiment, label7=CPED7[r.Emotion],
                             text=str(r.Utterance)))
    m = pd.DataFrame(rows)
    os.makedirs(f"{WORK}/cped", exist_ok=True)
    m.to_csv(f"{WORK}/cped/meta.csv", index=False)
    print(m.groupby("split").label7.value_counts().unstack())
