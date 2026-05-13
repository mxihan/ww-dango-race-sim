export const BOARD_SIZE = 32

export interface TileInfo {
  position: number
  type: 'normal' | 'Booster' | 'Inhibitor' | 'SpaceTimeRift'
}

export const SPECIAL_TILES: Record<number, TileInfo> = {
  3: { position: 3, type: 'Booster' },
  6: { position: 6, type: 'SpaceTimeRift' },
  10: { position: 10, type: 'Inhibitor' },
  11: { position: 11, type: 'Booster' },
  16: { position: 16, type: 'Booster' },
  20: { position: 20, type: 'SpaceTimeRift' },
  23: { position: 23, type: 'Booster' },
  28: { position: 28, type: 'Inhibitor' },
}

export const GRID: number[][] = [
  [0, 1, 2, 3, 4, 5, 6, 7],
  [15, 14, 13, 12, 11, 10, 9, 8],
  [16, 17, 18, 19, 20, 21, 22, 23],
  [31, 30, 29, 28, 27, 26, 25, 24],
]

export function getTileInfo(pos: number): TileInfo {
  return SPECIAL_TILES[pos] ?? { position: pos, type: 'normal' }
}
