<template>
  <div class="event-log" ref="logContainer">
    <div
      v-for="(event, i) in events"
      :key="i"
      class="event-row"
      :class="{ active: i === currentIndex, [event.kind]: true }"
      @click="$emit('select', i)"
      :ref="(el) => { if (i === currentIndex) activeRow = el as HTMLElement }"
    >
      <span class="event-round">R{{ event.round }}</span>
      <span class="event-text">{{ formatEvent(event) }}</span>
    </div>
    <div v-if="events.length === 0" class="empty">No events</div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { TraceEvent, SkillData, MoveData, TileData, BuKingData, FinishData } from '../types'

const props = defineProps<{
  events: TraceEvent[]
  currentIndex: number
}>()

defineEmits<{
  select: [index: number]
}>()

const logContainer = ref<HTMLElement | null>(null)
const activeRow = ref<HTMLElement | null>(null)

function formatEvent(event: TraceEvent): string {
  switch (event.kind) {
    case 'skill': {
      const d = event.data as SkillData
      return `🎯 ${d.dango_id} → ${d.hook_name}`
    }
    case 'move': {
      const d = event.data as MoveData
      return `➡️ ${d.dango_id} ${d.from}→${d.to}`
    }
    case 'tile': {
      const d = event.data as TileData
      return `⚡ ${d.tile} at pos ${d.position}`
    }
    case 'bu_king': {
      const d = event.data as BuKingData
      return `👑 Bu King ${d.path.join('→')}`
    }
    case 'finish': {
      const d = event.data as FinishData
      return `🏁 ${d.group.join(', ')} finished`
    }
  }
}

watch(() => props.currentIndex, () => {
  activeRow.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
</script>

<style scoped>
.event-log {
  height: 100%;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}
.event-row {
  padding: 4px 8px;
  cursor: pointer;
  border-left: 3px solid transparent;
  display: flex;
  gap: 8px;
  transition: background 0.1s;
}
.event-row:hover { background: rgba(255,255,255,0.05); }
.event-row.active { background: rgba(255,255,255,0.1); border-left-color: #fff; }
.event-row.skill { background-color: #1a3a5c; }
.event-row.skill.active { background-color: #2a4a6e; }
.event-row.move { background-color: #1a3c1a; }
.event-row.move.active { background-color: #2a4a2a; }
.event-row.tile { background-color: #3c3a1a; }
.event-row.tile.active { background-color: #4a4a2a; }
.event-row.bu_king { background-color: #2a1a3c; }
.event-row.bu_king.active { background-color: #3a2a4e; }
.event-row.finish { background-color: #3c3a1a; }
.event-row.finish.active { background-color: #5a4a2a; }
.event-round { color: #888; min-width: 30px; }
.event-text { flex: 1; }
.empty { color: #666; padding: 16px; text-align: center; }
</style>
