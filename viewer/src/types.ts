export interface SkillData {
  dango_id: string
  hook_name: string
}

export interface MoveData {
  dango_id: string
  from: number
  to: number
  group: string[]
  path: number[]
}

export interface TileData {
  group: string[]
  position: number
  next_position: number
  tile: string
}

export interface BuKingData {
  roll: number
  path: number[]
}

export interface FinishData {
  group: string[]
  position: number
}

export type EventData = SkillData | MoveData | TileData | BuKingData | FinishData

export interface StateSnapshot {
  positions: Record<string, string[]>
  laps_completed: Record<string, number>
  round_number: number
}

export interface TraceEvent {
  kind: 'skill' | 'move' | 'tile' | 'bu_king' | 'finish'
  round: number
  data: EventData
  state: StateSnapshot
}

export type Race = TraceEvent[]
export type TraceFile = Race[]
