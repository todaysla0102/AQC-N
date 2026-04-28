export const SHOP_TYPE_STORE = 0
export const SHOP_TYPE_WAREHOUSE = 1
export const SHOP_TYPE_OTHER_WAREHOUSE = 2
export const SHOP_TYPE_REPAIR = 3

export const SHOP_NAME_DISPLAY_ALIASES = [
  ['澳群淘宝', '澳群线上Casio淘宝'],
]

export const SHOP_NAME_ALIASES = [
  ['澳群线上Casio淘宝', '澳群淘宝'],
  ['澳群淘宝', '澳群淘宝'],
  ['武商梦时代Casio专卖店', '梦时代'],
  ['梦时代', '梦时代'],
  ['武汉新佳丽广场Casio专卖店', '新佳丽'],
  ['新佳丽', '新佳丽'],
  ['武汉世贸广场Casio专柜', '世贸'],
  ['武商世贸Casio专柜', '世贸'],
  ['世贸广场', '世贸'],
  ['十堰武商卡西欧专柜', '十堰武商'],
  ['十堰武商', '十堰武商'],
  ['武商奥莱Casio专柜', '武商奥莱'],
  ['武商奥莱', '武商奥莱'],
  ['宜昌国贸Casio专卖店', '宜昌国贸'],
  ['宜昌国贸', '宜昌国贸'],
  ['武昌万象城Casio专卖店', '武昌万象城'],
  ['武昌万象城', '武昌万象城'],
  ['孝感保利仓库', '孝感保利'],
  ['孝感保利', '孝感保利'],
]

export function cleanShopName(value) {
  return String(value || '').trim()
}

export function replaceShopNameAliases(value) {
  let text = String(value || '')
  for (const [source, target] of SHOP_NAME_DISPLAY_ALIASES) {
    if (!source || !target) {
      continue
    }
    text = text.split(source).join(target)
  }
  return text.trim()
}

export function displayShopName(value) {
  return replaceShopNameAliases(cleanShopName(value))
}

export function simplifyShopName(shopName) {
  const cleanName = cleanShopName(shopName)
  if (!cleanName) {
    return ''
  }
  const matched = SHOP_NAME_ALIASES.find(([keyword]) => cleanName.includes(keyword))
  return matched ? matched[1] : cleanName
}

export function normalizeLocationRow(item, fallbackShopType = SHOP_TYPE_STORE) {
  const shopId = Number(item?.shopId ?? item?.id ?? 0)
  const shopName = cleanShopName(item?.shopName ?? item?.name)
  const shopType = Number(item?.shopType ?? fallbackShopType)
  const quantity = Number(item?.quantity ?? item?.shopQuantity ?? 0)
  return {
    shopId,
    shopName,
    shopShortName: simplifyShopName(shopName) || shopName,
    shopType,
    quantity,
  }
}

export function sortLocationsByName(rows) {
  return [...(rows || [])].sort((left, right) => {
    const leftType = Number(left?.shopType ?? SHOP_TYPE_STORE)
    const rightType = Number(right?.shopType ?? SHOP_TYPE_STORE)
    if (leftType !== rightType) {
      return leftType - rightType
    }
    const leftName = simplifyShopName(left?.shopName ?? left?.name ?? '') || cleanShopName(left?.shopName ?? left?.name)
    const rightName = simplifyShopName(right?.shopName ?? right?.name ?? '') || cleanShopName(right?.shopName ?? right?.name)
    if (leftName !== rightName) {
      return leftName.localeCompare(rightName, 'zh-CN')
    }
    return Number(left?.shopId ?? left?.id ?? 0) - Number(right?.shopId ?? right?.id ?? 0)
  })
}

export function sortLocationsById(rows) {
  return [...(rows || [])].sort((left, right) => {
    const leftId = Number(left?.shopId ?? left?.id ?? 0)
    const rightId = Number(right?.shopId ?? right?.id ?? 0)
    if (leftId !== rightId) {
      return leftId - rightId
    }
    const leftType = Number(left?.shopType ?? SHOP_TYPE_STORE)
    const rightType = Number(right?.shopType ?? SHOP_TYPE_STORE)
    if (leftType !== rightType) {
      return leftType - rightType
    }
    return compareTextValue(cleanShopName(left?.shopName ?? left?.name), cleanShopName(right?.shopName ?? right?.name))
  })
}

function compareTextValue(left, right) {
  return String(left || '').localeCompare(String(right || ''), 'zh-CN', {
    numeric: true,
    sensitivity: 'base',
  })
}
