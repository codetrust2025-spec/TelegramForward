#!/usr/bin/env python3
"""Quick smoke test for from-scratch job routing."""
import sys
sys.path.insert(0, r"C:\Users\codet\OneDrive\Desktop\Automation\scripts")
import ai_smart_reply_vps as m

history = [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hi 👍 I'm Karthik. What can I help you with?"},
    {"role": "user", "content": "I need job"},
]

r1 = m._job_seeker_reply("I need job", history=history, lang="english", lead={"name": "Unknown"})
assert "scheduled round" not in r1.lower(), r1
assert "resume" in r1.lower() or "naukri" in r1.lower() or "profile" in r1.lower(), r1
print("need job:", r1)

history2 = history + [
    {"role": "assistant", "content": r1},
    {"role": "user", "content": "Everything should be done by scratch"},
]
r2 = m._job_seeker_reply(
    "Everything should be done by scratch",
    history=history2,
    lang="english",
    lead={"name": "Unknown"},
)
assert "fresher" in r2.lower() or "experience" in r2.lower(), r2
assert "scheduled round" not in r2.lower(), r2
print("from scratch:", r2)

history3 = [
    {"role": "user", "content": "I have interview tomorrow for Java"},
]
r3 = m._job_seeker_reply("I need job support", history=history3, lang="english")
assert "scheduled round" in r3.lower() or "tech stack" in r3.lower(), r3
print("has interview:", r3)

print("All routing tests passed")
