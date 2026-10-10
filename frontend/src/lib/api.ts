// 开发时走 Vite 代理；生产时可配置独立的后端域名。
const apiOrigin = import.meta.env.PROD
  ? (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
  : ''

export function apiUrl(path = ''): string {
  return `${apiOrigin}/api/v1${path}`
}
