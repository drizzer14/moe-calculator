# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**14th_ua's MoE Calculator** (`com.14th_ua.moe_calculator`) — a World of Tanks **EU 2.3.0.1** Garage mod.
Hard dependency: **OpenWG GameFace**. Player-facing docs live in this repo's
`README.md` / `INSTALL.md` (add them); WoT-modding background: `RESEARCH.md`.

## The one rule that bites everywhere

The game runs compiled `.pyc`, and **bytecode is version-locked**: package with
**Python 2.7.18** (`C:\Python27\python.exe`) — Python 3 bytecode will NOT load.
Tests and dev tools run on **Python 3.13**. There is no npm/linter/CI; builds are
plain Python scripts.

## Task-scoped skills

Detailed, situational guidance lives in the installed **`wotmod`** harness plugin
skills (loaded on demand to keep context tight) — do not duplicate it here:
- **wotmod-basics** — the WoT modding stack, file structure, load model, Fair Play, resources.
- **wotmod-architecture** — the engine-free domain / adapter / Wulf-bridge layering and the
  conventions that bite (listener re-arming, Wulf MAP-arg, engine-free domain) + `game-api`.
- **wotmod-build-deploy** — build the `.wotmod`, deploy locally, run pytest, hot-reload JS/CSS.
- **wotmod-debug-repl** — live in-client TCP REPL introspection and decompiled-source navigation.
- **wotmod-gameface-widget** — the Gameface HTML/CSS/JS widget: DOM, model observer, CSS quirks.
- **wotmod-release** — bump the version, tag, build the installer, publish the GH release.
- **wotmod-planner** — research each idea/bug and save an implementer-ready note under
  `TASKS/`, plus capture/prune the `TASKS.md` backlog.

Project-specific detail (this mod's exact file tree, its widget DOM, its version
files) belongs in this repo's own `.claude/skills/`, which should reference the
harness skills above for the shared pattern.
