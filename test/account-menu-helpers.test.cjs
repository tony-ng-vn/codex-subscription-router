const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const sourcePath = path.join(__dirname, "..", "ui", "account-menu.js");
const source = fs.readFileSync(sourcePath, "utf8");

function loadFunction(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} must exist in account-menu.js`);
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) {
      return vm.runInNewContext(`(${source.slice(start, index + 1)})`);
    }
  }
  throw new Error(`Could not parse ${name}`);
}

test("separates the subscription name from quiet metadata", () => {
  const identity = loadFunction("codexMuxAccountIdentity");
  assert.deepEqual(
    { ...identity({ label: "Primary - Team - Preferred", planLabel: "Team", preferred: true }) },
    { name: "Primary", metadata: ["Team", "Preferred"] },
  );
  assert.deepEqual(
    { ...identity({ label: "Subscription 2 - Team - US", planLabel: "Team", preferred: false }) },
    { name: "Subscription 2", metadata: ["Team", "US"] },
  );
});

test("maps remaining usage to accessible severity states", () => {
  const usageState = loadFunction("codexMuxUsageState");
  assert.equal(usageState(100).level, "normal");
  assert.equal(usageState(50).level, "normal");
  assert.equal(usageState(36).level, "warning");
  assert.equal(usageState(19).level, "low");
  assert.equal(usageState(0).level, "critical");
  assert.equal(usageState(36).ariaLabel, "36% usage remaining");
});

test("keeps the earliest usable manual reset expiry", () => {
  const resetSummary = loadFunction("codexMuxResetSummary");
  const result = resetSummary({
    available_count: 2,
    credits: [
      { status: "available", is_supported_by_plan: true, expires_at: "2026-09-10T00:00:00Z" },
      { status: "available", is_supported_by_plan: true, expires_at: "2026-08-28T00:00:00Z" },
      { status: "redeemed", is_supported_by_plan: true, expires_at: "2026-08-24T00:00:00Z" },
    ],
  });
  assert.deepEqual(
    { ...result },
    { count: 2, expiresAt: "2026-08-28T00:00:00Z" },
  );
  assert.deepEqual(
    { ...resetSummary({ available_count: 0, credits: [] }) },
    { count: 0, expiresAt: null },
  );
});

test("formats valid dates and adds relative urgency only when useful", () => {
  const timing = loadFunction("codexMuxDateTiming");
  const now = new Date("2026-08-23T12:00:00-07:00");
  assert.deepEqual(
    { ...timing("2026-08-24T12:00:00-07:00", now) },
    { dateLabel: "Aug 24", relativeLabel: "tomorrow", urgent: true },
  );
  assert.deepEqual(
    { ...timing("2026-08-28T12:00:00-07:00", now) },
    { dateLabel: "Aug 28", relativeLabel: "in 5 days", urgent: false },
  );
  assert.equal(timing(null, now), null);
  assert.equal(timing("not-a-date", now), null);
});
