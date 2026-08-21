import re
import urllib.request

UA = "PerviyAgent/0.4 (+local)"
html = urllib.request.urlopen(
    urllib.request.Request(
        "https://career.habr.com/vacancies?q=QA&remote=true&qualification=intern",
        headers={"User-Agent": UA},
    ),
    timeout=45,
).read().decode("utf-8", errors="replace")

for m in re.finditer(
    r'href="/vacancies/(\d+)"[^>]*>.*?aria-label="([^"]+)"',
    html,
    flags=re.DOTALL,
):
    print(m.group(1), m.group(2)[:70])
    if m.start() > 50000:
        break

print("---")
for m in re.finditer(
    r'aria-label="([^"]+)"[^>]*href="/vacancies/(\d+)"',
    html,
):
    print(m.group(2), m.group(1)[:70])

print("--- datetime blocks")
for m in re.finditer(
    r'/vacancies/(\d+)".*?datetime="(\d{4}-\d{2}-\d{2})',
    html,
    flags=re.DOTALL,
):
    print(m.group(1), m.group(2))
