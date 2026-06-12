#!/usr/bin/env python3
"""Patch login tab to show all logged-in accounts including shutdown."""
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent / "static" / "assets" / "app-BkUk1ts9.js"

PATCHES = [
    (
        "onProvisionSlot:E}){var Ge,gt,ae,we,Ce,Re,$e,Ke,nt,He,it,Ct,ve,On,Cr;",
        "onProvisionSlot:E,includeShutdownInGrid:$=!1}){var Ge,gt,ae,we,Ce,Re,$e,Ke,nt,He,it,Ct,ve,On,Cr;",
        "Ay signature",
        1,
    ),
    (
        "R=b.useMemo(()=>{const Ve=e.active_account,jt=()=>C[0]??B??null;return Ve&&Va(O,Ve)?qi(D,z,Ve)?jt():Ve",
        "R=b.useMemo(()=>{const Ve=e.active_account,jt=()=>($?te:C)[0]??B??null;return Ve&&Va(O,Ve)?qi(D,z,Ve)&&!$?jt():Ve",
        "active account R",
        1,
    ),
    (
        'se=s&&q==="all",le=b.useMemo(()=>se?R&&Va(O,R)&&!qi(D,z,R)&&!C.includes(R)?th([...C,R],A,O):C:H,[se,C,H,R,O,A,D,z])',
        'se=s&&q==="all",le=b.useMemo(()=>$?th(te,A,O):se?R&&Va(O,R)&&!qi(D,z,R)&&!C.includes(R)?th([...C,R],A,O):C:H,[se,$,te,C,H,R,O,A,D,z])',
        "grid le",
        1,
    ),
    (
        "b.useEffect(()=>{if(g||se||!R||!Va(O,R)||H.includes(R))return;const Ve=H[0]",
        "b.useEffect(()=>{if(g||se||$||!R||!Va(O,R)||H.includes(R))return;const Ve=H[0]",
        "auto-switch effect",
        1,
    ),
    (
        'be=!!(R&&!qi(D,z,R)&&(q==="all"||H.includes(R)||ge))',
        'be=!!(R&&Va(O,R)&&($||!qi(D,z,R))&&(q==="all"||H.includes(R)||ge||$))',
        "detail card be",
        1,
    ),
    (
        'if(q==="all"||se)return`${Ve} accounts${jt} · ${X.campaign} campaign · ${X.forwarding} forwarding`;',
        'if($)return`${te.length} logged in${Y>0?` · ${Y} resting (Shutdown tab)`:""}`;if(q==="all"||se)return`${Ve} accounts${jt} · ${X.campaign} campaign · ${X.forwarding} forwarding`;',
        "subtitle",
        1,
    ),
    (
        "accountsModeFilter:le,onAccountsModeFilterChange:de,hideAccountsModeFilter:!0,workspaceMode:le,",
        'accountsModeFilter:"all",onAccountsModeFilterChange:de,hideAccountsModeFilter:!0,includeShutdownInGrid:!0,workspaceMode:le,',
        "login tab props",
        2,
    ),
]


def main() -> None:
    text = BUNDLE.read_text(encoding="utf-8")
    original = text
    for old, new, name, expected in PATCHES:
        count = text.count(old)
        if count != expected:
            raise SystemExit(f"PATCH FAILED — {name}: expected {expected}, found {count}")
        text = text.replace(old, new)
    if text == original:
        raise SystemExit("No changes made")
    BUNDLE.write_text(text, encoding="utf-8")
    print(f"Patched {BUNDLE} ({len(text)} bytes)")
    for _, _, name, _ in PATCHES:
        print(f"  OK: {name}")


if __name__ == "__main__":
    main()
