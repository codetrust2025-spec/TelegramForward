import re
import urllib.request

html = urllib.request.urlopen("https://teleautomation.online/", timeout=20).read().decode()
m = re.search(r"/assets/(app-[^\"]+\.js)", html)
print("bundle:", m.group(1) if m else "not found")
if m:
    js = urllib.request.urlopen("https://teleautomation.online/assets/" + m.group(1), timeout=30).read().decode("utf-8", "replace")
    print("embeddedfolderview:", "embeddedfolderview" in js)
    print("data-room-creds-fix:", "data-room-creds-fix" in js)
    print("offer-single-preview:", "offer-single-preview" in js)
