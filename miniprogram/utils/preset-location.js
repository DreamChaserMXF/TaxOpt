export const CUSTOM_PRESET_LABEL = '自定义参数（默认杭州）'

export const HANGZHOU_DEFAULT_CONFIG = {
  basic_deduction: 60000,
  social_security_base_min: 4986,
  social_security_base_limit: 25299,
  pension_rate: 0.08,
  medical_rate: 0.02,
  unemployment_rate: 0.005,
  housing_fund_base_min: 2490,
  housing_fund_base_limit: 40694,
  housing_fund_employee_rate: 0.12,
  housing_fund_employer_rate: 0.12,
  children_education: 0,
  continuing_education: 0,
  serious_illness: 0,
  housing_loan_interest: 0,
  housing_rent: 0,
  elderly_support: 0,
  annual_additional_deduction: 0,
}

const PRESET_CITY_COORDINATES = {
  'anhui-hefei': [31.82, 117.23],
  'beijing-beijing': [39.90, 116.41],
  'chongqing-chongqing': [29.56, 106.55],
  'fujian-fuzhou': [26.08, 119.30],
  'fujian-xiamen': [24.48, 118.09],
  'gansu-lanzhou': [36.06, 103.84],
  'guangdong-dongguan': [23.02, 113.75],
  'guangdong-foshan': [23.02, 113.12],
  'guangdong-guangzhou': [23.13, 113.26],
  'guangdong-shenzhen': [22.55, 114.05],
  'guangxi-nanning': [22.82, 108.37],
  'guizhou-guiyang': [26.65, 106.63],
  'hainan-haikou': [20.04, 110.20],
  'hebei-shijiazhuang': [38.04, 114.51],
  'heilongjiang-haerbin': [45.80, 126.53],
  'henan-zhengzhou': [34.75, 113.62],
  'hubei-wuhan': [30.59, 114.30],
  'hunan-changsha': [28.23, 112.94],
  'jiangsu-nanjing': [32.06, 118.79],
  'jiangsu-suzhou': [31.30, 120.58],
  'jiangsu-wuxi': [31.49, 120.31],
  'jiangxi-nanchang': [28.68, 115.86],
  'jilin-changchun': [43.82, 125.32],
  'liaoning-dalian': [38.91, 121.61],
  'liaoning-shenyang': [41.80, 123.43],
  'neimenggu-huhehaote': [40.84, 111.75],
  'ningxia-yinchuan': [38.49, 106.23],
  'qinghai-xining': [36.62, 101.78],
  'shaanxi-xian': [34.34, 108.94],
  'shandong-jinan': [36.65, 117.12],
  'shandong-qingdao': [36.07, 120.38],
  'shanghai-shanghai': [31.23, 121.47],
  'shanxi-taiyuan': [37.87, 112.55],
  'sichuan-chengdu': [30.57, 104.06],
  'tianjin-tianjin': [39.12, 117.20],
  'xinjiang-wulumuqi': [43.82, 87.62],
  'xizang-lasa': [29.65, 91.13],
  'yunnan-kunming': [25.04, 102.71],
  'zhejiang-hangzhou': [30.27, 120.15],
  'zhejiang-hangzhou-counties': [30.23, 119.72],
  'zhejiang-ningbo': [29.87, 121.55],
  'zhejiang-wenzhou': [27.99, 120.70],
}

const MAX_MATCH_DISTANCE_KM = 120

function toRadians(value) {
  return value * Math.PI / 180
}

function distanceInKm(lat1, lon1, lat2, lon2) {
  const earthRadiusKm = 6371
  const dLat = toRadians(lat2 - lat1)
  const dLon = toRadians(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return earthRadiusKm * c
}

export function findNearestPresetSlug(latitude, longitude, presetSlugs) {
  let bestSlug = ''
  let bestDistance = Infinity

  presetSlugs.forEach((slug) => {
    const point = PRESET_CITY_COORDINATES[slug]
    if (!point) return
    const distance = distanceInKm(latitude, longitude, point[0], point[1])
    if (distance < bestDistance) {
      bestDistance = distance
      bestSlug = slug
    }
  })

  if (bestDistance > MAX_MATCH_DISTANCE_KM) return ''
  return bestSlug
}
