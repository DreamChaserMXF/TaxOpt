// 本地联调默认指向 FastAPI 开发服务；真机/发布前需替换为 HTTPS 公网域名
const BASE_URL = 'http://127.0.0.1:8000'
const DEFAULT_TIMEOUT = 15000
const CALCULATE_TIMEOUT = 30000

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function request(method, path, data, options = {}) {
  const timeout = options.timeout || DEFAULT_TIMEOUT
  const retries = options.retries || 0

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await new Promise((resolve, reject) => {
        uni.request({
          url: BASE_URL + path,
          method,
          data,
          timeout,
          header: { 'Content-Type': 'application/json' },
          success(res) {
            if (res.statusCode >= 200 && res.statusCode < 300) {
              resolve(res.data)
            } else {
              const msg = (res.data && res.data.detail) || `请求失败（${res.statusCode}）`
              reject(new Error(msg))
            }
          },
          fail(err) {
            const rawMessage = err && err.errMsg ? err.errMsg : '网络错误，请检查连接'
            if (rawMessage.includes('timeout')) {
              reject(new Error('请求超时，请确认本地服务已启动后重试'))
              return
            }
            reject(new Error(rawMessage))
          },
        })
      })
    } catch (error) {
      if (attempt === retries) throw error
      await delay(250)
    }
  }
}

export const api = {
  // 获取城市预设列表
  getPresets() {
    return request('GET', '/api/presets', undefined, { retries: 1 })
  },

  // 获取指定城市预设参数
  getPreset(slug) {
    return request('GET', `/api/presets/${slug}`, undefined, { retries: 1 })
  },

  // 计算
  calculate(payload) {
    return request('POST', '/api/calculate', payload, { timeout: CALCULATE_TIMEOUT })
  },
}
