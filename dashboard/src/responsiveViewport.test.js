import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Mobile-keyboard behaviour, as far as it can honestly be asserted here.
 *
 * A real soft keyboard shrinks the *visual* viewport without changing the
 * layout viewport, and neither jsdom nor a desktop browser reproduces that.
 * What can be checked deterministically is that the layout does not depend on
 * units that break when it happens: `vh` freezes at the un-shrunk height on
 * mobile browsers, so a dialog sized in `vh` keeps its full height behind the
 * keyboard and pushes its submit button out of reach. `dvh` tracks the visual
 * viewport and is what these surfaces must use.
 *
 * The limitation is deliberate and documented: these tests prove the units and
 * the scroll containers are right, not that a physical keyboard behaves.
 */
const read = (p) => readFileSync(resolve(process.cwd(), p), "utf8");

const SHEETS = [
  "src/index.css",
  "src/responsive.css",
  "src/components/ui/CommonModal.css",
  "src/candidates/PayoutModal.css",
];

/** Strip comments so prose about vh is not mistaken for a declaration. */
const declarations = (css) => css.replace(/\/\*[\s\S]*?\*\//g, "");

describe("surfaces that must survive a shrinking viewport", () => {
  it("sizes the shared modal against the dynamic viewport", () => {
    const css = declarations(read("src/components/ui/CommonModal.css"));
    expect(css).toMatch(/max-height:\s*calc\(100dvh/);
    expect(css).toMatch(/overflow-y:\s*auto/);
  });

  it.each(SHEETS)("%s never sizes a dialog or drawer with plain vh", (sheet) => {
    const css = declarations(read(sheet));
    // A height in vh on a dialog/drawer/modal surface is the failure mode.
    const offenders = [];
    const re = /([^{}]*(?:modal|dialog|drawer|sheet|overlay)[^{}]*)\{([^}]*)\}/gi;
    let m;
    while ((m = re.exec(css))) {
      const [, selector, body] = m;
      if (/(?:^|[^d])\b(?:max-)?height:\s*\d+vh/.test(body)) offenders.push(selector.trim().slice(0, 60));
    }
    expect(offenders, `plain vh on ${sheet}`).toEqual([]);
  });

  it("locks the background without moving the page", () => {
    // position: fixed on body would reset scroll to the top when a keyboard
    // opens and the dialog re-lays-out.
    const css = declarations(read("src/responsive.css"));
    const lock = css.slice(css.indexOf("body:has"), css.indexOf("body:has") + 1400);
    expect(lock).toContain("overflow: hidden");
    expect(lock).not.toContain("position: fixed");
  });

  it("keeps mobile modals within the dynamic viewport", () => {
    const css = declarations(read("src/responsive.css"));
    // The phone block caps modal height with dvh, not vh.
    expect(css).toMatch(/max-height:\s*9?\d+dvh/);
  });

  it("respects the safe area at the bottom of mobile sheets", () => {
    const css = declarations(read("src/responsive.css"));
    expect(css).toMatch(/padding-bottom:\s*max\([^)]*var\(--safe-bottom\)/);
  });
});

describe("form controls stay reachable when the viewport shrinks", () => {
  it("gives form controls the touch minimum rather than a fixed height", () => {
    // Locate by the raw file: the marker is in a comment, which declarations()
    // strips before the vh checks above.
    const raw = read("src/responsive.css");
    const at = raw.indexOf("tap-friendly");
    expect(at).toBeGreaterThan(-1);
    const slice = declarations(raw.slice(at, at + 700));
    // min-height, not height: a fixed height cannot shrink with the viewport.
    expect(slice).toContain("min-height: var(--ta-touch-min)");
    expect(slice).not.toMatch(/[^-]height:\s*\d+px/);
  });
});
