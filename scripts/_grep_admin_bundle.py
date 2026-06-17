import re
import urllib.request

h = urllib.request.urlopen("https://teleautomation.online/").read().decode()
b = re.search(r"/assets/app-[^\"]+\.js", h).group().split("/")[-1]
t = urllib.request.urlopen(f"https://teleautomation.online/assets/{b}").read().decode("utf-8", "replace")
print("bundle", b)
for pat in ["/admin/", "admin/overview", "HTTP 404", "Overview"]:
    print(pat, t.count(pat))
urls = sorted(set(re.findall(r'"(/admin/[^"]+)"', t)))
print("admin urls", len(urls))
for u in urls:
    print(" ", u)
# metrics paths
for u in sorted(set(re.findall(r'"(/metrics/[^"]+)"', t))):
    print(" ", u)
