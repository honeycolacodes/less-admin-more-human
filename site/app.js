/*
 * Less admin. More human. Interactive prompt builder.
 *
 * Reads data/prompts.json (the same file that builds the PDF and the Markdown
 * pages), turns every {{field}} in a prompt into a text box, and keeps a live,
 * copyable preview. Everything runs in the browser: nothing is sent anywhere.
 */
(() => {
  "use strict";

  const state = { data: null, current: null, values: {} };
  const $ = (id) => document.getElementById(id);

  const ICONS = {
    arrow: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>',
    copy: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>',
  };

  /* ---------- tiny DOM helpers ---------- */

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value == null || value === false) continue;
      if (key === "class") el.className = value;
      else if (key === "style") el.style.cssText = value;
      else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
      else el.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child == null || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  function icon(name) {
    // Only ever called with the fixed strings in ICONS, never with data.
    const tpl = document.createElement("template");
    tpl.innerHTML = ICONS[name];
    return tpl.content.firstChild;
  }

  function colorVars(name) {
    const c = state.data.colors[name];
    return `--tint:${c.tint};--deep:${c.deep};--label:${c.label}`;
  }

  /* ---------- prompt rendering lives in render.js, shared with the parity test ---------- */

  const { segments, renderText } = window.LAMH;

  const valuesFor = (id) => (state.values[id] ||= {});

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const area = h("textarea", { style: "position:fixed;opacity:0", "aria-hidden": "true" });
      area.value = text;
      document.body.append(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    }
  }

  /* ---------- static sections ---------- */

  function renderPage() {
    const d = state.data;
    $("byline").textContent = `${d.author.name} · ${d.author.role}`;
    $("tagline").textContent = d.tagline;
    $("chips").replaceChildren(...d.cover_chips.map((chip) => h("li", null, chip)));
    $("how").replaceChildren(...d.how_it_works.map((s) => h("li", null, h("span", null, h("strong", null, s.verb), " ", s.text))));

    $("pick-grid").replaceChildren(
      ...d.prompts.map((p) =>
        h(
          "button",
          { type: "button", class: "pick", style: colorVars(p.color), "data-id": p.id, "aria-pressed": "false", "aria-controls": "workspace", onclick: () => select(p.id, "smooth") },
          h("span", { class: "pick-top" }, h("span", { class: "pick-num" }, p.number), h("span", { class: "pick-tag" }, p.bonus ? "Bonus" : p.time)),
          h("span", { class: "pick-trigger" }, `“${p.trigger}”`),
          h("span", { class: "pick-cta" }, icon("arrow"), p.cta)
        )
      )
    );

    $("fix-list").replaceChildren(
      ...d.fixes.map((fix) => {
        let body;
        if (fix.lead) {
          body = [h("p", null, h("strong", null, fix.lead), " ", fix.text)];
        } else {
          const button = h("button", { type: "button", class: "btn", "aria-label": `Copy reply: ${fix.reply}` }, icon("copy"), "Copy");
          button.addEventListener("click", async () => {
            if (await copyText(fix.reply)) flash(button, "Copied");
          });
          body = [h("strong", null, "Reply with:"), h("div", { class: "fix-reply" }, h("code", null, fix.reply), button)];
        }
        if (fix.note) body.push(h("p", { class: "fix-note" }, fix.note));
        return h("div", { class: "fix", style: colorVars(fix.color) }, h("div", { class: "fix-name" }, fix.problem), h("div", { class: "fix-body" }, body));
      })
    );
    $("before-list").replaceChildren(...d.before_you_use.map((b) => h("li", null, h("span", null, h("strong", null, b.lead), " ", b.text))));

    $("closing-title").textContent = d.closing.title;
    $("closing-text").textContent = d.closing.text;
    if (d.author.linkedin) {
      $("closing-cta").replaceChildren(`${d.closing.cta_label} `, h("a", { href: d.author.linkedin, rel: "me noopener" }, `${d.author.name} on LinkedIn`));
      $("closing-cta").hidden = false;
    }
    $("footer-credit").replaceChildren(`Made by ${d.author.name}, ${d.author.role}. `, h("a", { href: "less-admin-more-human.pdf", download: true }, "Get the PDF"), ".");
    $("footer-note").textContent = d.further_reading;
  }

  function flash(button, label) {
    const original = [...button.childNodes];
    button.replaceChildren(icon("copy"), label);
    setTimeout(() => button.replaceChildren(...original), 1800);
  }

  /* ---------- the workspace for one prompt ---------- */

  // scroll: false = stay put, "smooth" = after a click, "instant" = arriving from a shared link.
  function select(id, scroll) {
    const prompt = state.data.prompts.find((p) => p.id === id);
    if (!prompt) return;
    state.current = prompt;
    document.querySelectorAll(".pick").forEach((el) => el.setAttribute("aria-pressed", String(el.dataset.id === id)));
    renderWorkspace(prompt);
    if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
    if (scroll) {
      const ws = $("workspace");
      ws.scrollIntoView({ block: "start", behavior: scroll === "instant" ? "instant" : "smooth" });
      $("ws-title").focus({ preventScroll: true });
    }
  }

  function renderWorkspace(p) {
    const ws = $("workspace");
    const values = valuesFor(p.id);
    const output = h("pre", { class: "output-body", id: "output", tabindex: "0", "aria-label": "Your prompt, with your details filled in" });
    const status = h("p", { class: "status", role: "status", "aria-live": "polite" });
    const copyButton = h("button", { type: "button", class: "btn btn-yellow" }, icon("copy"), "Copy prompt");

    const update = () => {
      const pieces = segments(p, values);
      output.replaceChildren(...pieces.map((piece) => (piece.kind === "text" ? piece.value : h("span", { class: piece.kind }, piece.kind === "blank" ? `[${piece.value}]` : piece.value))));
      const blanks = pieces.filter((piece) => piece.kind === "blank").length;
      status.className = "status";
      status.textContent = blanks ? `${blanks} blank${blanks > 1 ? "s" : ""} left. You can copy now and fill ${blanks > 1 ? "them" : "it"} in the chat.` : "All filled in. Ready to copy.";
    };

    copyButton.addEventListener("click", async () => {
      const pieces = segments(p, values);
      const blanks = pieces.filter((piece) => piece.kind === "blank").length;
      if (await copyText(renderText(p, values))) {
        status.className = "status ok";
        status.textContent = blanks ? `Copied. ${blanks} blank${blanks > 1 ? "s are" : " is"} still in [brackets] for you to fill.` : "Copied. Paste it into your AI chat.";
        flash(copyButton, "Copied");
      } else {
        status.textContent = "Copy did not work here. Select the text and copy it yourself.";
      }
    });

    const fields = p.fields.map((field) => {
      const id = `f-${p.id}-${field.key}`;
      const area = h("textarea", { id, name: field.key, placeholder: field.hint, rows: "4" });
      area.value = values[field.key] || "";
      area.addEventListener("input", () => {
        values[field.key] = area.value;
        update();
      });
      return h("div", { class: "field" }, h("label", { for: id }, field.label), area);
    });

    const clear = h("button", { type: "button", class: "link-btn" }, "Clear all");
    clear.addEventListener("click", () => {
      Object.keys(values).forEach((key) => delete values[key]);
      ws.querySelectorAll("textarea").forEach((area) => (area.value = ""));
      update();
      ws.querySelector("textarea")?.focus();
    });

    const out = p.example.output;
    const exampleOutput = Array.isArray(out) ? out.map((line) => h("span", { style: "display:block" }, h("strong", null, line.lead), " ", line.text)) : out;

    const index = state.data.prompts.indexOf(p);
    const next = state.data.prompts[(index + 1) % state.data.prompts.length];
    const nextButton = h("button", { type: "button", class: "btn" }, `Next: ${next.title}`);
    nextButton.addEventListener("click", () => select(next.id, "smooth"));

    ws.style.cssText = colorVars(p.color);
    const blocks = [
      h("div", { class: "band" },
        h("div", { class: "band-num", "aria-hidden": "true" }, p.number),
        h("div", { class: "band-text" }, h("div", { class: "kicker" }, p.audience), h("h2", { class: "display", id: "ws-title", tabindex: "-1" }, p.title))
      ),
      h("div", { class: "meta" },
        h("div", { class: "meta-item" }, h("span", { class: "label" }, "Use it when"), h("strong", null, p.use_when)),
        h("div", { class: "meta-item" }, h("span", { class: "label" }, "Time"), h("strong", null, p.time)),
        h("div", { class: "meta-item" }, h("span", { class: "label" }, "Have ready"), h("strong", null, p.have_ready))
      ),
      p.blurb ? h("p", { class: "lede" }, p.blurb) : null,
      p.tells ? [h("div", { class: "label" }, "Watch for these tells"), h("ul", { class: "tells" }, p.tells.map((t) => h("li", null, t)))] : null,
      h("div", { class: "build" },
        h("form", { class: "fields", onsubmit: (e) => e.preventDefault() }, h("div", { class: "fields-head" }, h("h3", null, "Fill in the blanks"), clear), fields),
        h("div", { class: "output" }, h("div", { class: "output-head" }, h("span", { class: "kicker" }, "Your prompt"), copyButton), output, status)
      ),
      h("div", { class: "label" }, "Made-up example"),
      h("div", { class: "example-grid" },
        h("div", { class: "example" }, h("strong", null, "You paste"), h("span", null, p.example.input)),
        h("div", { class: "example result" }, h("strong", null, p.example.output_label), h("span", null, exampleOutput))
      ),
      h("div", { class: "label" }, "Then do this"),
      h("ul", { class: "next-steps" }, p.next_steps.map((step, i) => h("li", null, h("label", null, h("input", { type: "checkbox", id: `s-${p.id}-${i}` }), h("span", null, step))))),
      h("div", { class: "ws-nav" }, nextButton, h("a", { class: "btn", href: "#pick" }, "Pick a different prompt")),
    ];
    ws.replaceChildren(...blocks.flat().filter(Boolean));
    ws.hidden = false;
    update();
  }

  /* ---------- start ---------- */

  function route() {
    const id = decodeURIComponent(location.hash.slice(1));
    if (state.data.prompts.some((p) => p.id === id) && state.current?.id !== id) select(id, "instant");
  }

  async function start() {
    try {
      const response = await fetch("data/prompts.json");
      if (!response.ok) throw new Error(response.statusText);
      state.data = await response.json();
    } catch (error) {
      $("pick-grid").replaceChildren(h("p", null, "Could not load the prompts. If you opened this file directly, run: python scripts/build_site.py --serve"));
      return;
    }
    renderPage();
    route();
    window.addEventListener("hashchange", route);
  }

  start();
})();
