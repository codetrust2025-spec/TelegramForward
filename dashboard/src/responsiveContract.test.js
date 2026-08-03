import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The responsive layer's own contract, guarded against drift.
 *
 * jsdom has no layout engine, so the rules are asserted against the stylesheet.
 * The behaviour they produce was measured on the live page — see the PR — and
 * these tests exist so the rules cannot be quietly removed or narrowed again.
 */
const read = (p) => readFileSync(resolve(process.cwd(), p), "utf8");
const responsive = read("src/responsive.css");

function blockAt(head, css = responsive) {
  const at = css.indexOf(head);
  expect(at, `block not found: ${head}`).toBeGreaterThan(-1);
  let depth = 0;
  for (let i = css.indexOf("{", at); i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}") {
      depth -= 1;
      if (depth === 0) return css.slice(at, i + 1);
    }
  }
  throw new Error(`unterminated block: ${head}`);
}

describe("responsive layer is wired up", () => {
  it("is imported by the app entry point", () => {
    expect(read("src/main.jsx")).toMatch(/import ['"]\.\/responsive\.css['"]/);
  });

  it("declares the documented breakpoints and touch minimum", () => {
    for (const token of [
      "--ta-mobile-max: 767px",
      "--ta-tablet-min: 768px",
      "--ta-laptop-min: 1024px",
      "--ta-desktop-min: 1440px",
      "--ta-ultra-min: 1920px",
      "--ta-touch-min: 44px",
    ]) {
      expect(responsive).toContain(token);
    }
  });

  it("prevents horizontal scrolling at the document level", () => {
    expect(responsive).toMatch(/html\s*{[^}]*overflow-x:\s*clip/);
  });

  it("caps the shell on ultra-wide displays instead of stretching forever", () => {
    expect(responsive).toContain("--ta-shell-max-ultra");
  });
});

describe("touch targets on the public booking screen", () => {
  const coarse = blockAt("@media (hover: none), (pointer: coarse)");

  it("covers the screen's controls generically, not by an allowlist", () => {
    // An allowlist is why .sbs-picker__toggle shipped at 22x22.
    expect(coarse).toMatch(/\.submit-slot-screen button/);
    expect(coarse).toMatch(/\.submit-slot-screen \[role="button"\]/);
    expect(coarse).toMatch(/\.submit-slot-screen select/);
  });

  it("gives icon-only controls a width as well as a height", () => {
    const iconRule = coarse.slice(coarse.indexOf(".sbs-picker__toggle,"));
    expect(iconRule).toContain("min-width: var(--ta-touch-min)");
    expect(iconRule).toContain("min-height: var(--ta-touch-min)");
  });

  it("uses the declared minimum rather than a hard-coded size", () => {
    const slice = coarse.slice(coarse.indexOf(".submit-slot-screen button"));
    expect(slice).toContain("var(--ta-touch-min)");
    expect(slice).not.toMatch(/min-height:\s*\d+px/);
  });
});

describe("wide tables stay inside a scroll container", () => {
  // A min-width wider than a phone is fine — inside an overflow-x container.
  // Outside one it is a guaranteed horizontal scrollbar on the whole page.
  const sheets = [
    "src/candidates/EarningsBreakdown.css",
    "src/candidates/CompanyExpenditure.css",
    "src/dailyOps.css",
    "src/recruitmentMail.css",
  ];

  it.each(sheets)("%s pairs wide tables with a scroller", (sheet) => {
    const css = read(sheet);
    const wide = css.match(/min-width:\s*([4-9]\d{2}|\d{4,})px/g) || [];
    if (wide.length === 0) return;
    expect(css).toMatch(/overflow-x:\s*auto|overflow:\s*auto/);
  });
});

describe("the touch minimum survives a fine pointer at phone width", () => {
  // The coarse-pointer block alone left the 22x22 control in place on any
  // browser reporting a fine pointer — a phone in desktop mode, or a tablet
  // with a mouse. Verified live: matchMedia('(pointer: coarse)') was false at
  // 320px while '(max-width: 767px)' was true.
  // More than one max-width:767px block exists; take the one carrying the
  // booking screen's rules.
  const phone = (() => {
    const extract = (at) => {
      let depth = 0;
      for (let i = responsive.indexOf("{", at); i < responsive.length; i += 1) {
        if (responsive[i] === "{") depth += 1;
        if (responsive[i] === "}") {
          depth -= 1;
          if (depth === 0) return responsive.slice(at, i + 1);
        }
      }
      throw new Error("unterminated block");
    };
    let from = 0;
    for (;;) {
      const at = responsive.indexOf("@media (max-width: 767px)", from);
      expect(at, "phone-width booking block missing").toBeGreaterThan(-1);
      const block = extract(at);
      if (block.includes(".submit-slot-screen")) return block;
      from = at + 1;
    }
  })();

  it("applies the minimum on width, not only on pointer type", () => {
    expect(phone).toMatch(/\.submit-slot-screen button/);
    expect(phone).toMatch(/\.sbs-picker__toggle/);
    expect(phone).toContain("var(--ta-touch-min)");
  });

  it("still gives icon-only controls both dimensions", () => {
    const icon = phone.slice(phone.indexOf(".sbs-picker__toggle"));
    expect(icon).toContain("min-width: var(--ta-touch-min)");
    expect(icon).toContain("min-height: var(--ta-touch-min)");
  });
});

describe("baseline target size for fine pointers", () => {
  // Between 768px and a fine pointer neither the coarse block nor the
  // phone-width block applies. Measured live at 768px: 22x22, under the 24x24
  // WCAG 2.5.8 asks for at any pointer type.
  it("sets an unconditional floor outside every media query", () => {
    const beforeFirstMedia = responsive.slice(0, responsive.indexOf("@media"));
    const baseline = responsive.slice(
      responsive.indexOf("Baseline target size"),
      responsive.indexOf("Phone-width booking screen"),
    );
    expect(baseline).toContain("min-width: 24px");
    expect(baseline).toContain("min-height: 24px");
    expect(baseline).toContain(".sbs-picker__toggle");
    // Not nested inside a media query.
    expect(baseline).not.toContain("@media");
    expect(beforeFirstMedia.length).toBeGreaterThan(0);
  });

  it("still lets the touch minimum raise it on phones", () => {
    // min-* floors compose: 24px baseline, 44px at phone width.
    expect(responsive).toContain("--ta-touch-min: 44px");
  });
});

describe("authenticated screens meet the touch minimum on phones", () => {
  // Every selector here was measured under 44px in a real browser at 320-600px
  // with the app's own shells and wrappers in place. The harness that produced
  // those numbers lives in dashboard/harness.
  const measured = [
    ".cand-tabs__btn",
    ".cand-btn",
    ".cand-phone-trigger",
    ".admin-tab",
    ".dr-tab",
    ".kai-prompts button",
    ".kai-message-actions button",
  ];

  const block = (() => {
    const extract = (at) => {
      let depth = 0;
      for (let i = responsive.indexOf("{", at); i < responsive.length; i += 1) {
        if (responsive[i] === "{") depth += 1;
        if (responsive[i] === "}") { depth -= 1; if (depth === 0) return responsive.slice(at, i + 1); }
      }
      throw new Error("unterminated block");
    };
    let from = 0;
    for (;;) {
      const at = responsive.indexOf("@media (max-width: 767px)", from);
      expect(at, "authenticated touch-target block missing").toBeGreaterThan(-1);
      const b = extract(at);
      if (b.includes(".cand-tabs__btn")) return b;
      from = at + 1;
    }
  })();

  it.each(measured)("raises %s to the declared minimum", (sel) => {
    expect(block).toContain(sel);
  });

  it("uses the variable rather than a hard-coded height", () => {
    expect(block).toContain("min-height: var(--ta-touch-min)");
  });

  it("leaves desktop untouched by staying inside the phone breakpoint", () => {
    expect(block.startsWith("@media (max-width: 767px)")).toBe(true);
  });
});

describe("dense dashboard controls clear the pointer minimum", () => {
  // Measured at 21px tall at every width from 320 to 2560.
  it("floors the Daily Ops controls at 24px for any pointer", () => {
    const at = responsive.indexOf("Pointer-target floor");
    expect(at, "pointer-target floor missing").toBeGreaterThan(-1);
    // Slice to the next section rather than a fixed length: the selector list
    // grows as more undersized controls are found.
    const slice = responsive.slice(at, responsive.indexOf("Authenticated screens: measured"));
    for (const sel of [".ops-dash-kpi", ".ops-booking-pie__open", ".pending-works-pill"]) {
      expect(slice).toContain(sel);
    }
    expect(slice).toContain("min-height: 24px");
    // Unconditional: these were undersized on desktop too.
    expect(slice.slice(0, slice.indexOf("}"))).not.toContain("@media");
  });
});

describe("cascade order lets the phone minimum win", () => {
  // The unconditional 24px floor and the 44px phone rule share specificity, so
  // whichever comes last wins. With the floor written after the phone block,
  // Daily Ops controls stayed at 24px on phones.
  it("declares the unconditional floor before the phone-width block", () => {
    const floor = responsive.indexOf("Pointer-target floor");
    const phone = responsive.indexOf("Authenticated screens: measured");
    expect(floor).toBeGreaterThan(-1);
    expect(phone).toBeGreaterThan(-1);
    expect(floor).toBeLessThan(phone);
  });
});

describe("form controls clear the minimum on phones", () => {
  it("raises the app-wide tap-friendly rule from 40px to the declared minimum", () => {
    // index.css sets 40px under 900px with this exact selector; matching it is
    // what makes every filter select and search field comply.
    const at = responsive.indexOf("tap-friendly");
    expect(at, "form-control note missing").toBeGreaterThan(-1);
    const slice = responsive.slice(at, at + 700);
    expect(slice).toContain("input:not([type='checkbox'])");
    expect(slice).toContain("min-height: var(--ta-touch-min)");
  });

  it("also matches the toolbar's own 26px rule", () => {
    expect(responsive).toContain(".cand-toolbar select.cand-input");
  });
});

describe("shared mobile shell targets", () => {
  // These live in the mobile header and drawer, so they appear on every route:
  // one miss here is a miss on all eleven. Measured 34-40px at 320px.
  const shell = [
    ".mobile-header__menu",
    ".mobile-header__bell",
    ".mobile-header__util-btn",
    ".mobile-header__bulk",
    ".mail-bell__button",
    ".btn--segment",
  ];

  const phone = (() => {
    const extract = (at) => {
      let depth = 0;
      for (let i = responsive.indexOf("{", at); i < responsive.length; i += 1) {
        if (responsive[i] === "{") depth += 1;
        if (responsive[i] === "}") { depth -= 1; if (depth === 0) return responsive.slice(at, i + 1); }
      }
      throw new Error("unterminated block");
    };
    let from = 0;
    for (;;) {
      const at = responsive.indexOf("@media (max-width: 767px)", from);
      expect(at, "shell touch-target block missing").toBeGreaterThan(-1);
      const b = extract(at);
      if (b.includes(".mobile-header__bulk")) return b;
      from = at + 1;
    }
  })();

  it.each(shell)("raises %s on phones", (sel) => {
    expect(phone).toContain(sel);
  });

  it("lets the header action cluster shrink instead of overflowing", () => {
    // flex-shrink: 0 meant it could not give way at 320px and pushed itself
    // and the drawer past the viewport edge.
    const rule = phone.slice(phone.indexOf(".mobile-header__actions"));
    expect(rule).toContain("flex-shrink: 1");
    expect(rule).toContain("min-width: 0");
  });
});

describe("link-styled buttons clear the pointer minimum", () => {
  // padding: 0 leaves the box as just the text line — 16-21px tall on
  // Dashboard, Accounts, Forwarding, Campaigns, Settings and Inbox.
  const linkish = [
    ".desk-panel__link",
    ".fwd-link",
    ".mob-section-head__link",
    ".pending-works-strip__cta",
    ".shutdown-list-help-summary",
    ".tg-sidebar-dashboard-btn",
    ".tg-sidebar-notify-close",
  ];

  it.each(linkish)("floors %s at 24px for any pointer", (sel) => {
    const at = responsive.indexOf("Pointer-target floor");
    const slice = responsive.slice(at, responsive.indexOf("Authenticated screens: measured"));
    expect(slice).toContain(sel);
  });
});

describe("floors survive component stylesheet import order", () => {
  // Component CSS is imported by the components, so it can land after this
  // file in the bundle and win at equal specificity. .mobile-header__actions
  // stayed flex-shrink:0 for exactly that reason until it was scoped.
  it("scopes the target floors to .app-shell rather than using !important", () => {
    expect(responsive).toContain("NOTE ON SPECIFICITY");
    // Only the floors this audit added. The file has pre-existing !important
    // rules for the inbox single-pane layout that predate it.
    const floors = responsive
      // Start at the comment opener, or the stripper below cannot match the
      // first (then unterminated) comment.
      .slice(
        responsive.indexOf("/* NOTE ON SPECIFICITY"),
        responsive.indexOf("/* ── Landscape phones: short viewport"),
      )
      // Strip comments: they mention !important to explain why it is avoided.
      .replace(/\/\*[\s\S]*?\*\//g, "");
    expect(floors).not.toContain("!important");
  });

  it.each([
    ".app-shell .mobile-header__actions",
    ".app-shell .mobile-drawer__item",
    ".app-shell .btn--danger",
    ".app-shell .btn--ghost",
    ".app-shell .btn--segment",
    ".app-shell .mob-section-head__link",
  ])("scopes %s", (sel) => {
    expect(responsive).toContain(sel);
  });

  it("lets the header cluster shrink so it cannot push past the viewport", () => {
    const at = responsive.indexOf(".app-shell .mobile-header__actions");
    const rule = responsive.slice(at, responsive.indexOf("}", at));
    expect(rule).toContain("flex-shrink: 1");
    expect(rule).toContain("min-width: 0");
  });
});

describe("shared mobile header controls", () => {
  // The header and drawer are part of every route's shell, so a miss here is a
  // miss on all eleven. All measured under 44px at 320px.
  it.each([
    ".app-shell .mobile-header__brand",
    ".app-shell .mobile-drawer__item",
    ".app-shell .btn--danger",
    ".app-shell .btn--ghost",
  ])("raises %s on phones", (sel) => {
    expect(responsive).toContain(sel);
  });
});
