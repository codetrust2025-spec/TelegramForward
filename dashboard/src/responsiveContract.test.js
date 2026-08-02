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
