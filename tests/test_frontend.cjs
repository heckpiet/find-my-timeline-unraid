const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { test } = require("node:test");
const vm = require("node:vm");

async function dashboard(devices) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, {
      textContent: "", lastChild: {}, dataset: {}, listeners: {},
      classList: { add() {}, remove() {}, toggle() {} },
      setAttribute() {}, querySelectorAll: () => [],
      addEventListener(event, callback) { this.listeners[event] = callback; },
    });
    return elements.get(id);
  };
  const all = element("all");
  all.dataset.hours = "0";
  const urls = [];
  const context = {
    document: {
      getElementById: element,
      querySelectorAll: (selector) => selector === "[data-hours]" ? [all] : [],
    },
    L: {
      map: () => ({ setView() { return this; }, removeLayer() {} }),
      control: { zoom: () => ({ addTo() {} }) },
      tileLayer: () => ({ addTo() {} }),
    },
    URLSearchParams, setInterval() {}, setTimeout() {}, clearTimeout() {},
    fetch: async (url) => {
      urls.push(url);
      const payload = url === "/api/stats"
        ? { total_devices: devices.length, total_locations: 1, devices }
        : url === "/api/system/status" ? { poller: {}, configuration: {} } : [];
      return { ok: true, json: async () => payload };
    },
  };
  vm.runInNewContext(readFileSync("static/app.js", "utf8"), context);
  await new Promise(setImmediate);
  return { element, all, urls };
}

test("latest position uses location time rather than device polling time", async () => {
  const { element } = await dashboard([{
    last_seen: new Date().toISOString(),
    latest_location: { timestamp: new Date(Date.now() - 3 * 86400000).toISOString() },
  }]);
  assert.equal(element("metric-latest").textContent, "3 d ago");
});

test("devices without locations do not imply a recent position", async () => {
  const { element } = await dashboard([{ last_seen: new Date().toISOString() }]);
  assert.equal(element("metric-latest").textContent, "—");
});

test("All removes the hours restriction from the location request", async () => {
  const { all, urls } = await dashboard([]);
  assert.equal(urls.at(-1), "/api/locations?limit=5000&hours=24");
  all.listeners.click();
  await new Promise(setImmediate);
  assert.equal(urls.at(-1), "/api/locations?limit=5000");
});


test("custom local date inputs are sent as UTC instants", async () => {
  const { element, urls } = await dashboard([]);
  element("start-time").value = "2026-08-03T09:00";
  element("end-time").value = "2026-08-03T12:00";
  element("apply-range").listeners.click();
  await new Promise(setImmediate);
  const params = new URL(urls.at(-1), "http://localhost").searchParams;
  assert.equal(params.get("start"), new Date("2026-08-03T09:00").toISOString());
  assert.equal(params.get("end"), new Date("2026-08-03T12:00").toISOString());
  assert.equal(params.has("hours"), false);
});
