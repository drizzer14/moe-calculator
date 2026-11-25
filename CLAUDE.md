# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**14th_ua's MoE Calculator** (`com.14th_ua.moe_calculator`) — a World of Tanks (Wargaming EU / NA / Asia) Garage mod.
Hard dependency: **OpenWG GameFace**. Player-facing docs live in this repo's
`README.md` / `INSTALL.md`.

Client/mod versions rot at every client upgrade — this file is NOT the source of truth for
them. Read: **deploy target** = `deploy.local.json` (`"version"`); **mod version** = `src/meta.xml`
(`<version>`); **what the client actually is** = the game's own `version.xml`.

## The one rule that bites everywhere

The game runs compiled `.pyc`, and **bytecode is version-locked**: package with
**Python 2.7.18** (`C:\Python27\python.exe`) — Python 3 bytecode will NOT load.
Tests and dev tools run on **Python 3.13**. `ruff` lint (plus a Python 2.7 compile) runs on
every edited `src/**/*.py` via the PostToolUse hook; there is no npm or CI, and builds are
plain Python scripts.

## Never weaken a check

Fix the code when pytest, `ruff`, `py_compile`, or a build check fails — never loosen the
check. No `|| true`, no deleted rule, no skipped test. Every suppression carries a concrete
reason on the same line (`# noqa: F401 -- re-exported for the bridge`).

## Skill drift rule

After every gated iteration, run the retrospect → scribe → commit drift pass (see
`orchestrator` § Skill drift rule).

## Task-scoped skills

Situational guidance lives in the installed **`wotmod`** plugin's skills (loaded on demand by
their `description`; see the plugin's `skills/` for the current set) — for substantial work
start with **orchestrator**. Do not duplicate them here.

Project-specific detail (this mod's exact file tree, its widget DOM, its version
files) belongs in this repo's own `.claude/skills/`, which should reference the
harness skills for the shared pattern.
