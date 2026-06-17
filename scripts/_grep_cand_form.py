import re

t = open(
    r"C:\Users\codet\TelegramForward\dashboard\src\candidates\candidatesModule.jsx",
    encoding="utf-8",
).read()
for label in ("Service", "Round", "domestic", "non_domestic", "expected", "Consultancy"):
    i = t.find(label)
    if i >= 0:
        print("===", label, "===")
        print(t[max(0, i - 40) : i + 400])
        print()
