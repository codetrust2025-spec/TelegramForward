import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * jsdom does not lay out or evaluate media queries, so the visual rules are
 * checked against the stylesheet itself. These guard the specific rules that
 * were asked for; the arithmetic and DOM structure are covered elsewhere.
 */
// Vitest resolves import.meta.url to a non-file scheme, so read from the
// project root instead (tests run with `dashboard/` as the working directory).
const css = readFileSync(
  resolve(process.cwd(), "src/candidates/EarningsBreakdown.css"),
  "utf8",
);

/** The body of a rule, with whitespace collapsed. */
function rule(selector) {
  const at = css.indexOf(selector + " {");
  expect(at, `rule not found: ${selector}`).toBeGreaterThan(-1);
  return css.slice(at, css.indexOf("}", at)).replace(/\s+/g, " ");
}

/** Every `@media (max-width: 768px)` block joined — there is more than one. */
function mobileBlock() {
  const blocks = [];
  let from = 0;
  for (;;) {
    const at = css.indexOf("@media (max-width: 768px)", from);
    if (at === -1) break;
    let depth = 0;
    for (let i = css.indexOf("{", at); i < css.length; i += 1) {
      if (css[i] === "{") depth += 1;
      if (css[i] === "}") {
        depth -= 1;
        if (depth === 0) {
          blocks.push(css.slice(at, i + 1));
          from = i + 1;
          break;
        }
      }
    }
    if (from <= at) throw new Error("unterminated media block");
  }
  expect(blocks.length, "mobile media query missing").toBeGreaterThan(0);
  return blocks.join("\n");
}

describe("summary column alignment", () => {
  it("gives every term an identical column so the band lines up", () => {
    const rows = rule(".earn-ledger-rows");

    expect(rows).toContain("grid-auto-flow: column");
    expect(rows).toContain("grid-auto-columns: minmax(0, 1fr)");
    // Equal tracks regardless of whether the optional Recoveries item is present.
    expect(rows).not.toContain("auto-fit");
  });

  it("keeps the band aligned to a common top edge", () => {
    expect(rule(".earn-ledger-rows")).toContain("align-items: start");
  });
});

describe("opening-balance reason", () => {
  it("is capitalised visually, not in the data", () => {
    expect(rule(".earn-ledger-note::first-letter")).toContain("text-transform: uppercase");
  });
});

describe("outcome sentence visibility", () => {
  it("is set apart rather than left as the quietest line in the card", () => {
    const outcome = rule(".earn-ledger-outcome");

    expect(outcome).toMatch(/background: rgba\(99, 102, 241/);
    expect(outcome).toMatch(/border-left: 3px solid/);
    expect(outcome).toContain("font-weight: 700");
    // Larger than the labels around it.
    expect(outcome).toContain("font-size: 13.5px");
  });
});

describe("mobile stacked card", () => {
  const mobile = mobileBlock();

  it("stacks the calculation one item per row", () => {
    expect(mobile).toMatch(/\.earn-ledger-rows\s*{[^}]*grid-auto-flow:\s*row/);
    expect(mobile).toMatch(/\.earn-ledger-rows\s*{[^}]*grid-template-columns:\s*1fr/);
  });

  it("puts the label left and the amount right on each row", () => {
    expect(mobile).toMatch(/\.earn-ledger-row\s*{[^}]*justify-content:\s*space-between/);
    expect(mobile).toMatch(/\.earn-ledger-value\s*{[^}]*text-align:\s*right/);
  });

  it("drops the reason onto its own full-width line", () => {
    expect(mobile).toMatch(/\.earn-ledger-note\s*{[^}]*flex:\s*1 0 100%/);
  });

  it("keeps the total separated once the band becomes a list", () => {
    expect(mobile).toMatch(/\.earn-ledger-row--total\s*{[^}]*border-top/);
  });

  it("never introduces a horizontal scroller", () => {
    expect(css).not.toMatch(/\.earn-ledger[^{]*{[^}]*overflow-x:\s*(auto|scroll)/);
    expect(css).not.toMatch(/\.earn-ledger[^{]*{[^}]*min-width:\s*[1-9]/);
    // The container is width-bound, so nothing inside can push it wider.
    expect(rule(".earn-ledger")).toContain("width: 100%");
  });
});

describe("amounts share one line across the band", () => {
  it("fixes the label line box so the info badge cannot push its amount down", () => {
    expect(rule(".earn-ledger-label")).toContain("line-height: 16px");
  });

  it("fixes the value line box so the larger closing figure stays in line", () => {
    expect(rule(".earn-ledger-value")).toContain("line-height: 20px");
  });

  it("emphasises only the closing figure, not its label", () => {
    // A larger label would make that column taller than the rest.
    expect(rule(".earn-ledger-row--total .earn-ledger-value")).toContain("font-size: 15px");
    expect(rule(".earn-ledger-row--total .earn-ledger-label")).not.toContain("font-size");
  });

  it("sizes the card border-box so padding cannot overflow the row", () => {
    expect(rule(".earn-ledger")).toContain("box-sizing: border-box");
  });
});
