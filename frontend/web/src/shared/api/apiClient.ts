const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface RequestOptions {
  /** Не вызывать onUnauthorized при 401 (показать ошибку на месте, без редиректа на логин). */
  skip401Redirect?: boolean
}

interface FetchOptions extends RequestInit, RequestOptions {
  params?: Record<string, string>
}

let authTokenGetter: (() => string | null) | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthTokenGetter(getter: (() => string | null) | null): void {
  authTokenGetter = getter
}

export function setOnUnauthorized(handler: (() => void) | null): void {
  onUnauthorized = handler
}

class ApiError extends Error {
  status: number
  statusText: string
  constructor(
    message: string,
    status: number,
    statusText: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.statusText = statusText
  }
}

async function fetchJson<T>(
  endpoint: string,
  options: FetchOptions = {},
): Promise<T> {
  const { params, skip401Redirect, ...fetchOptions } = options

  // Формируем URL
  let url = `${API_BASE_URL}${endpoint}`
  if (params) {
    const searchParams = new URLSearchParams(params)
    url += `?${searchParams.toString()}`
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string>),
  }
  const token = authTokenGetter?.() ?? null
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const requestOptions: RequestInit = {
    ...fetchOptions,
    headers: {
      ...headers,
      ...(fetchOptions.headers &&
      typeof fetchOptions.headers === 'object' &&
      !Array.isArray(fetchOptions.headers)
        ? (fetchOptions.headers as Record<string, string>)
        : {}),
    },
  }

  let response: Response

  try {
    response = await fetch(url, requestOptions)
  } catch (error) {
    // Обработка сетевых ошибок (включая CORS)
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(
        'Не удалось подключиться к серверу. Проверьте, что сервер запущен и CORS настроен правильно.',
        0,
        'Network Error'
      )
    }
    throw error
  }

  if (response.status === 401 && onUnauthorized && !skip401Redirect) {
    onUnauthorized()
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`
    
    // Пытаемся получить детали ошибки из JSON ответа
    try {
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/json')) {
        const errorData = await response.json()
        if (errorData.detail) {
          errorMessage = errorData.detail
        } else if (errorData.message) {
          errorMessage = errorData.message
        } else if (typeof errorData === 'string') {
          errorMessage = errorData
        }
      } else {
        // Если не JSON, пытаемся прочитать как текст
        const text = await response.text()
        if (text) {
          errorMessage = text
        }
      }
    } catch {
      // Если не удалось распарсить ответ, используем дефолтное сообщение
    }
    
    throw new ApiError(errorMessage, response.status, response.statusText)
  }

  // 204 No Content или пустой ответ — не парсим JSON
  if (response.status === 204) {
    return {} as T
  }

  const contentType = response.headers.get('content-type')
  if (!contentType || !contentType.includes('application/json')) {
    return {} as T
  }

  const text = await response.text()
  if (!text || text.trim() === '') {
    return {} as T
  }

  return JSON.parse(text) as T
}

export const apiClient = {
  get: <T>(endpoint: string, options?: FetchOptions) =>
    fetchJson<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchJson<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchJson<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: unknown, options?: FetchOptions) =>
    fetchJson<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string, options?: FetchOptions) =>
    fetchJson<T>(endpoint, { ...options, method: 'DELETE' }),
}

export { ApiError }
