"""Minimize heavy rate-limit / account sleep UI in App.jsx."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "dashboard" / "src" / "App.jsx"
c = p.read_text(encoding="utf-8")

old_badges_and_box = """      {/* Active badge */}
      {isActive && !heavyLimit && (
        <motion.div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#3b82f6', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>ACTIVE</div>
      )}
      {heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#ef4444', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>🛑 RATE LIMITED</div>
      )}

      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>
        👤 {label}
      </div>
      {heavyLimit && (
        <div style={{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: '10px 12px', marginBottom: 10, fontSize: 12, color: '#fecaca',
        }} onClick={e => e.stopPropagation()}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>🛑 Heavy rate limit — account sleeps</div>
          <div style={{ color: '#fca5a5' }}>
            Cycle stopped early. Telegram blocked this account for a long period.
            {acctState?.next_cycle_in > 0 && (
              <span> Resume in ~{formatDurationShort(acctState.next_cycle_in)}.</span>
            )}
          </div>
        </div>
      )}"""

old_badges_and_box = old_badges_and_box.replace("motion.div", "motion.div")  # noop
old_badges_and_box = """      {/* Active badge */}
      {isActive && !heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#3b82f6', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>ACTIVE</div>
      )}
      {heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#ef4444', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>🛑 RATE LIMITED</div>
      )}

      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>
        👤 {label}
      </div>
      {heavyLimit && (
        <div style={{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: '10px 12px', marginBottom: 10, fontSize: 12, color: '#fecaca',
        }} onClick={e => e.stopPropagation()}>
          <motion.div style={{ fontWeight: 700, marginBottom: 4 }}>🛑 Heavy rate limit — account sleeps</div>
          <div style={{ color: '#fca5a5' }}>
            Cycle stopped early. Telegram blocked this account for a long period.
            {acctState?.next_cycle_in > 0 && (
              <span> Resume in ~{formatDurationShort(acctState.next_cycle_in)}.</span>
            )}
          </div>
        </div>
      )}"""

# fix - file uses div not motion
old_badges_and_box = """      {/* Active badge */}
      {isActive && !heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#3b82f6', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>ACTIVE</div>
      )}
      {heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#ef4444', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>🛑 RATE LIMITED</div>
      )}

      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>
        👤 {label}
      </div>
      {heavyLimit && (
        <div style={{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: '10px 12px', marginBottom: 10, fontSize: 12, color: '#fecaca',
        }} onClick={e => e.stopPropagation()}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>🛑 Heavy rate limit — account sleeps</motion.div>
          <div style={{ color: '#fca5a5' }}>
            Cycle stopped early. Telegram blocked this account for a long period.
            {acctState?.next_cycle_in > 0 && (
              <span> Resume in ~{formatDurationShort(acctState.next_cycle_in)}.</span>
            )}
          </div>
        </div>
      )}"""

old_badges_and_box = """      {/* Active badge */}
      {isActive && !heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#3b82f6', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>ACTIVE</div>
      )}
      {heavyLimit && (
        <div style={{
          position: 'absolute', top: -10, left: 14,
          background: '#ef4444', color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>🛑 RATE LIMITED</div>
      )}

      <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10 }}>
        👤 {label}
      </div>
      {heavyLimit && (
        <div style={{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: '10px 12px', marginBottom: 10, fontSize: 12, color: '#fecaca',
        }} onClick={e => e.stopPropagation()}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>🛑 Heavy rate limit — account sleeps</motion.div>
          <div style={{ color: '#fca5a5' }}>
            Cycle stopped early. Telegram blocked this account for a long period.
            {acctState?.next_cycle_in > 0 && (
              <span> Resume in ~{formatDurationShort(acctState.next_cycle_in)}.</span>
            )}
          </div>
        </div>
      )}""".replace("</motion.div>", "</div>", 1).replace("account sleeps</motion.div>", "account sleeps</motion.div>")

# Just read from file and use exact bytes
start = c.find("      {/* Active badge */}")
end = c.find("      {info ? (", start)
if start < 0 or end < 0:
    raise SystemExit("markers not found")
block = c[start:end]
print("FOUND BLOCK LEN", len(block))

new_block = """      {isActive && (
        <div style={{
          position: 'absolute', top: -9, left: 14,
          background: heavyLimit ? '#b45309' : '#3b82f6',
          color: '#fff', fontSize: 10,
          fontWeight: 700, padding: '2px 8px', borderRadius: 99,
        }}>
          {heavyLimit ? 'SLEEP' : 'ACTIVE'}
        </div>
      )}

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 8, gap: 8,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0' }}>👤 {label}</div>
        {sleepHint && (
          <span style={{
            fontSize: 11, color: '#fbbf24', fontWeight: 500,
            whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            ⏸ {sleepHint}
          </span>
        )}
      </div>

"""

c = c[:start] + new_block + c[end:]
p.write_text(c, encoding="utf-8")
print("patched AccountSlot sleep UI")
