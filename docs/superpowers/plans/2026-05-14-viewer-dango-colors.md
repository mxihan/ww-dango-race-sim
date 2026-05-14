# Viewer Dango Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every existing dango ID a fixed viewer color so known pieces no longer fall back to gray.

**Architecture:** Keep the existing `BoardView.vue` rendering path unchanged. Update the centralized `DANGO_COLORS` table in `viewer/src/colors.ts`, then verify the viewer build.

**Tech Stack:** Vue 3, Vite, TypeScript

---

## File Structure

- Modify `viewer/src/colors.ts`: extend `DANGO_COLORS` with all existing dango IDs.
- Do not modify trace schema, board rendering, simulator rules, or viewer layout.

## Task 1: Complete Fixed Dango Color Table

**Files:**
- Modify: `viewer/src/colors.ts`

- [ ] **Step 1: Replace the color table**

Update `DANGO_COLORS` to include all current known IDs:

```ts
export const DANGO_COLORS: Record<string, string> = {
  carlotta: '#ff6b6b',
  chisa: '#ffd166',
  lynae: '#06d6a0',
  mornye: '#8ecae6',
  aemeath: '#c77dff',
  shorekeeper: '#4cc9f0',
  augusta: '#e74c3c',
  iuno: '#3498db',
  phrolova: '#1abc9c',
  changli: '#2ecc71',
  jinhsi: '#e67e22',
  calcharo: '#9b59b6',
  phoebe: '#f78fb3',
  luuk_herssen: '#95a5a6',
  bu_king: '#f1c40f',
}
```

- [ ] **Step 2: Verify no rendering logic changed**

Confirm `viewer/src/components/BoardView.vue` still uses:

```ts
function dangoColor(id: string): string {
  return DANGO_COLORS[id] ?? '#888'
}
```

Expected: unknown IDs still fall back to gray.

- [ ] **Step 3: Build viewer**

Run from `viewer/`:

```powershell
npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 4: Commit**

Stage only the viewer color change for this task:

```powershell
git add viewer/src/colors.ts
git commit -m "feat(viewer): add colors for all dango pieces"
```

Expected: commit succeeds.

## Task 2: Commit Requested Sample Config Change

**Files:**
- Modify: `src/dango_sim/sample_config.py`

- [ ] **Step 1: Review existing diff**

Run:

```powershell
git diff -- src/dango_sim/sample_config.py
```

Expected: diff only changes which sample participants are active.

- [ ] **Step 2: Run Python tests**

Run:

```powershell
uv run pytest tests/test_sample_config.py
uv run pytest
```

Expected: tests pass with the requested sample participant selection.

- [ ] **Step 3: Commit sample config**

Run:

```powershell
git add src/dango_sim/sample_config.py
git commit -m "chore: update sample config participants"
```

Expected: commit succeeds.

## Final Verification

- [ ] **Step 1: Run viewer build**

```powershell
npm run build
```

from `viewer/`.

- [ ] **Step 2: Run Python tests**

```powershell
uv run pytest
```

from the repository root.

- [ ] **Step 3: Confirm status**

```powershell
git status --short
```

Expected: no modified tracked files remain. Pre-existing untracked files may remain.
