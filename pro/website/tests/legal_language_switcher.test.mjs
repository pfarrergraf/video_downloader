import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

const root = new URL("..", import.meta.url);
const read = (relative) => readFileSync(new URL(relative, root), "utf8");

test("legal language selector reflects the document actually on screen", () => {
  const script = read("legal-lang.js");

  // A saved homepage preference may only be changed by the user. It must not
  // make a German document visually claim to be an English or French one.
  assert.match(script, /const selectedCode = available\.includes\(current\) \? current/);
  assert.doesNotMatch(script, /available\.includes\(preferred\) \? preferred/);
  assert.match(script, /location\.href = lang === 'de' \? `\$\{doc\}\.html` : `\$\{doc\}\.\$\{lang\}\.html`/);
});

test("every translated legal document loads the shared language selector", () => {
  const legalFiles = readdirSync(root).filter((name) => /^(agb|datenschutz|impressum|rechtliches)(\.[a-z]+)?\.html$/.test(name));
  assert.ok(legalFiles.length > 0);
  for (const file of legalFiles) {
    assert.match(read(file), /<script src="legal-lang\.js"/, file);
  }
});
