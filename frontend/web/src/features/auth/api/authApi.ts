import { apiClient, type RequestOptions } from '@/shared/api/apiClient'
import type {
  LoginRequest,
  LoginResponse,
  MeResponse,
  RegisterRequest,
  RegisterResponse,
  VerifyResponse,
} from '../types'

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    return apiClient.post<LoginResponse>('/api/v1/auth/login', data)
  },

  register: async (data: RegisterRequest): Promise<RegisterResponse> => {
    return apiClient.post<RegisterResponse>('/api/v1/auth/register', data)
  },

  verifyEmail: async (token: string): Promise<VerifyResponse> => {
    return apiClient.get<VerifyResponse>('/api/v1/auth/verify', {
      params: { token },
    })
  },

  /** Проверка валидности токена (GET /me). При 401 не вызывать глобальный редирект. */
  me: async (options?: RequestOptions): Promise<MeResponse> => {
    return apiClient.get<MeResponse>('/api/v1/auth/me', options)
  },
}
