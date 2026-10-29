// Captures docs/screenshot.png from a running app:
//   LEADFINDER_DEMO=1 streamlit run app.py --server.headless true
//   node docs/screenshot.mjs [url]
import { chromium } from "playwright";

const url = process.argv[2] ?? "http://localhost:8501";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1.5 });
await page.goto(url);
await page.getByText("Businesses found").waitFor({ timeout: 60_000 });
await page.waitForTimeout(2500); // let the table and map finish rendering
await page.screenshot({ path: new URL("./screenshot.png", import.meta.url).pathname.replace(/^\/(\w:)/, "$1") });
await browser.close();
console.log("saved docs/screenshot.png");
