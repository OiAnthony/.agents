#!/usr/bin/env node
/* Render TeX formulas from stdin JSON to self-contained MathJax SVG fragments.
 * Input:  [{"tex":"x^2", "display":true}, ...]
 * Output: ["<mjx-container ...>...</mjx-container>", ...]
 */
const fs = require("fs");
const os = require("os");
const path = require("path");

const nodeMajor = Number.parseInt(process.versions.node.split(".")[0], 10);
if (!Number.isInteger(nodeMajor) || nodeMajor < 20 || nodeMajor === 21) {
  process.stderr.write(
    "MathJax render failed: strict LaTeX rendering requires Node.js 20 or Node.js 22+\n",
  );
  process.exit(1);
}

const runtimePackage = require("./mathjax-runtime/package.json");
const mathJaxVersion = runtimePackage.dependencies["@mathjax/src"];
const cacheHome = process.platform === "darwin"
  ? path.join(os.homedir(), ".cache")
  : (process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache"));
const mathRoot = path.join(cacheHome, "kami", "mathjax", mathJaxVersion);
const load = (id) => require(require.resolve(id, { paths: [mathRoot] }));

const packageModules = [
  "ams/AmsConfiguration.js",
  "boldsymbol/BoldsymbolConfiguration.js",
  "braket/BraketConfiguration.js",
  "cancel/CancelConfiguration.js",
  "cases/CasesConfiguration.js",
  "centernot/CenternotConfiguration.js",
  "empheq/EmpheqConfiguration.js",
  "enclose/EncloseConfiguration.js",
  "extpfeil/ExtpfeilConfiguration.js",
  "gensymb/GensymbConfiguration.js",
  "mathtools/MathtoolsConfiguration.js",
  "mhchem/MhchemConfiguration.js",
  "newcommand/NewcommandConfiguration.js",
  "physics/PhysicsConfiguration.js",
  "tagformat/TagFormatConfiguration.js",
  "textcomp/TextcompConfiguration.js",
  "textmacros/TextMacrosConfiguration.js",
  "unicode/UnicodeConfiguration.js",
  "units/UnitsConfiguration.js",
  "upgreek/UpgreekConfiguration.js",
];
const packages = [
  "base", "ams", "boldsymbol", "braket", "cancel", "cases", "centernot",
  "empheq", "enclose", "extpfeil", "gensymb", "mathtools",
  "mhchem", "newcommand", "physics", "tagformat", "textcomp", "textmacros",
  "unicode", "units", "upgreek",
];

try {
  const installed = load("@mathjax/src/package.json");
  if (installed.version !== mathJaxVersion) {
    throw new Error(`expected @mathjax/src ${mathJaxVersion}, found ${installed.version}`);
  }
  const { mathjax } = load("@mathjax/src/js/mathjax.js");
  const { TeX } = load("@mathjax/src/js/input/tex.js");
  const { SVG } = load("@mathjax/src/js/output/svg.js");
  const { liteAdaptor } = load("@mathjax/src/js/adaptors/liteAdaptor.js");
  const { RegisterHTMLHandler } = load("@mathjax/src/js/handlers/html.js");
  const { SafeHandler } = load("@mathjax/src/js/ui/safe/SafeHandler.js");
  for (const moduleName of packageModules) {
    load(`@mathjax/src/js/input/tex/${moduleName}`);
  }

  const adaptor = liteAdaptor();
  const handler = RegisterHTMLHandler(adaptor);
  SafeHandler(handler);
  const tex = new TeX({
    packages,
    maxBuffer: 10 * 1024,
    formatError(_jax, err) {
      throw err;
    },
  });
  // `none` keeps every SVG self-contained, avoiding cross-formula path IDs.
  const svg = new SVG({ fontCache: "none" });
  const doc = mathjax.document("", {
    InputJax: tex,
    OutputJax: svg,
    compileError(_document, _math, err) {
      throw err;
    },
    safeOptions: {
      allow: { URLs: "none", classes: "none", cssIDs: "none", styles: "none" },
    },
  });
  if (process.argv.includes("--probe")) {
    const probeNode = doc.convert("x", { display: false });
    const probeOutput = adaptor.outerHTML(probeNode);
    if (!probeOutput.startsWith("<mjx-container") || !probeOutput.includes("<svg")) {
      throw new Error("locked MathJax runtime failed its SVG smoke render");
    }
    process.stdout.write(JSON.stringify({ version: installed.version, root: mathRoot }));
    process.exit(0);
  }

  const formulas = JSON.parse(fs.readFileSync(0, "utf8"));
  if (!Array.isArray(formulas)) {
    throw new Error("input must be a JSON array");
  }
  const rendered = formulas.map(({ tex: source, display }, index) => {
    if (typeof source !== "string" || typeof display !== "boolean") {
      throw new Error(`formula ${index + 1} must contain string tex and boolean display`);
    }
    const node = doc.convert(source, { display });
    const output = adaptor.outerHTML(node);
    if (output.includes("data-mjx-error") || output.includes("<merror")) {
      throw new Error(`formula ${index + 1} produced a MathJax error node`);
    }
    return output;
  });
  process.stdout.write(JSON.stringify(rendered));
} catch (err) {
  process.stderr.write(`MathJax render failed: ${err.stack || err.message}\n`);
  process.exit(1);
}
