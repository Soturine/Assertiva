const { chromium } = require(process.argv[2]);
const fs = require("fs");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(require("url").pathToFileURL(require("path").join(__dirname, process.argv[3] || "page.html")).href);
  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const results = await page.evaluate(async () => await axe.run());
  results.url = process.argv[4] || "http://localhost/checkout";
  fs.writeFileSync("axe-results.json", JSON.stringify(results, null, 2));
  console.log(results.testEngine, results.violations.map(v => v.id + ":" + v.impact + ":" + v.nodes.length), "incomplete", results.incomplete.map(v => v.id), "passes", results.passes.length);
  await browser.close();
})();
