<template>
  <div class="board-view">
    <div class="grid">
      <template v-for="(row, ri) in GRID" :key="ri">
        <div
          v-for="pos in row"
          :key="pos"
          class="tile"
          :class="[tileClass(pos), { flash: flashingTile === pos }]"
          :style="tileStyle(pos)"
        >
          <span class="tile-label">{{ pos === 0 ? 'S/F' : pos }}</span>
          <span v-if="tileIcon(pos)" class="tile-icon">{{ tileIcon(pos) }}</span>
          <div class="pieces">
            <div
              v-for="dango in dangosAt(pos)"
              :key="dango"
              class="piece"
              :class="{ active: isActiveDango(dango) }"
              :style="{ backgroundColor: dangoColor(dango) }"
            >
              <span class="piece-label">{{ dangoLabel(dango) }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { GRID, getTileInfo } from '../board'
import { DANGO_COLORS, TILE_STYLES } from '../colors'
import type { StateSnapshot, EventData, MoveData } from '../types'

const props = defineProps<{
  state: StateSnapshot | null
  activeDangoId: string | null
  eventData: EventData | null
}>()

const flashingTile = ref<number | null>(null)

watch(() => props.eventData, (data) => {
  if (data && 'from' in data) {
    const move = data as MoveData
    flashingTile.value = move.to
    setTimeout(() => { flashingTile.value = null }, 400)
  }
})

function dangosAt(pos: number): string[] {
  if (!props.state) return []
  return props.state.positions[String(pos)] ?? []
}

function tileClass(pos: number): string {
  const info = getTileInfo(pos)
  return info.type !== 'normal' ? `tile-${info.type.toLowerCase()}` : ''
}

function tileStyle(pos: number): Record<string, string> {
  const info = getTileInfo(pos)
  if (pos === 0) return { background: '#2d5a2d' }
  if (info.type === 'normal') return {}
  const style = TILE_STYLES[info.type]
  return { borderColor: style.border, borderWidth: '2px', borderStyle: 'solid' }
}

function tileIcon(pos: number): string {
  const info = getTileInfo(pos)
  if (info.type === 'normal') return ''
  return TILE_STYLES[info.type].icon
}

function dangoColor(id: string): string {
  return DANGO_COLORS[id] ?? '#888'
}

function dangoLabel(id: string): string {
  return id.slice(0, 2).toUpperCase()
}

function isActiveDango(id: string): boolean {
  return props.activeDangoId === id
}
</script>

<style scoped>
.board-view {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 8px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 4px;
  width: 100%;
  max-width: 520px;
}
.tile {
  aspect-ratio: 1;
  background: #2a2a3e;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 2px;
  position: relative;
  min-height: 60px;
}
.tile-label { font-size: 10px; color: #666; }
.tile-icon { font-size: 12px; }
.pieces {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  justify-content: center;
  margin-top: auto;
  margin-bottom: 2px;
}
.piece {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid rgba(255,255,255,0.4);
  transition: box-shadow 0.2s;
}
.piece.active {
  border-color: #fff;
  box-shadow: 0 0 8px 2px rgba(255,255,255,0.6);
}
.piece-label {
  font-size: 7px;
  color: #fff;
  font-weight: bold;
  text-shadow: 0 0 2px rgba(0,0,0,0.8);
}
.tile.flash {
  animation: tileFlash 0.4s ease-out;
}
@keyframes tileFlash {
  0% { background: rgba(74, 144, 217, 0.4); }
  100% { background: #2a2a3e; }
}
</style>
