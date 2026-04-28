function countLabelUnits(label) {
  return [...String(label || '')].reduce((total, char) => {
    return total + (/[\u0000-\u00ff]/.test(char) ? 0.62 : 1)
  }, 0)
}

function estimateActionButtonWidth(label) {
  const units = countLabelUnits(label)
  return Math.max(42, Math.round(20 + units * 14))
}

function normalizeActionGroups(groups) {
  if (!Array.isArray(groups)) {
    return []
  }
  return groups
    .map((group) => {
      if (Array.isArray(group)) {
        return group
          .filter(Boolean)
          .map((item) => String(item).trim())
          .filter(Boolean)
      }
      const single = String(group || '').trim()
      return single ? [single] : []
    })
    .filter((group) => group.length > 0)
}

export function resolveTableActionWidth(groups, options = {}) {
  const {
    compact = false,
    compactWidth = 92,
    minWidth = 112,
    maxWidth = 420,
    cellPadding = 26,
    wrapperPadding = 14,
    gap = 8,
  } = options

  if (compact) {
    return compactWidth
  }

  const normalizedGroups = normalizeActionGroups(groups)
  if (!normalizedGroups.length) {
    return minWidth
  }

  const width = normalizedGroups.reduce((maxWidthValue, labels) => {
    const buttonsWidth = labels.reduce((sum, label) => sum + estimateActionButtonWidth(label), 0)
    const groupWidth = wrapperPadding + buttonsWidth + Math.max(labels.length - 1, 0) * gap
    return Math.max(maxWidthValue, groupWidth)
  }, 0)

  return Math.min(maxWidth, Math.max(minWidth, Math.ceil(width + cellPadding)))
}
