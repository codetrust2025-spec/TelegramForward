import urllib.request

t = urllib.request.urlopen("https://teleautomation.online/assets/app-sPW-AjZE.js").read().decode("utf-8", "replace")
# error at col ~26161 in line 46 - find by searching problematic patterns
# Often minified: st.something where st should be a React import
idx = 26161
print("around 26161:", repr(t[26000:26300]))
# search "st is not" patterns - look for posting mode patch issues
for needle in ["isForwardingMode", "postingMode", "PostingModePanel", "st."]:
    c = t.count(needle)
    if c < 20 and c > 0:
        print(needle, c)
# find ReferenceError-prone: bare st. not defined as var
import re
# posting mode patch area
for m in re.finditer(r"isForwardingMode", t):
    print("ctx", t[m.start()-200:m.start()+300])
    break
