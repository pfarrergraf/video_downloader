// Minimal shim of the Cloudflare D1 binding surface used by
// pro/website/functions/_affiliate*.js, backed by node:sqlite so tests run
// the real schema.sql + migrations/*.sql against a real SQLite engine
// (matching the pattern tests/test_affiliate_program.py already uses on the
// Python side) instead of hand-rolled mock data.
//
// Deliberately only implements prepare().bind().first()/all()/run() and
// batch() -- the only D1 surface _affiliate*.js touches.
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { readdirSync } from "node:fs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEBSITE = path.resolve(HERE, "..", "..");

class FakeStatement {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.params = [];
  }

  bind(...params) {
    this.params = params;
    return this;
  }

  async first() {
    const row = this.db.prepare(this.sql).get(...this.params);
    return row ?? null;
  }

  async all() {
    const rows = this.db.prepare(this.sql).all(...this.params);
    return { results: rows };
  }

  async run() {
    const info = this.db.prepare(this.sql).run(...this.params);
    return { meta: { changes: Number(info.changes), last_row_id: info.lastInsertRowid } };
  }
}

export class FakeD1 {
  constructor() {
    this.db = new DatabaseSync(":memory:");
    this.db.exec("PRAGMA foreign_keys = ON");
    this.db.exec(readFileSync(path.join(WEBSITE, "schema.sql"), "utf8"));
    const migrationsDir = path.join(WEBSITE, "migrations");
    for (const file of readdirSync(migrationsDir).filter((f) => f.endsWith(".sql")).sort()) {
      this.db.exec(readFileSync(path.join(migrationsDir, file), "utf8"));
    }
  }

  prepare(sql) {
    return new FakeStatement(this.db, sql);
  }

  async batch(statements) {
    const results = [];
    for (const statement of statements) {
      results.push(await statement.run());
    }
    return results;
  }
}

export function makeEnv(overrides = {}) {
  return { DB: new FakeD1(), REFERRAL_HASH_SALT: "test-salt", ...overrides };
}
