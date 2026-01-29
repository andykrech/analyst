export interface RegisterRequest {
  email: string
  password: string
  password_confirm: string
}

export interface RegisterResponse {
  message: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type?: string
  email?: string
}

export interface VerifyResponse {
  message: string
}
