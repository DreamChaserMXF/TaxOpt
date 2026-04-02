// 申请到服务器和域名后，将此处替换为实际地址，并在微信小程序后台添加到合法域名白名单
const BASE_URL = 'https://your.domain.com'

function request(method, path, data) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + path,
      method,
      data,
      header: { 'Content-Type': 'application/json' },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const msg = res.data?.detail || `请求失败（${res.statusCode}）`
          reject(new Error(msg))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误，请检查连接'))
      },
    })
  })
}

export const api = {
  // 获取城市预设列表
  getPresets() {
    return request('GET', '/api/presets')
  },

  // 获取指定城市预设参数
  getPreset(slug) {
    return request('GET', `/api/presets/${slug}`)
  },

  // 计算
  calculate(payload) {
    return request('POST', '/api/calculate', payload)
  },
}
