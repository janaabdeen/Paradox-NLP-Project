# PARADOX — NLP Report Module (Demo) / وحدة التقارير (NLP)

Turns structured hazard outputs (time-series + computer vision) into a short emergency report in **Arabic and English**, with a validation layer that checks the text against the input numbers.

يحوّل مخرجات الـ TS والـ CV لتقرير طوارئ قصير بالعربي والإنجليزي، مع طبقة تحقق بتقارن النص بالأرقام الأصلية.

> ⚠️ **Demo only / تجريبي فقط.** Not an operational warning system and not for real emergency decisions. / ليس نظام إنذار تشغيلي ولا يصلح لاتخاذ قرارات حقيقية.

## How it works / إزاي بيشتغل

1. **Collect** – drought and fire probabilities from the time-series module (CSV), flooded area from the CV module (JSON).
2. **Risk level** – computed by code (low / medium / high from fixed thresholds), not by the language model.
3. **Generate** – an LLM (via OpenRouter) writes the report from those facts only.
4. **Validate** – the text is rejected if it adds or omits numbers, drops the risk level or the 7-day horizon, leaks internal field names, calls the flood area a "risk", or does not say the flood number is from a sample image.
5. **Fallback** – after 3 failed attempts a fixed template is used, so the output is always consistent with the inputs.
6. **Output** – bilingual report with automatic caveats.

## Files

| File | Purpose |
|---|---|
| `report.py` | Core: facts → prompt → LLM → validation → fallback |
| `full_report.py` | Combines TS CSV + CV JSON and writes `report_full.txt` |
| `cv_demo.json` | Flooded-area numbers for 5 sample images (see below) |
| `example_output.txt` | Example of a generated report |

## Quick start

```bash
pip install -r requirements.txt

# Windows (CMD)
set OPENROUTER_API_KEY=your_key_here
# macOS / Linux
export OPENROUTER_API_KEY=your_key_here
```

Download `delta_predictions.csv` from the `data` folder of the TS repo (link below) into this folder, then:

```bash
python full_report.py                              # delta, 2025-03-15, sample_2
python full_report.py delta 2025-03-15 sample_1    # region, date, CV sample
```

Without an API key the script still runs and uses the fixed template. `MODEL` in `report.py` is `openrouter/free`, which picks a free model, so wording can vary between runs.

## Inputs

**Time-series (TS):** `<region>_predictions.csv` with columns `date, drought, fire` (values 0–1, multiplied by 100). Horizon: 7 days.

**Computer vision (CV):** `cv_demo.json`. The CV repo does not export numbers, so the flooded-area values were measured by counting pixel colors in the "MVP Prediction" panels of the 5 demo images in the CV repo README. Assumed mapping (from the class order and colormap, not confirmed by the CV authors): dark blue = land, green = flood, red = permanent water. Values are approximate: they are a percentage of the whole panel, so no-data pixels are not excluded.

The flood number is an **estimated flooded area as % of a sample image**, not a probability, and it comes from a public dataset, not from the Delta region. The report says so explicitly.

## Limitations

- Fire risk is a weather-based proxy, not real fire records; probabilities are uncalibrated.
- The CV baseline has mean flood IoU 46.23% and F1 59.80% (per its README) and can miss small or large flooded areas. This module reports what it is given and does not correct upstream errors (e.g. `sample_1` is predicted ~0.6% while the ground truth is much larger).
- Validation catches numbers, risk levels, horizon and some misleading wording. It does not guarantee every sentence is correct.
- The report is not tied to a real region/date for the flood part.

## Related repos

- Time-series module: https://github.com/osoo1234/Paradox-TS-Project-1
- Flood detection (CV): https://github.com/zizo7amada20/flood-detection-cv

---

## بالعربي

- **المدخلات:** احتمال الجفاف والحريق من ملف توقعات الـ TS، ومساحة الفيضان المقدّرة من صور عيّنة الـ CV.
- **مستوى الخطر** بيتحسب بالكود، والموديل اللغوي بيكتب الصياغة بس.
- **التحقق:** أي تقرير فيه رقم زيادة أو ناقص، أو من غير مستوى الخطر أو "خلال 7 أيام"، أو بيسمّي الفيضان "خطر"، بيتم رفضه، وبعد 3 محاولات بننزل على قالب ثابت.
- **رقم الفيضان** نسبة مساحة من صورة عيّنة من داتا عامة، مش احتمال ومش خاص بالدلتا، وقياسه تقريبي من صور الـ README.
- الحريق مبني على مؤشر طقس مش حرائق فعلية، والنسب غير معايرة.
- **التشغيل:** `pip install -r requirements.txt`، وسجّلي `OPENROUTER_API_KEY`، وحمّلي `delta_predictions.csv` من ريبو الـ TS، وبعدين `python full_report.py`.
