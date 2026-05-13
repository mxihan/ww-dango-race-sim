<template>
  <div class="file-loader" @dragover.prevent @drop.prevent="onDrop">
    <div class="loader-content">
      <div class="drop-zone">
        <p class="drop-icon">📂</p>
        <p>Drop <strong>trace.json</strong> here</p>
        <p class="or">or</p>
        <label class="file-button">
          Browse Files
          <input type="file" accept=".json" @change="onFileSelect" hidden />
        </label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TraceFile } from '../types'

const emit = defineEmits<{
  loaded: [data: TraceFile]
}>()

function parseFile(file: File) {
  const reader = new FileReader()
  reader.onload = () => {
    const data = JSON.parse(reader.result as string) as TraceFile
    emit('loaded', data)
  }
  reader.readAsText(file)
}

function onFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) parseFile(file)
}

function onDrop(event: DragEvent) {
  const file = event.dataTransfer?.files[0]
  if (file) parseFile(file)
}
</script>

<style scoped>
.file-loader {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
  z-index: 100;
}
.loader-content {
  text-align: center;
}
.drop-zone {
  border: 2px dashed #4a4a6a;
  border-radius: 16px;
  padding: 48px 64px;
}
.drop-zone:hover {
  border-color: #6a6a9a;
  background: rgba(255,255,255,0.02);
}
.drop-icon { font-size: 48px; margin-bottom: 16px; }
.or { color: #666; margin: 12px 0; }
.file-button {
  display: inline-block;
  padding: 10px 24px;
  background: #4a90d9;
  color: white;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
.file-button:hover { background: #3a7ac9; }
</style>
