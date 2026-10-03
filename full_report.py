import csv, json, sys
from report import make_report

# تشغيل عادي:            python full_report.py
# منطقة/تاريخ/عيّنة تانية: python full_report.py delta 2025-03-15 sample_2
REGION = sys.argv[1] if len(sys.argv) > 1 else "delta"
DATE = sys.argv[2] if len(sys.argv) > 2 else "2025-03-15"
SAMPLE = sys.argv[3] if len(sys.argv) > 3 else "sample_2"

with open(REGION.lower() + "_predictions.csv", encoding="utf-8") as f:
    rows = list(csv.reader(f))
found = None
for row in rows[1:]:
    if row[0] == DATE:
        found = row
if found is None:
    print("DATE NOT FOUND in", REGION)
    sys.exit()

with open("cv_demo.json", encoding="utf-8") as f:
    cv = json.load(f)
if SAMPLE not in cv["samples"]:
    print("UNKNOWN SAMPLE. choose one of:", list(cv["samples"]))
    sys.exit()
scene = cv["samples"][SAMPLE]

data = {"region": REGION.title(), "date": DATE,
        "hazards": [
            {"type": "drought", "kind": "probability", "prob": float(found[1]) * 100, "horizon_days": 7},
            {"type": "fire", "kind": "probability", "prob": float(found[2]) * 100, "horizon_days": 7},
            {"type": "flood", "kind": "area_pct", "value": scene["pred_flood_area_pct"], "scene": SAMPLE}]}

rep, src = make_report(data)
with open("report_full.txt", "w", encoding="utf-8") as f:
    f.write(rep["ar"] + "\n\n" + "=" * 40 + "\n\n" + rep["en"])
print(src, "saved in report_full.txt")
