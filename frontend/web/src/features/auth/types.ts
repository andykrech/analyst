export interface RegisterRequest {
  email: string
  password: string
  password_confirm: string
}

export interface RegisterResponse {
  message: string
}

export interface VerifyResponse {
  message: string
}
