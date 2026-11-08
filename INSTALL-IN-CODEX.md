# Install using Codex

Give Codex the location of this repository and the prompt below. This authorization covers only installation, not a real delegated task.

```text
Install the Astra orchestration workflow from this repository branch.

Read README.md, install.py, POLICY.md, WORKER-INSTRUCTIONS.md,
skill/astra-flash-orchestrator/SKILL.md, and
skill/astra-flash-orchestrator/references/routing.md first.

This fork makes the implementation worker configurable. For this installation,
use the default worker:

- model: gpt-5.6-luna
- reasoning effort: high
- native subagent requirement: multi_agent_version v2

Preserve my current GPT-6 Astra root model and reasoning effort, existing Codex
Router, config.toml, authentication, permissions, and unrelated instructions.
Do not install another runtime or Router, change credentials, restart services,
or modify provider configuration.

Do not add, change, or remove [agents].default_subagent_model or
[agents].default_subagent_reasoning_effort. The package's named
astra_flash_builder role pins its own worker model and effort. The legacy role
name is retained for compatibility even though this fork defaults to Luna.

Verify Python 3.11+, native subagent/custom-role support, and that the effective
local Codex model catalog contains gpt-5.6-luna exactly once with
multi_agent_version = "v2". Verify that high is a supported reasoning effort.
Do not edit the catalog or config.toml to make this true. If the route is not
v2, stop and report the discrepancy.

Run the offline test suite first. On Windows, a symlink safety fixture may be
skipped only when the OS reports WinError 1314 because symlink privilege is
unavailable; that skip is expected in this fork and must not hide any other test
failure.

Then run install.py as a dry run using:

python -B install.py --worker-model gpt-5.6-luna --worker-effort high

Inspect the proposed writes. They must be limited to the documented skill,
astra_flash_builder role, managed AGENTS policy block, and package backup/receipt
locations. config.toml, Router files, provider credentials, and unrelated agent
files must remain unchanged.

If the dry run is clean, apply with:

python -B install.py --worker-model gpt-5.6-luna --worker-effort high --apply

Then run the static doctor with the same worker binding:

python -B skill/astra-flash-orchestrator/scripts/doctor.py --worker-model gpt-5.6-luna --worker-effort high

Do not launch a worker or run paid inference during installation.

Report:
- installed paths
- observed Astra root model and effort
- installed worker model and effort
- test results, including any Windows symlink skips
- doctor result
- generated undo receipt
- confirmation that config/auth/provider files were unchanged
- any remaining runtime limitation

Finally tell me to fully quit and reopen Codex. The first separately authorized
useful $astra-flash-orchestrator task should verify from host/router metadata that
the child actually ran as gpt-5.6-luna. Do not use the child's self-reported
identity as evidence.
```
