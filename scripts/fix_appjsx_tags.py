path = r"C:\Users\ravin\TelegramForward\dashboard\src\App.jsx"
with open(path, encoding="utf-8") as f:
    c = f.read()

c = c.replace("Account {i + 1}</motion.div>", "Account {i + 1}</div>")

old_block = """              <motion.div style={{
                fontSize: 11, fontWeight: 400, marginTop: 4,
                color: heavyLimit ? '#fca5a5' : selected ? '#93c5fd' : '#64748b',
              }}>
                {info ? info.name : 'Not logged in'}
                {heavyLimit
                  ? ` · 🛑 sleeping${sleepLeft ? ` (${formatDurationShort(sleepLeft)} left)` : ''}`
                  : running ? ' · ● Running' : ''}
              </motion.div>"""

new_block = """              <div style={{
                fontSize: 11, fontWeight: 400, marginTop: 4,
                color: heavyLimit ? '#fca5a5' : selected ? '#93c5fd' : '#64748b',
              }}>
                {info ? info.name : 'Not logged in'}
                {heavyLimit
                  ? ` · 🛑 sleeping${sleepLeft ? ` (${formatDurationShort(sleepLeft)} left)` : ''}`
                  : running ? ' · ● Running' : ''}
              </div>"""

if old_block in c:
    c = c.replace(old_block, new_block)
    print("replaced block")
else:
    print("block not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(c)
