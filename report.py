import os, re, json
from openai import OpenAI

DEBUG = False  # يطبع رد الموديل وسبب الرفض (خليه False بعد ما تخلصي)

KEY = os.environ.get("OPENROUTER_API_KEY")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=KEY) if KEY else None
MODEL = "openrouter/free"

LOW, HIGH = 33, 66
AR = {"low": "منخفض", "medium": "متوسط", "high": "مرتفع"}
AR_H = {"drought": "الجفاف", "fire": "الحريق", "flood": "الفيضان"}
LEVEL_AR = {
    "low": ["منخفض", "منخفضة", "ضعيف", "ضعيفة"],
    "medium": ["متوسط", "متوسطة"],
    "high": ["مرتفع", "مرتفعة", "عالي", "عالية", "عالٍ"],
}
LEAKS = ["area_pct", "(probability)", "type:", "kind:", "scene:", "area percentage"]
DISC_HEAD = {"ar": "تنبيه: نموذج تجريبي.", "en": "Note: demo model."}
DISC_FIRE = {"ar": "خطر الحريق مبني على مؤشر طقس وليس سجلات حرائق فعلية.",
             "en": "Fire risk is a weather-based proxy, not real fire records."}
DISC_CV = {"ar": "المساحة المغمورة تقدير من نموذج رؤية حاسوبية baseline (متوسط IoU حوالي 46%، وقد يفوّت "
                 "مساحات صغيرة أو كبيرة) على صورة عيّنة من داتا عامة، وليست خاصة بالمنطقة المذكورة.",
           "en": "Flooded area is an estimate from a baseline computer-vision model (mean IoU about 46%, "
                 "it may miss small or large areas) on a sample image from a public dataset, "
                 "not specific to the region named."}
DISC_TAIL = {"ar": "النسب غير معايرة ولا يُستخدم لقرارات طوارئ حقيقية.",
             "en": "Probabilities are uncalibrated. Not for real emergency decisions."}


def level(p):
    return "low" if p < LOW else "medium" if p < HIGH else "high"


def build_facts(d):
    hazards = []
    for h in d["hazards"]:
        if h.get("kind") == "area_pct":
            hazards.append({"type": h["type"], "kind": "area_pct",
                            "area_pct": round(h["value"], 1),
                            "scene": h.get("scene", "sample")})
        else:
            hazards.append({"type": h["type"], "kind": "probability",
                            "prob": round(h["prob"]), "level": level(h["prob"]),
                            "horizon_days": h["horizon_days"]})
    return {"region": d["region"], "date": d["date"], "hazards": hazards}


def disclaimer(facts, lang):
    types = {h["type"] for h in facts["hazards"]}
    kinds = {h["kind"] for h in facts["hazards"]}
    parts = [DISC_HEAD[lang]]
    if "fire" in types:
        parts.append(DISC_FIRE[lang])
    if "area_pct" in kinds:
        parts.append(DISC_CV[lang])
    parts.append(DISC_TAIL[lang])
    return " ".join(parts)


def nums(t):
    t = t.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    return set(re.findall(r"\d+", t))


DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def has_horizon(text, n):
    t = text.translate(DIGITS)
    return re.search(r"(?<!\d)%d(?!\d)\s*-?\s*(?:أيام|ايام|يوم|days?)" % n, t, re.I) is not None


def need_numbers(facts):
    need = set()
    for h in facts["hazards"]:
        if h["kind"] == "area_pct":
            need.add(str(int(h["area_pct"])))
        else:
            need.add(str(h["prob"]))
            need.add(str(h["horizon_days"]))
    return need


def parse_json(txt):
    a, b = txt.find("{"), txt.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("no JSON in reply: " + txt[:80])
    return json.loads(txt[a:b + 1])


def reject(why):
    if DEBUG:
        print("REJECT:", why)
    return False


