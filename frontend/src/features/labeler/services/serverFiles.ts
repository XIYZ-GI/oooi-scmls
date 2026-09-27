import { libraryRequest, downloadServerFile } from '@/lib/serverLibrary'
import type { LabelSample } from '../types'

export async function importStructureFile(file: File) {
  if (!/\.mcstructure$/i.test(file.name)) throw new Error('请选择 .mcstructure 文件')
  if (file.size > 16 * 1024 * 1024) throw new Error('单文件不能超过 16 MiB')
  return libraryRequest<{ items: LabelSample[]; added: number }>(`samples/upload?filename=${encodeURIComponent(file.name)}`, { method: 'POST', body: file, headers: { 'Content-Type': 'application/octet-stream' } })
}

export async function uploadDataset(file: File) {
  if (file.size > 64 * 1024 * 1024) throw new Error('JSON 备份不能超过 64 MiB')
  return libraryRequest<{ items: LabelSample[]; added: number }>('samples/import', { method: 'POST', body: file, headers: { 'Content-Type': 'application/json' } })
}

export function downloadDataset(samples: LabelSample[], filename: string, all = false) {
  return downloadServerFile(`samples/export${all ? '' : `?sample_id=${encodeURIComponent(samples[0].id)}`}`, filename)
}
