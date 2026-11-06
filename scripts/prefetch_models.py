"""把模型权重提前拉到本地，避免比赛现场等下载。

    python scripts/prefetch_models.py                      # 默认目录
    python scripts/prefetch_models.py --dest /opt/emo_models
    python scripts/prefetch_models.py --small              # 用 base 版 SER

默认走 ModelScope（国内直连）。默认目录：Windows 是 D:/emo_models，
Linux/macOS 是 ~/emo_models。下载完把 EMOBOT_MODEL_DIR 指向 --dest，
运行时就会加载本地目录而不是临时下载。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_DEST = os.environ.get(
    "EMOBOT_MODEL_DIR",
    "D:/emo_models" if sys.platform == "win32" else str(Path.home() / "emo_models"),
)

MODELS = {
    "sensevoice": ("iic/SenseVoiceSmall", "SenseVoiceSmall", "ASR + 情感标签"),
    "e2v-large": ("iic/emotion2vec_plus_large", "emotion2vec_plus_large", "语音情感概率"),
    "e2v-base": ("iic/emotion2vec_base", "emotion2vec_base", "语音情感概率（小）"),
}


def _download_modelscope(model_id: str, dest: Path) -> Path:
    from modelscope import snapshot_download

    return Path(snapshot_download(model_id, local_dir=str(dest)))


def _download_hf(repo_id: str, dest: Path) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo_id, local_dir=str(dest),
                                  endpoint=os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--only", nargs="*", choices=list(MODELS), help="只下指定项")
    ap.add_argument("--small", action="store_true", help="用 emotion2vec_base 代替 plus_large")
    ap.add_argument("--mirror", choices=["modelscope", "hf"], default="modelscope")
    args = ap.parse_args(argv)

    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    names = args.only or ["sensevoice", "e2v-base" if args.small else "e2v-large"]
    print(f"目标目录: {dest}\n镜像: {args.mirror}\n")

    failed = 0
    for key in names:
        model_id, sub, why = MODELS[key]
        target = dest / sub
        if target.exists() and any(target.iterdir()):
            print(f"[跳过] {sub} 已存在 ({why})")
            continue
        print(f"[下载] {model_id} -> {target} ({why})")
        try:
            if args.mirror == "modelscope":
                _download_modelscope(model_id, target)
            else:
                _download_hf(model_id, target)
            print(f"[完成] {sub}")
        except ImportError as e:
            failed += 1
            print(f"[失败] 缺少依赖 {e}；先 pip install modelscope 或 huggingface_hub")
        except Exception as e:
            failed += 1
            print(f"[失败] {model_id}: {e}")

    # EmotiEffNet 权重由库自己下载，这里预热一次
    try:
        print("[预热] emotiefflib 人脸模型…")
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer

        EmotiEffLibRecognizer(engine="torch", model_name="enet_b0_8_va_mtl", device="cpu")
        print("[完成] emotiefflib")
    except Exception as e:
        print(f"[跳过] emotiefflib 预热失败（不影响其他模型）: {e}")

    print("\n把下面一行加到环境变量（或写进 setup_env.ps1 生成的激活脚本）：")
    print(f'  EMOBOT_MODEL_DIR="{dest}"')
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
