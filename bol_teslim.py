import csv, os, re
from collections import OrderedDict

SRC = "entes_katalog_birlesik_1.csv"
OUT = "veri"

# kategori -> list of (seri, model, {ozellik:deger})
kats = OrderedDict()

with open(SRC, encoding="utf-8-sig", newline="") as f:
    r = csv.DictReader(f)
    for row in r:
        kat = row["Kategori"].strip()
        seri = row["Seri"].strip()
        model = row["Model"].strip()
        ozet = row["Özellikler"].strip()
        feats = {}
        if ozet:
            for part in ozet.split("|"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    feats[k.strip()] = v.strip()
        kats.setdefault(kat, []).append((seri, model, feats))

def slug(s):
    s = s.lower()
    tr = str.maketrans("çğıöşü", "cgiosu")
    s = s.translate(tr)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

summary = []
for kat, rows in kats.items():
    # o kategorideki tum ozellik anahtarlarinin birlesimi (ilk gorulme sirasi korunur)
    cols = []
    for _, _, feats in rows:
        for k in feats:
            if k not in cols:
                cols.append(k)
    header = ["Kategori", "Seri", "Model"] + cols
    path = os.path.join(OUT, slug(kat) + ".csv")
    with open(path, "w", encoding="utf-8", newline="") as g:
        w = csv.writer(g)
        w.writerow(header)
        for seri, model, feats in rows:
            line = [kat, seri, model] + [feats.get(c, "Belirsiz") for c in cols]
            w.writerow(line)
    summary.append((kat, len(rows), len(cols), path))

print("=== URETILEN DOSYALAR ===")
for kat, nrows, ncols, path in summary:
    print(f"{os.path.basename(path):45s} model={nrows:3d} kolon={ncols}")
print(f"\nTOPLAM {len(summary)} kategori dosyasi")
