import type { TargetPoint, TimingResult, TimingTarget } from '../types'

export const FAILED_TARGET_COLOR = '#a33bd1'

export function targetFailed(result: TimingTarget | undefined) {
  return !!result && (result.failed ?? (result.tick === null || !!result.error || result.movedBlocks < 10))
}

export function targetResult(timing: TimingResult | null, point: TargetPoint) {
  return timing?.targets.find(item => item.x === point.x && item.y === point.y && (item.z ?? 0) === (point.z ?? 0))
}
