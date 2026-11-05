
### ravdess（56 条，7 类，随机 UA = 14.3）

| 来源 | 方法 | UA | macro-F1 | n |
|---|---|---|---|---|
| 本地 | emotion2vec+ 零样本 (A)⚠ | 89.3 | 89.1 | 56 |
| 本地 | late fusion avg A+V | 89.3 | 89.7 | 56 |
| 本地 | WavLM 探针 (A) | 85.7 | 84.7 | 56 |
| 本地 | EmotiEffNet 探针 (V) | 76.8 | 77.7 | 56 |
| dashscope | qwen3.8-omni-flash av | 66.1 | 64.3 | 56 |
| openrouter | google/gemini-3.8-flash av | 66.1 | 63.9 | 56 |
| openrouter | google/gemini-3.8-flash video | 62.5 | 59.4 | 56 |
| dashscope | qwen3-omni-flash av | 57.1 | 57.3 | 56 |
| openrouter | google/gemini-3.8-flash audio | 55.4 | 57.7 | 56 |
| openrouter | minimax/minimax-m3 video | 55.4 | 51.4 | 56 |
| openrouter | moonshotai/kimi-k3 video | 53.6 | 51.1 | 56 |
| dashscope | qwen3.8-omni-flash audio | 51.8 | 53.8 | 56 |
| dashscope | qwen3-omni-flash video | 50.0 | 48.5 | 56 |
| 本地 | Qwen2.5-Omni-7B av | 41.1 | 32.1 | 56 |
| dashscope | qwen3.8-omni-flash video | 41.1 | 32.0 | 56 |
| 本地 | Qwen2.5-Omni-7B video | 35.7 | 27.9 | 56 |
| openrouter | bytedance-seed/seed-2.0-lite video | 35.7 | 34.5 | 56 |
| dashscope | qwen3-omni-flash audio | 28.6 | 24.0 | 56 |
| 本地 | DFER-CLIP 零样本 (V) | 25.0 | 21.7 | 56 |
| 本地 | Qwen2.5-Omni-7B audio | 25.0 | 20.2 | 56 |

### cremad（54 条，6 类，随机 UA = 16.7）

| 来源 | 方法 | UA | macro-F1 | n |
|---|---|---|---|---|
| 本地 | late fusion avg A+V | 94.4 | 94.1 | 54 |
| 本地 | EmotiEffNet 探针 (V) | 88.9 | 88.7 | 54 |
| 本地 | WavLM 探针 (A) | 83.3 | 83.1 | 54 |
| 本地 | emotion2vec+ 零样本 (A)⚠ | 83.3 | 83.5 | 54 |
| openrouter | google/gemini-3.8-flash av | 59.3 | 54.1 | 54 |
| openrouter | google/gemini-3.8-flash video | 57.4 | 52.1 | 54 |
| dashscope | qwen3.8-omni-flash av | 53.7 | 48.6 | 54 |
| dashscope | qwen3.8-omni-flash video | 53.7 | 50.7 | 54 |
| openrouter | minimax/minimax-m3 video | 46.3 | 41.5 | 54 |
| openrouter | moonshotai/kimi-k3 video | 44.4 | 39.2 | 54 |
| dashscope | qwen3-omni-flash video | 42.6 | 36.7 | 54 |
| dashscope | qwen3.8-omni-flash audio | 40.7 | 41.1 | 54 |
| openrouter | bytedance-seed/seed-2.0-lite video | 40.7 | 34.7 | 54 |
| 本地 | DFER-CLIP 零样本 (V) | 38.9 | 32.5 | 54 |
| openrouter | google/gemini-3.8-flash audio | 29.6 | 24.9 | 54 |
| 本地 | Qwen2.5-Omni-7B video | 27.8 | 20.1 | 54 |
| dashscope | qwen3-omni-flash audio | 22.2 | 14.6 | 54 |
| 本地 | Qwen2.5-Omni-7B av | 20.4 | 11.4 | 54 |
| 本地 | Qwen2.5-Omni-7B audio | 16.7 | 4.9 | 54 |

### meld（56 条，7 类，随机 UA = 14.3）

| 来源 | 方法 | UA | macro-F1 | n |
|---|---|---|---|---|
| dashscope | qwen3.8-omni-flash avt | 55.1 | 54.6 | 53 |
| dashscope | qwen3-omni-flash audio | 53.6 | 52.3 | 56 |
| openrouter | google/gemini-3.8-flash avt | 48.7 | 47.8 | 54 |
| openrouter | google/gemini-3.8-flash audio | 48.2 | 46.3 | 56 |
| dashscope | qwen3-omni-flash avt | 46.8 | 45.9 | 53 |
| 本地 | Qwen2.5-Omni-7B avt | 44.6 | 44.7 | 56 |
| dashscope | qwen3.8-omni-flash audio | 44.6 | 44.3 | 56 |
| dashscope | qwen3.8-omni-flash av | 44.4 | 43.2 | 53 |
| 本地 | RoBERTa 微调 (T) | 42.9 | 37.1 | 56 |
| 本地 | Qwen3-8B LoRA+ctx (T) | 42.9 | 40.5 | 56 |
| dashscope | qwen3-omni-flash av | 41.8 | 38.2 | 53 |
| 本地 | WavLM 探针 (A) | 41.1 | 39.3 | 56 |
| 本地 | late fusion avg A+V+T | 37.5 | 32.8 | 56 |
| openrouter | google/gemini-3.8-flash av | 37.5 | 37.0 | 54 |
| 本地 | Qwen2.5-Omni-7B audio | 32.1 | 29.6 | 56 |
| 本地 | Qwen2.5-Omni-7B av | 32.1 | 29.3 | 56 |
| 本地 | late fusion avg A+V+T (ASR 文本) | 32.1 | 27.6 | 56 |
| 本地 | Qwen3-8B LoRA+ctx (T, ASR 文本) | 30.4 | 25.8 | 56 |
| openrouter | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free av | 28.6 | 23.7 | 55 |
| openrouter | moonshotai/kimi-k3 video | 26.8 | 24.2 | 56 |
| openrouter | google/gemini-3.8-flash video | 25.0 | 23.1 | 54 |
| dashscope | qwen3.8-omni-flash video | 23.5 | 21.5 | 53 |
| openrouter | bytedance-seed/seed-2.0-lite video | 23.2 | 18.7 | 56 |
| openrouter | minimax/minimax-m3 video | 23.2 | 21.8 | 56 |
| dashscope | qwen3-omni-flash video | 18.7 | 13.4 | 53 |
| 本地 | EmotiEffNet 探针 (V) | 10.7 | 9.1 | 56 |

### ter_cped（56 条，7 类，随机 UA = 14.3）

| 来源 | 方法 | UA | macro-F1 | n |
|---|---|---|---|---|
| 本地 | Qwen3-8B LoRA+ctx (T) | 46.4 | 42.6 | 56 |
| openrouter | google/gemini-3.8-flash text_ctx | 46.4 | 40.2 | 56 |
| dashscope | qwen3.8-omni-flash text_ctx | 44.6 | 42.5 | 56 |
| dashscope | kimi-k3 text_ctx | 41.1 | 37.3 | 56 |
| openrouter | minimax/minimax-m3 text_ctx | 41.1 | 37.6 | 56 |
| openrouter | bytedance-seed/seed-2.0-lite text_ctx | 39.3 | 34.6 | 56 |
| 本地 | Qwen3-8B 零样本+ctx (T) | 33.9 | 30.1 | 56 |
| 本地 | RoBERTa 微调+ctx (T) | 30.4 | 30.7 | 56 |
