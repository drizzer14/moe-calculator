# RESEARCH.md

WoT-modding background for **14th_ua's MoE Calculator**.

For the general modding stack — how a `.wotmod` loads, the OpenWG GameFace injection
model, Wulf ViewModels, the two-Python split, the community references
(`modding.wot-tools.dev`, `wgmods.dev`) and the WoT Fair Play rules — see the
**`wotmod-basics`** harness skill. Do not duplicate that material here; this file is
only for what is specific to THIS mod.

## Resolved scope (this mod)

_Fill this in as you pin down the mod's behavior. Suggested sections:_

- **What it does** — the player-facing feature, in one or two sentences.
- **Where it mounts** — the hangar view / sub-view it injects into, and why.
- **Data it reads** — the game subsystems the adapter reads (and the decompiled-client
  symbols verified for each).
- **Modes / states** — the bar (or widget) states and their priority order.
- **Actions it performs** — the write-side flows (research, unlock, navigate) and the
  WG APIs they go through.
- **Open questions** — anything still unverified against the live client.
