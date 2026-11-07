import puppeteer from "puppeteer-core";
import fs from "fs";

const base = process.argv[2] || "http://127.0.0.1:8765/";
const outDir = "/tmp/sheep-test";
fs.mkdirSync(outDir, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const errors = [];
function watch(page) {
  page.on("pageerror", (err) => errors.push("pageerror " + err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push("console " + msg.text());
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("sheep-") || url.includes(".css") || url.includes(".js") || url.includes("widgets/")) {
      errors.push("requestfailed " + url + " " + (req.failure() && req.failure().errorText));
    }
  });
}

async function heroFrame(page, idPart) {
  for (const frame of page.frames()) {
    try {
      const ok = await frame.evaluate((part) => !!document.getElementById(part), idPart);
      if (ok) return frame;
    } catch {
      /* detached */
    }
  }
  return null;
}

const desktop = await browser.newPage();
watch(desktop);
await desktop.setViewport({ width: 1920, height: 1072, deviceScaleFactor: 1 });
await desktop.goto(base, { waitUntil: "networkidle0", timeout: 30000 });
await desktop.waitForSelector("#desktop-stage iframe");
const dFrame = await heroFrame(desktop, "sheepStage");
if (!dFrame) throw new Error("desktop hero frame missing");

const stageBox = await dFrame.evaluate(() => {
  const stage = document.getElementById("sheepStage");
  const rect = stage.getBoundingClientRect();
  return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
});
const iframeBox = await desktop.evaluate(() => {
  const frame = document.querySelector('#desktop-stage iframe[title^="Sheep scanner"]');
  const rect = frame.getBoundingClientRect();
  return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
});
const point = {
  x: iframeBox.x + stageBox.x + stageBox.w * 0.55,
  y: iframeBox.y + stageBox.y + stageBox.h * 0.42,
};
await desktop.mouse.move(point.x, point.y);
await new Promise((r) => setTimeout(r, 120));
const hovering = await dFrame.evaluate(() => {
  const scanner = document.getElementById("scanner");
  const rect = scanner.getBoundingClientRect();
  return {
    opacity: getComputedStyle(scanner).opacity,
    width: rect.width,
    clip: document.getElementById("xrayMask").style.clipPath,
  };
});
await desktop.mouse.down();
await desktop.mouse.move(point.x + 80, point.y + 30);
await desktop.mouse.up();
const afterUp = await dFrame.evaluate(() => ({
  opacity: getComputedStyle(document.getElementById("scanner")).opacity,
  clip: document.getElementById("xrayMask").style.clipPath,
}));
await desktop.mouse.move(10, 10);
await new Promise((r) => setTimeout(r, 80));
const afterLeave = await dFrame.evaluate(() => ({
  opacity: getComputedStyle(document.getElementById("scanner")).opacity,
  clip: document.getElementById("xrayMask").style.clipPath,
}));
await desktop.screenshot({ path: outDir + "/desktop-1920.png" });

const headline = await desktop.evaluate(() => {
  const stage = document.getElementById("desktop-stage");
  const scale = stage.getBoundingClientRect().width / 1024;
  const node = [...stage.querySelectorAll("h1, p")].find((el) => el.textContent.trim() === "IS THAT");
  const rect = node.getBoundingClientRect();
  const origin = stage.getBoundingClientRect();
  return {
    scale,
    x: (rect.x - origin.x) / scale,
    y: (rect.y - origin.y) / scale,
    fontSize: getComputedStyle(node).fontSize,
  };
});

const mobile = await browser.newPage();
watch(mobile);
await mobile.setViewport({ width: 400, height: 985, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
await mobile.goto(base, { waitUntil: "networkidle0", timeout: 30000 });
const mFrame = await heroFrame(mobile, "mobileSheepStage");
if (!mFrame) throw new Error("mobile hero frame missing");
const mIframe = await mobile.evaluate(() => {
  const frame = document.querySelector('#mobile-stage iframe[title^="Sheep scanner"]');
  const rect = frame.getBoundingClientRect();
  return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
});
const mStage = await mFrame.evaluate(() => {
  const rect = document.getElementById("mobileSheepStage").getBoundingClientRect();
  return { x: rect.x, y: rect.y, w: rect.width, h: rect.height };
});
const touch = {
  x: mIframe.x + mStage.x + mStage.w * 0.5,
  y: mIframe.y + mStage.y + mStage.h * 0.55,
};
const beforeTouchScroll = await mobile.evaluate(() => window.scrollY);
await mobile.touchscreen.touchStart(touch.x, touch.y);
await new Promise((r) => setTimeout(r, 150));
const during = await mFrame.evaluate(() => {
  const scanner = document.getElementById("mobileScanner");
  const rect = scanner.getBoundingClientRect();
  return {
    scanning: document.getElementById("mobileSheepStage").classList.contains("is-scanning"),
    opacity: getComputedStyle(scanner).opacity,
    width: rect.width,
    clip: document.getElementById("mechanicalMask").style.clipPath,
  };
});
await mobile.touchscreen.touchMove(touch.x + 36, touch.y + 24);
await new Promise((r) => setTimeout(r, 80));
const dragged = await mFrame.evaluate(() => document.getElementById("mechanicalMask").style.clipPath);
const scrollDuring = await mobile.evaluate(() => window.scrollY);
await mobile.touchscreen.touchEnd();
await new Promise((r) => setTimeout(r, 250));
const afterTouch = await mFrame.evaluate(() => ({
  scanning: document.getElementById("mobileSheepStage").classList.contains("is-scanning"),
  clip: document.getElementById("mechanicalMask").style.clipPath,
}));
await mobile.screenshot({ path: outDir + "/mobile-400-top.png" });
await mobile.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await new Promise((r) => setTimeout(r, 200));
const scrolled = await mobile.evaluate(() => window.scrollY);
await mobile.screenshot({ path: outDir + "/mobile-400-bottom.png" });

const report = {
  hovering,
  afterUp,
  afterLeave,
  headline,
  iframeBox,
  during,
  dragged,
  afterTouch,
  beforeTouchScroll,
  scrollDuring,
  scrolled,
  errors,
};
fs.writeFileSync(outDir + "/report.json", JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
await browser.close();
