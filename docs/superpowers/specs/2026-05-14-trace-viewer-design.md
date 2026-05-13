# Trace Viewer Design

**Goal:** A Vue 3 SPA that loads `trace.json` and replays dango races visually — board view with dango pieces + event timeline, navigable event-by-event or auto-playing.

**Architecture:** Vite + Vue 3 app in `viewer/` at project root. Static build, no backend. User loads trace files via file picker or drag-and-drop.

**Tech Stack:** Vue 3, Vite, TypeScript

---

## Layout

Vertical split: **Board (left)** | **Event log (right)**, with a **control bar** spanning the full width at the bottom.

### Board Panel (Left)

- 4 rows × 8 columns wrapped grid showing all 32 tiles (0–31 + finish)
- Snake-pattern wrapping: row 0 goes left→right, row 1 right→left, etc.
- Special tiles color-coded with icons:
  - **Booster** (pos 3, 11, 16, 23): green border, ⚡ icon, "+N" label
  - **Inhibitor** (pos 10, 28): red border, 🛑 icon, "-N" label
  - **SpaceTimeRift** (pos 6, 20): purple border, 🌀 icon
  - **Start/Finish** (pos 0): bright green background
- Dango pieces rendered as colored circles stacked vertically on their tile
- The currently active dango (from the selected event) gets a glow/highlight ring
- Tile the dango lands on flashes briefly on move events

### Event Panel (Right)

- Scrollable list of all events in the selected race
- Each event is color-coded by kind:
  - `skill`: blue background tint
  - `move`: green background tint
  - `tile`: yellow background tint
  - `bu_king`: purple background tint
  - `finish`: gold background tint
- Event display format:
  - `skill`: `R{round} 🎯 {dango_id} → {hook_name}`
  - `move`: `R{round} ➡️ {dango_id} {from}→{to}`
  - `tile`: `R{round} ⚡ {tile_type} at pos {position}`
  - `bu_king`: `R{round} 👑 Bu King moves {path}`
  - `finish`: `R{round} 🏁 {group} finished`
- Clicking an event sets the board to that event's state and highlights the event row
- Auto-scrolls to follow the current event during playback

### Control Bar (Bottom)

- **Race tabs**: clickable tabs for each race in the file (Race 1, Race 2, ...)
- **Navigation**: ◀ Prev event | ▶ Next event | ⏮ First | ⏭ Last
- **Playback**: ▶ Play / ⏸ Pause auto-advance
- **Speed**: slider (0.5x–5x, default 1x)
- **Counter**: "Event 42 / 212 · Round 5"
- **File load**: "Load trace.json" button + drag-and-drop zone (shown when no file is loaded)

## Data Flow

1. Page loads empty state with file picker / drop zone
2. User selects `trace.json` via file input or drag-and-drop
3. `FileReader` reads and parses JSON into an array of races
4. `ref<number>` for `selectedRace` (default 0) and `currentEventIndex` (default 0)
5. Board renders from `races[selectedRace][currentEventIndex].state`
6. Playback uses `setInterval` to increment `currentEventIndex`, speed controlled by slider
7. Event click sets `currentEventIndex` directly

## Color Scheme

Dark theme (#1a1a2e background).

Dango colors (fixed per ID):
| Dango | Color | Hex |
|-------|-------|-----|
| augusta | Red | #e74c3c |
| iuno | Blue | #3498db |
| changli | Green | #2ecc71 |
| jinhsi | Orange | #e67e22 |
| calcharo | Purple | #9b59b6 |
| phrolova | Teal | #1abc9c |
| bu_king | Gold | #f1c40f |

## Trace JSON Schema

Input file is an array of races. Each race is an array of events:

```json
[
  [
    {
      "kind": "skill",
      "round": 1,
      "data": { "dango_id": "augusta", "hook_name": "on_round_start" },
      "state": {
        "positions": { "0": ["augusta", "iuno", ...], "5": ["jinhsi"] },
        "laps_completed": { "augusta": 0, ... },
        "round_number": 1
      }
    },
    ...
  ],
  ...
]
```

Event kinds and their `data` fields:
- `skill`: `{ dango_id, hook_name }`
- `move`: `{ dango_id, from, to, group, path }`
- `tile`: `{ group, position, next_position, tile }`
- `bu_king`: `{ roll, path }`
- `finish`: `{ group, position }`

## Project Structure

```
viewer/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── components/
│   │   ├── BoardView.vue      # 4×8 tile grid with dango pieces
│   │   ├── EventLog.vue       # Scrollable event list
│   │   ├── ControlBar.vue     # Playback controls + race tabs
│   │   └── FileLoader.vue     # Drag-and-drop / file picker overlay
│   ├── types.ts               # TypeScript interfaces for trace data
│   └── colors.ts              # Dango color map + tile color map
```

## Testing

- No unit tests needed for a viewer tool
- Manual verification: load a trace.json, step through events, verify board state matches
- Build produces `viewer/dist/` that can be opened as static files or served via `npx serve viewer/dist`
