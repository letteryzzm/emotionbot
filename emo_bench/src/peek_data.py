import pyarrow.parquet as pq, glob, json, os
os.chdir(os.path.expanduser("~/emo/data"))
f = sorted(glob.glob("ravdess_av/data/*.parquet"))[0]
p = pq.ParquetFile(f); print(p.schema_arrow); print("rows", p.metadata.num_rows, "rowgroups", p.num_row_groups)
t = p.read_row_group(0).slice(0, 2).to_pylist()
for r in t:
    print({k: (v if not isinstance(v, (bytes, dict, list)) else (type(v).__name__, list(v.keys()) if isinstance(v, dict) else len(v))) for k, v in r.items()})
print(open("ravdess_av/README.md").read()[:800])
for fn in glob.glob("emobox/data/cremad/fold_1/*.jsonl") + glob.glob("emobox/data/meld/fold_1/*.jsonl"):
    L = open(fn).read().splitlines(); print(fn, len(L)); print(L[0][:300])
print(os.listdir("cped/data/CPED")); print(open("cped/data/CPED/test_split.csv").read()[:600])
