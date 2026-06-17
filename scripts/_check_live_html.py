import re
import urllib.request

html = urllib.request.urlopen("https://teleautomation.online/", timeout=20).read().decode()
print("assets:", re.findall(r"/assets/[^\"']+", html))
