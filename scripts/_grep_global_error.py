import urllib.request

t = urllib.request.urlopen(
    "https://teleautomation.online/assets/app-Bh_EAEC2.js"
).read().decode("utf-8", "replace")

# Find main inbox layout with error banner
for needle in [
    "Select a lead to view the conversation",
    "crm-layout",
    "inbox-error",
    "global-error",
    "app-error",
    "error-banner",
]:
    print(needle, t.find(needle))

# search .message in error display - err variable near inbox main view
idx = t.find('Z==="inbox"')
print("inbox view idx", idx)
if idx > 0:
    print(t[idx : idx + 2500][:2500])
