<template>
  <div class="app">
    <FileLoader v-if="!traceData" @loaded="onLoaded" />
    <template v-else>
      <div class="main-area">
        <div class="board-panel">
          <BoardView :state="currentState" :activeDangoId="activeDangoId" :eventData="currentEventData" />
        </div>
        <div class="event-panel">
          <EventLog :events="currentRace" :currentIndex="currentEventIndex" @select="(i: number) => currentEventIndex = i" />
        </div>
      </div>
      <ControlBar
        :races="traceData"
        :selectedRace="selectedRace"
        :currentIndex="currentEventIndex"
        :totalEvents="currentRace.length"
        :currentRound="currentEvent?.round ?? 0"
        :isPlaying="isPlaying"
        :speed="playSpeed"
        @selectRace="(i: number) => { selectedRace = i; currentEventIndex = 0 }"
        @prev="currentEventIndex = Math.max(0, currentEventIndex - 1)"
        @next="stepNext"
        @first="currentEventIndex = 0"
        @last="currentEventIndex = currentRace.length - 1"
        @togglePlay="togglePlay"
        @update:speed="playSpeed = $event"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { TraceFile, TraceEvent, SkillData, MoveData } from './types'
import FileLoader from './components/FileLoader.vue'
import BoardView from './components/BoardView.vue'
import EventLog from './components/EventLog.vue'
import ControlBar from './components/ControlBar.vue'

const traceData = ref<TraceFile | null>(null)
const selectedRace = ref(0)
const currentEventIndex = ref(0)
const isPlaying = ref(false)
const playSpeed = ref(1)
let playInterval: ReturnType<typeof setInterval> | null = null

const currentRace = computed(() => {
  if (!traceData.value) return [] as TraceEvent[]
  return traceData.value[selectedRace.value] ?? []
})

const currentEvent = computed<TraceEvent | null>(() => {
  const race = currentRace.value
  if (race.length === 0) return null
  return race[currentEventIndex.value] ?? null
})

const currentState = computed(() => currentEvent.value?.state ?? null)
const currentEventData = computed(() => currentEvent.value?.data ?? null)

const activeDangoId = computed<string | null>(() => {
  const data = currentEventData.value
  if (!data) return null
  if ('dango_id' in data) return (data as SkillData | MoveData).dango_id
  return null
})

function stepNext() {
  if (currentEventIndex.value < currentRace.value.length - 1) {
    currentEventIndex.value++
  } else {
    stopPlay()
  }
}

function togglePlay() {
  if (isPlaying.value) {
    stopPlay()
  } else {
    startPlay()
  }
}

function startPlay() {
  if (currentEventIndex.value >= currentRace.value.length - 1) {
    currentEventIndex.value = 0
  }
  isPlaying.value = true
  scheduleInterval()
}

function stopPlay() {
  isPlaying.value = false
  if (playInterval) {
    clearInterval(playInterval)
    playInterval = null
  }
}

function scheduleInterval() {
  if (playInterval) clearInterval(playInterval)
  const ms = Math.max(50, 500 / playSpeed.value)
  playInterval = setInterval(stepNext, ms)
}

watch(playSpeed, () => {
  if (isPlaying.value) scheduleInterval()
})

function onLoaded(data: TraceFile) {
  traceData.value = data
  selectedRace.value = 0
  currentEventIndex.value = 0
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; color: #e0e0e0; font-family: system-ui, sans-serif; }
.app { width: 100vw; height: 100vh; display: flex; flex-direction: column; position: relative; }
.main-area { flex: 1; display: flex; overflow: hidden; }
.board-panel { flex: 1; display: flex; align-items: center; justify-content: center; border-right: 1px solid #2a2a4a; overflow: hidden; }
.event-panel { flex: 1; overflow: hidden; }
</style>
