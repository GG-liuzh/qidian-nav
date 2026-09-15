import type { Category } from './types'

export function categoryTree(rows: Category[]) {
  const result: (Category & { depth: number })[] = []
  const seen = new Set<string>()
  const children = new Map<string | null, Category[]>()
  for (const row of rows) {
    const siblings = children.get(row.parent_id) || []
    siblings.push(row)
    children.set(row.parent_id, siblings)
  }
  function walk(parent: string | null, depth: number) {
    for (const row of children.get(parent) || []) {
      if (seen.has(row.id)) continue
      seen.add(row.id)
      result.push({ ...row, depth })
      walk(row.id, depth + 1)
    }
  }
  walk(null, 0)
  for (const row of rows)
    if (!seen.has(row.id)) {
      seen.add(row.id)
      result.push({ ...row, depth: 0 })
      walk(row.id, 1)
    }
  return result
}

export function categoryLabel(row: Category & { depth: number }) {
  return `${'　'.repeat(row.depth)}${row.depth ? '↳ ' : ''}${row.name}`
}
