<template>
  <div class="control-bar">
    <div class="race-tabs">
      <button
        v-for="(_, i) in races"
        :key="i"
        class="race-tab"
        :class="{ active: i === selectedRace }"
        @click="$emit('selectRace', i)"
      >
        Race {{ i + 1 }}
      </button>
    </div>
    <div class="controls">
      <button @click="$emit('first')" title="First event">⏮</button>
      <button @click="$emit('prev')" title="Previous event">◀</button>
      <button @click="$emit('togglePlay')" :title="isPlaying ? 'Pause' : 'Play'">
        {{ isPlaying ? '⏸' : '▶' }}
      </button>
      <button @click="$emit('next')" title="Next event">▶</button>
      <button @click="$emit('last')" title="Last event">⏭</button>
    </div>
    <div class="speed-control">
      <label>Speed:</label>
      <input type="range" min="0.5" max="5" step="0.5" :value="speed"
             @input="$emit('update:speed', Number(($event.target as HTMLInputElement).value))" />
      <span>{{ speed }}x</span>
    </div>
    <div class="counter">
      Event {{ currentIndex + 1 }}/{{ totalEvents }} · Round {{ currentRound }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  races: unknown[]
  selectedRace: number
  currentIndex: number
  totalEvents: number
  currentRound: number
  isPlaying: boolean
  speed: number
}>()

defineEmits<{
  selectRace: [index: number]
  prev: []
  next: []
  first: []
  last: []
  togglePlay: []
  'update:speed': [value: number]
}>()
</script>

<style scoped>
.control-bar {
  padding: 10px 16px;
  border-top: 1px solid #2a2a4a;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.race-tabs { display: flex; gap: 4px; flex-wrap: wrap; max-height: 62px; overflow-y: auto; }
.race-tab {
  padding: 4px 12px;
  background: #2a2a3e;
  color: #aaa;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.race-tab.active { background: #4a90d9; color: #fff; }
.race-tab:hover:not(.active) { background: #3a3a5a; }
.controls { display: flex; gap: 4px; }
.controls button {
  padding: 6px 10px;
  background: #3a3a5a;
  color: #e0e0e0;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}
.controls button:hover { background: #4a4a7a; }
.speed-control {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #aaa;
}
.speed-control input[type="range"] { width: 80px; }
.counter { font-size: 12px; color: #888; margin-left: auto; }
</style>
