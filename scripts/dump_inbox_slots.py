#!/usr/bin/env python3
b=open(r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-BkUk1ts9.js",encoding="utf-8").read()
out=[]
i=b.find("function M8(")
out.append(b[i:i+2000])
# inbox panel where accountSlots used
for pat in ["accountSlots:s", "accountSlots:e", "accountSlots.filter", "Ti(l,", "Ti(e,"]:
    j=0
    while True:
        k=b.find(pat, j)
        if k<0: break
        if 670000 < k < 760000:
            out.append(f"\n--- {pat} @{k} ---\n{b[k:k+200]}")
        j=k+1
open(r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\inbox_slots.txt","w",encoding="utf-8").write("\n".join(out))
print("done", len(out))
