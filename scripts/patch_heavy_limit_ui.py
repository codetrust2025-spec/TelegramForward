# -*- coding: utf-8 -*-
path = r"C:\Users\ravin\TelegramForward\dashboard\src\App.jsx"
O, C = "<div", "</motion.div>"
C = "</motion.div>"
C = "</div>"

with open(path, encoding="utf-8") as f:
    c = f.read()

old_banner = f"""      {{acctNotification && (
        {O}
          style={{{{
            background: '#422006', border: '1px solid #f59e0b', borderRadius: 8,
            padding: '8px 12px', marginBottom: 8, color: '#fbbf24',
            fontSize: 13, fontWeight: 600, flexShrink: 0,
          }}}}
        >
          🔔 {{acctNotification}}
        {C}
      )}}"""

new_banner = f"""      {{acctNotification && (
        {O}
          style={{{{
            background: activeHeavyLimit ? '#450a0a' : '#422006',
            border: `1px solid ${{activeHeavyLimit ? '#ef4444' : '#f59e0b'}}`,
            borderRadius: 8,
            padding: '8px 12px', marginBottom: 8,
            color: activeHeavyLimit ? '#fca5a5' : '#fbbf24',
            fontSize: 13, fontWeight: 600, flexShrink: 0,
          }}}}
        >
          {{activeHeavyLimit ? '🛑' : '🔔'}} {{acctNotification}}
        {C}
      )}}"""

if old_banner in c:
    c = c.replace(old_banner, new_banner)
    print("banner patched")
else:
    print("banner not found")

old_border = "  const borderColor = isActive ? '#3b82f6' : '#2d3148'"
new_border = """  const heavyLimit = isHeavyRateLimit(acctState)
  const borderColor = heavyLimit ? '#ef4444' : (isActive ? '#3b82f6' : '#2d3148')"""
if old_border in c:
    c = c.replace(old_border, new_border)
    print("border patched")

heavy_banner = f"""
      {{heavyLimit && (
        {O} style={{{{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: '10px 12px', marginBottom: 10, fontSize: 12, color: '#fecaca',
        }}}} onClick={{e => e.stopPropagation()}}>
          {O} style={{{{ fontWeight: 700, marginBottom: 4 }}}}>🛑 Heavy rate limit — account sleeps{C}
          {O} style={{{{ color: '#fca5a5' }}}}>
            Cycle stopped early. Telegram blocked this account for a long period.
            {{acctState?.next_cycle_in > 0 && (
              <span> Resume in ~{{formatDurationShort(acctState.next_cycle_in)}}.</span>
            )}}
          {C}
        {C}
      )}}"""

marker = "        👤 {label}\n      </motion.div>"
marker = f"        👤 {{label}}\n      {C}"
insert_after = marker
if heavy_banner.strip() not in c and insert_after in c:
    c = c.replace(insert_after, insert_after + heavy_banner)
    print("heavy banner inserted")

# Fix slot style background and badges
c = c.replace(
    "background: isActive ? '#1e2a3f' : '#1a1d27',\n        borderRadius: 12, padding: '16px 18px',\n        border: `2px solid ${borderColor}`, width: '100%',\n        position: 'relative', cursor: 'pointer',\n      }}",
    "background: heavyLimit ? '#2a1515' : (isActive ? '#1e2a3f' : '#1a1d27'),\n        borderRadius: 12, padding: '16px 18px',\n        border: `2px solid ${borderColor}`, width: '100%',\n        position: 'relative', cursor: 'pointer',\n        boxShadow: heavyLimit ? '0 0 14px rgba(239, 68, 68, 0.25)' : 'none',\n      }}",
    1,
)
c = c.replace(
    "{isActive && (\n        <div style={{\n          position: 'absolute', top: -10, left: 14,\n          background: '#3b82f6'",
    "{isActive && !heavyLimit && (\n        <div style={{\n          position: 'absolute', top: -10, left: 14,\n          background: '#3b82f6'",
    1,
)
rate_badge = f"""      {{heavyLimit && (
        {O} style={{{{
          position: 'absolute', top: -10, left: 14,
          background: '#ef4444', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}}}>🛑 RATE LIMITED{C}
      )}}"""
if "RATE LIMITED" not in c and "}}>ACTIVE</div>" in c:
    c = c.replace("}}>ACTIVE</motion.div>", "}}>ACTIVE</motion.div>")
    c = c.replace("}}>ACTIVE</motion.div>", "}}>ACTIVE</motion.div>")
    c = c.replace("}}>ACTIVE</div>", "}}>ACTIVE</div>\n" + rate_badge, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)
print("done")