def validate(rep, facts):
    allowed = nums(json.dumps(facts))
    need = need_numbers(facts)
    for lang in ("ar", "en"):
        t = rep.get(lang, "")
        if not isinstance(t, str) or not t:
            return reject("missing text for " + lang)
        extra = nums(t) - allowed
        if extra:
            return reject("extra numbers in %s: %s" % (lang, sorted(extra)))
        missing = need - nums(t)
        if missing:
            return reject("missing numbers in %s: %s" % (lang, sorted(missing)))
    if facts["region"].lower() not in rep["en"].lower():
        return reject("region name missing in English")
    for lang in ("ar", "en"):
        low = rep[lang].lower()
        for bad in LEAKS:
            if bad in low:
                return reject("technical term leaked in %s: %s" % (lang, bad))
    if any(h["kind"] == "area_pct" for h in facts["hazards"]):
        if "sample" not in rep["en"].lower():
            return reject("english text does not say the flood area is from a sample image")
        if "عينة" not in rep["ar"].replace("ّ", ""):
            return reject("arabic text does not say the flood area is from a sample image")
        if "flood risk" in rep["en"].lower() or "خطر الفيضان" in rep["ar"]:
            return reject("flood area described as a risk")
        if not re.search(r"of the (?:\w+ ){0,2}(?:image|scene)", rep["en"].lower()):
            return reject("english text does not say the flood percent is 'of the image'")
        if not re.search(r"من\s+(?:مساحة\s+)?(?:ال)?(?:صورة|مشهد)", rep["ar"]):
            return reject("arabic text does not say the flood percent is 'من الصورة'")
    for h in facts["hazards"]:
        if h["kind"] == "probability":
            if not has_horizon(rep["en"], h["horizon_days"]):
                return reject("english text is missing the time horizon for " + h["type"])
            if not has_horizon(rep["ar"], h["horizon_days"]):
                return reject("arabic text is missing the time horizon for " + h["type"])
    for h in facts["hazards"]:
        if h["kind"] != "probability":
            continue
        if not any(w in rep["ar"] for w in LEVEL_AR[h["level"]]):
            return reject("arabic level word missing for " + h["type"])
        if h["level"] not in rep["en"].lower():
            return reject("english level word missing for " + h["type"])
    return True


def template(facts):
    ar, en = [], []
    for h in facts["hazards"]:
        name = AR_H.get(h["type"], h["type"])
        if h["kind"] == "area_pct":
            ar.append("تحليل الأقمار الصناعية (صورة عيّنة %s): المساحة المغمورة المقدّرة %.1f%% من الصورة."
                      % (h["scene"], h["area_pct"]))
            en.append("Satellite analysis (sample scene %s): estimated flooded area %.1f%% of the image."
                      % (h["scene"], h["area_pct"]))
        else:
            ar.append("خطر %s: %d%% (%s) خلال %d أيام." % (name, h["prob"], AR[h["level"]], h["horizon_days"]))
            en.append("%s risk: %d%% (%s) within %d days." % (h["type"].title(), h["prob"], h["level"], h["horizon_days"]))
    head = facts["region"] + " - " + facts["date"] + "\n"
    return {"ar": head + "\n".join(ar), "en": head + "\n".join(en)}


def generate(facts):
    if client is None:
        return template(facts), "template"
    prompt = f"""اكتب تقرير طوارئ قصير بالعربي والإنجليزي من الحقائق دي فقط.
ممنوع تضيف أي رقم أو مكان أو سبب مش موجود فيها.
- الخطر اللي نوعه probability: اذكر النسبة ومستوى الخطر. مستوى الخطر في العربي بالكلمات دي بالظبط: منخفض أو متوسط أو مرتفع. وفي الإنجليزي: low أو medium أو high.
- الخطر اللي نوعه area_pct: ده مساحة مغمورة تقديرية من تحليل صورة قمر صناعي عيّنة، مش من المنطقة المذكورة. اذكرها كنسبة من الصورة، ولا تقل إنها في المنطقة، ولا تدّيها مستوى خطر.
- اذكر اسم المنطقة (بالإنجليزي كما هو في الحقائق).
- اكتب الأرقام زي ما هي في الحقائق.
- لكل خطر نوعه probability اذكر المدى الزمني بالأيام من horizon_days، مثلًا "خلال 7 أيام" بالعربي و"within 7 days" بالإنجليزي.
- اكتب جمل عادية مفهومة لإنسان، وممنوع أسماء الحقول التقنية (probability, area_pct, type, kind, scene) وممنوع تعمل قائمة بحقول.
- نسبة الفيضان قولها "من الصورة" بالعربي و"of the image" بالإنجليزي.
- في جملة الفيضان قول صراحة إنها "صورة عيّنة" بالعربي و"sample image" بالإنجليزي، وما تسميش الفيضان "خطر" ولا "risk".
الحقائق: {json.dumps(facts, ensure_ascii=False)}
ردّ JSON فقط بالشكل: {{"ar": "...", "en": "..."}}"""
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=MODEL, temperature=0,
                messages=[{"role": "user", "content": prompt}])
            txt = r.choices[0].message.content or ""
            if DEBUG:
                print("MODEL SAID:", txt)
            rep = parse_json(txt)
            if validate(rep, facts):
                return rep, "llm"
        except Exception as e:
            print("ERROR:", e)
    return template(facts), "template"


def make_report(data):
    facts = build_facts(data)
    rep, src = generate(facts)
    rep = {k: rep[k] + "\n\n" + disclaimer(facts, k) for k in ("ar", "en")}
    return rep, src


if __name__ == "__main__":
    sample = {"region": "Delta", "date": "2025-03-15",
              "hazards": [{"type": "drought", "prob": 78.4, "horizon_days": 7},
                          {"type": "fire", "prob": 41.2, "horizon_days": 7}]}
    rep, src = make_report(sample)
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(rep["ar"] + "\n\n" + "=" * 40 + "\n\n" + rep["en"])
    print(src, "saved in report.txt")
