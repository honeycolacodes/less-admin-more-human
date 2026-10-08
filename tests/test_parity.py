"""The web tool and the Python build must render every prompt identically.

The PDF and Markdown come from lamh.content (Python); the web tool uses
site/render.js. This test feeds both the same prompts and the same tricky
inputs and compares the output character for character.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from lamh import content
from lamh.site import SITE_SRC

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

TRICKY_VALUES = [
    {},
    {"*": "simple"},
    {"*": "  padded  "},
    {"*": "   "},
    {"*": "multi\nline\n\nvalue"},
    {"*": "{{not_a_field}} stays literal"},
    {"*": "$1 $& $' replacement patterns"},
    {"*": "émoji 🙂 and “quotes”"},
]

NODE_SCRIPT = """
const { segments, renderText } = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map(({ prompt, values }) => ({
  text: renderText(prompt, values),
  blanks: segments(prompt, values).filter((p) => p.kind === "blank").map((p) => p.value),
}));
process.stdout.write(JSON.stringify(out));
"""


def _cases(library: content.Library) -> list[dict[str, Any]]:
    cases = []
    for prompt in library["prompts"]:
        for template in TRICKY_VALUES:
            keys = [f["key"] for f in prompt["fields"]]
            # "*" means: give every field this value; also try filling only the first field.
            values = dict.fromkeys(keys, template["*"]) if "*" in template else {}
            cases.append({"prompt": prompt, "values": values})
            if "*" in template and len(keys) > 1:
                cases.append({"prompt": prompt, "values": {keys[0]: template["*"]}})
    return cases


def test_python_and_javascript_render_identically(real_library: content.Library) -> None:
    cases = _cases(real_library)
    assert NODE is not None
    result = subprocess.run(
        [NODE, "-e", NODE_SCRIPT, str(SITE_SRC / "render.js")],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    js = json.loads(result.stdout)
    assert len(js) == len(cases)
    for case, js_out in zip(cases, js, strict=True):
        py_text = content.render_text(case["prompt"], case["values"])
        py_blanks = [
            value for kind, value in content.segments(case["prompt"], case["values"]) if kind == "field"
        ]
        label = f"{case['prompt']['id']} with {case['values']!r}"
        assert js_out["text"] == py_text, label
        assert js_out["blanks"] == py_blanks, label
