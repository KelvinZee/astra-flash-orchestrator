# Native Codex routing

The installed setup has three separate jobs:

1. Codex selects the root and child models.
2. Codex Router publishes and routes the selected worker model.
3. This skill tells Astra when to plan, delegate, review, and integrate.

## Worker selection

This fork defaults the implementation worker to the native Codex route
`gpt-5.6-luna` at reasoning effort `high`. Codex Router currently publishes
that native model as a v2-capable subagent route when the user is authenticated
with ChatGPT.

The worker is configurable at install/doctor time:

```
--worker-model <catalog-model-id>
--worker-effort <supported-effort>
```

Environment equivalents are `ASTRA_WORKER_MODEL` and
`ASTRA_WORKER_EFFORT`.

Alternate workers are accepted only when the configured local model catalog
contains exactly that model and advertises `multi_agent_version: "v2"`. The
installer never edits the catalog to manufacture v2 support and never silently
substitutes another route.

The legacy role name `astra_flash_builder` is retained for compatibility with
existing prompts and policy, even when the pinned worker is not DeepSeek Flash.

## Installation bindings

The installer writes a standalone personal agent named
`astra_flash_builder` and pins both its model and explicit reasoning effort.
It does not require, inherit or change global
`[agents].default_subagent_model` or
`[agents].default_subagent_reasoning_effort` values, so unrelated subagents
keep their existing defaults. It leaves root settings, provider URLs,
credentials, and `config.toml` untouched.

The child inherits sandbox/approval settings; its `[agents].enabled = false`
prevents recursive subagent tools under the documented custom-agent format.

## Runtime check

Fully quit/reopen the host app, then start a session with Astra selected. Check
that the installed skill and role are visible. Run `doctor.py` with the same
worker model/effort used during installation. The optional
`--check-local-router` performs only a loopback `/models` GET, without a model
inference request, ambient proxies, or redirects.

For the first real delegated task, verify all of the following:

- The root thread remains Astra.
- Child thread/session metadata shows the exact worker model pinned by
  `routing.json` and the generated role.
- Router/host metadata confirms the actual child route used.
- The child executes a small useful task, changes only its scope, and returns
  test evidence; Astra reviews the result independently.

When metadata is unavailable, report that inference routing remains unverified.
A worker claiming its own model name is not routing evidence. A green router
health check alone is not an end-to-end test.

## Usage and privacy

Delegation sends task context and tool results to whichever worker provider the
operator explicitly selected. Native `gpt-5.6-luna` stays on the authenticated
Codex/OpenAI path; external routes use their configured provider. Preserve
provider-sharing restrictions on private repositories, use minimal necessary
context, and avoid production data and secrets.
