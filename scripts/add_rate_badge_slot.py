from pathlib import Path

p = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "App.jsx"
c = p.read_text(encoding="utf-8")

needle = (
    "        }}>ACTIVE</div>\n"
    "      )}\n\n"
    "      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>\n"
    "        👤 {label}\n"
    "      </div>"
)
insert = (
    "        }}>ACTIVE</div>\n"
    "      )}\n"
    "      {heavyLimit && (\n"
    "        <div style={{\n"
    "          position: 'absolute', top: -10, left: 14,\n"
    "          background: '#ef4444', color: '#fff', fontSize: 10,\n"
    "          fontWeight: 700, padding: '2px 8px', borderRadius: 99,\n"
    "        }}>🛑 RATE LIMITED</div>\n"
    "      )}\n\n"
    "      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>\n"
    "        👤 {label}\n"
    "      </div>"
)

slot_section = c.split("function AccountSlot", 1)[1].split("function AccountPanel", 1)[0]
if "🛑 RATE LIMITED</div>" in slot_section and "top: -10, left: 14" in slot_section:
    print("already has slot badge")
elif needle not in c:
    raise SystemExit("needle not found")
else:
    p.write_text(c.replace(needle, insert, 1), encoding="utf-8")
    print("inserted slot rate badge")
