import re

html = open("logs/rabota-sample.html", encoding="utf-8").read()
part = html.split('class="vacancy-card--')[1]
for pat in [r"\d{4}-\d{2}-\d{2}", r"publication", r"дней назад", r"месяц"]:
    m = re.search(pat, part, re.I)
    print(pat, m.group(0) if m else None)
