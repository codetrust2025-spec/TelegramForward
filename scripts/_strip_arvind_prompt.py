"""Remove Arvind from data/ai_smart_reply.json business_prompt."""
import json
import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "data" / "ai_smart_reply.json"
data = json.loads(path.read_text(encoding="utf-8"))
p = data["config"]["business_prompt"]

replacements = [
    (
        "Java / AI-ML → Arvind 📞 +91 78938 98866 📲 https://wa.me/917893898866",
        "Java / AI-ML → Thirlok 📞 9000000001 📲 https://wa.me/919000000001",
    ),
    (
        "Java/AI → Arvind 📞 +91 78938 98866",
        "Java/AI → Thirlok 📞 9000000001",
    ),
    (
        "- Java / AI-ML roles → Arvind 📞 +91 78938 98866 📲 https://wa.me/917893898866",
        "- Java / AI-ML roles → Thirlok 📞 9000000001 📲 https://wa.me/919000000001",
    ),
    ("Arvind garu (most senior in Java & AI)", "Thirlok garu (senior software engineer)"),
    ("Arvind garu (most senior in Java roles)", "Thirlok garu (senior software engineer)"),
    ("Java & AI/ML roles (ALL below) → Arvind is most senior:", "Java & AI/ML roles → Thirlok (senior):"),
    ("→ ALWAYS hand off to Arvind with full contact:", "→ ALWAYS hand off to Thirlok with full contact:"),
    ("Arvind explains and closes Java/AI deals", "Thirlok explains and closes Java/AI deals"),
    ("📞 +91 78938 98866 | 📲 https://wa.me/917893898866", ""),
    ("Vani / Kalyan / Arvind / Nikhila-Bhavana / Thirlok", "Vani / Kalyan / Nikhila-Bhavana / Thirlok"),
    ("(Vani / Kalyan / Arvind / Nikhila-Bhavana / Thirlok", "(Vani / Kalyan / Nikhila-Bhavana / Thirlok"),
    ("DevOps NEVER goes to Arvind — only Kalyan\n", ""),
    ("DevOps NEVER goes to Arvind — always Kalyan\n", ""),
]
for old, new in replacements:
    p = p.replace(old, new)

# Collapse duplicate blank lines from removed phone line
p = re.sub(r"\n{3,}", "\n\n", p)
while "Arvind" in p:
    p = p.replace("Arvind", "Thirlok", 1)

data["config"]["business_prompt"] = p
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Arvind remaining:", p.count("Arvind"))
print("78938 remaining:", p.count("78938"))
