/*
 * Prompt rendering for the web tool.
 *
 * This is the JavaScript twin of lamh.content.segments / render_text in Python.
 * tests/test_parity.py runs both on the same inputs and fails if they ever
 * disagree, so the prompt you copy online is the prompt in the PDF.
 *
 * Works as a browser global (window.LAMH) and as a Node module.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LAMH = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const FIELD = /\{\{\s*([a-z0-9_]+)\s*\}\}/g;

  /** Split a prompt into text, filled and blank pieces. */
  function segments(prompt, values) {
    values = values || {};
    const hints = Object.fromEntries(prompt.fields.map((f) => [f.key, f.hint]));
    const pieces = [];
    let cursor = 0;
    for (const match of prompt.prompt.matchAll(FIELD)) {
      if (match.index > cursor) pieces.push({ kind: "text", value: prompt.prompt.slice(cursor, match.index) });
      const value = (values[match[1]] || "").trim();
      pieces.push(value ? { kind: "filled", value } : { kind: "blank", value: hints[match[1]] });
      cursor = match.index + match[0].length;
    }
    if (cursor < prompt.prompt.length) pieces.push({ kind: "text", value: prompt.prompt.slice(cursor) });
    return pieces;
  }

  /** Render a prompt as plain text, with [hints] where values are missing. */
  function renderText(prompt, values) {
    return segments(prompt, values)
      .map((p) => (p.kind === "blank" ? `[${p.value}]` : p.value))
      .join("");
  }

  return { segments, renderText };
});
