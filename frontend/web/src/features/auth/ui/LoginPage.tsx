import { Link } from 'react-router-dom'
import './LoginPage.css'

export function LoginPage() {
  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Вход</h1>
        <p className="todo-note">Login (TODO)</p>
        
        <form>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              disabled
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              type="password"
              disabled
            />
          </div>

          <button type="submit" disabled className="auth-button">
            Войти
          </button>
        </form>

        <p className="auth-footer">
          Нет аккаунта? <Link to="/register">Зарегистрироваться</Link>
        </p>
      </div>
    </div>
  )
}
