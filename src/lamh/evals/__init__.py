"""Prompt evals: run each prompt against a real model and check the answer follows the prompt's own rules.

A prompt that says "do not invent experience" is only as good as the model's
willingness to obey it. Each case in evals/cases.yaml fills a prompt's blanks
with realistic input, sends it to the model, then scores the answer two ways:

* rule checks, which are deterministic (word limits, banned phrases, required
  sections, no dates that were not in the input)
* rubric checks, where a grader model judges one yes-or-no criterion at a time
"""
