import { apiClient } from '@/shared/api/apiClient'
import type { RegisterRequest, RegisterResponse, VerifyResponse } from '../types'

export const authApi = {
  register: async (data: RegisterRequest): Promise<RegisterResponse> => {
    return apiClient.post<RegisterResponse>('/api/v1/auth/register', data)
  },

  verifyEmail: async (token: string): Promise<VerifyResponse> => {
    return apiClient.get<VerifyResponse>('/api/v1/auth/verify', {
      params: { token },
    })
  },
}
