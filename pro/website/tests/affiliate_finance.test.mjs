import test from "node:test";
import assert from "node:assert/strict";
import {
  commissionForSaleNumber,
  expectedCommissionForCount,
  isReservedPartnerCode,
  normalizePartnerCode,
  normalizeSlug,
} from "../functions/_affiliate.js";

test("fixed commission boundaries are exact integer cents", () => {
  const cases = new Map([
    [1, 200], [10, 200], [11, 250], [50, 250], [51, 300],
    [100, 300], [101, 350], [500, 350], [501, 400], [10000, 400],
  ]);
  for (const [saleNumber, expected] of cases) {
    assert.equal(commissionForSaleNumber(saleNumber), expected);
  }
});

test("cumulative commission ceiling follows the same tier schedule", () => {
  assert.equal(expectedCommissionForCount(0), 0);
  assert.equal(expectedCommissionForCount(10), 2000);
  assert.equal(expectedCommissionForCount(11), 2250);
  assert.equal(expectedCommissionForCount(50), 12000);
  assert.equal(expectedCommissionForCount(100), 27000);
  assert.equal(expectedCommissionForCount(500), 167000);
  assert.equal(expectedCommissionForCount(501), 167400);
  for (const count of [1, 17, 73, 220, 999]) {
    let iterative = 0;
    for (let sale = 1; sale <= count; sale += 1) iterative += commissionForSaleNumber(sale);
    assert.equal(expectedCommissionForCount(count), iterative);
    assert.ok(iterative <= count * 400, "no cumulative total may exceed 4 EUR per sale");
  }
});

test("invalid sale numbers fail closed", () => {
  for (const value of [0, -1, 1.5, NaN, "1", null]) {
    assert.throws(() => commissionForSaleNumber(value), RangeError);
  }
});

test("partner identifiers are normalized and reserved brands rejected", () => {
  assert.equal(normalizePartnerCode(" Technik Max! "), "TECHNIKMAX");
  assert.equal(normalizeSlug("Tëchnik Max"), "technik-max");
  assert.equal(isReservedPartnerCode("DownloadThat"), true);
  assert.equal(isReservedPartnerCode("Support"), true);
  assert.equal(isReservedPartnerCode("TechnikMax"), false);
});
