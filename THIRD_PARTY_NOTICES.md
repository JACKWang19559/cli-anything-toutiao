# Third-party notices

## CLI-Anything

- Project: https://github.com/HKUDS/CLI-Anything
- Revision: `34f519533bc175d2fe287ab8316b0dd99bb9cc43`
- License: Apache License 2.0; see [LICENSE](LICENSE).
- Original file: `cli-anything-plugin/repl_skin.py`
- Local copy: `agent-harness/cli_anything/toutiao/utils/repl_skin.py`

The terminal skin is copied from CLI-Anything. This harness also follows the upstream Codex skill, HARNESS methodology, namespace packaging, CLI entrypoint conventions, and skill distribution pattern. The Toutiao backend and local draft implementation are project-specific additions. This project is not presented as an official Toutiao product or an upstream CLI-Anything release.

Any project-specific adjustments to the copied skin must retain its provenance and be recorded here. Its caller may override the upstream skill-install hint because this project's skill is bundled locally and is not yet available in HKUDS/CLI-Anything.

## Runtime dependencies

Click and prompt-toolkit are installed as Python dependencies and retain their respective upstream licenses. `ego-browser` is a separately installed runtime; it is invoked as an external browser backend and is not redistributed with this package.
