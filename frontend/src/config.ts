import { parseApiBaseUrl } from '../configuration'

export const apiBaseUrl = parseApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
