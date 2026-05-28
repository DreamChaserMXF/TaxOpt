import { calculateWithConfig } from './tax-core.js'
import { getPresetConfig, listPresetSummaries } from './presets-data.js'

function buildConfig(payload = {}) {
  if (payload.preset_slug) {
    const preset = getPresetConfig(payload.preset_slug)
    if (!preset) {
      throw new Error(`未知预设：${payload.preset_slug}`)
    }
    return preset
  }

  if (!payload.config) {
    throw new Error('必须提供 config 或 preset_slug 之一')
  }
  return payload.config
}

export const api = {
  // 获取城市预设列表。预设已随小程序打包，无需请求服务端。
  async getPresets() {
    return listPresetSummaries()
  },

  // 获取指定城市预设参数。
  async getPreset(slug) {
    const preset = getPresetConfig(slug)
    if (!preset) {
      throw new Error(`未知预设：${slug}`)
    }
    return preset
  },

  // 本地计算，返回字段保持与原 FastAPI /api/calculate 一致。
  async calculate(payload) {
    return calculateWithConfig(payload, buildConfig(payload))
  },
}
