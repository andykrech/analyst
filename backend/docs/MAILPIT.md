# Проверка отправки писем через Mailpit

## Запуск Mailpit

- **Docker Compose**: сервис `mailpit` (SMTP порт 1025, Web UI порт 8025).
- **Локально**: установите [Mailpit](https://github.com/axllent/mailpit) и запустите (по умолчанию SMTP 1025, UI 8025).

В `.env` backend укажите:

```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=no-reply@local
SMTP_HOST=mailpit
SMTP_PORT=1025
FRONTEND_BASE_URL=http://localhost:5173
```

Без Docker используйте `SMTP_HOST=localhost`.

## Где открыть UI Mailpit

- **URL**: http://localhost:8025  
- В интерфейсе отображаются все письма, принятые по SMTP (порт 1025).

## Как убедиться, что письмо ушло и ссылка кликабельна

1. Зарегистрируйте пользователя: `POST /api/v1/auth/register` с `email` и `password`.
2. Откройте http://localhost:8025 — в списке должно появиться новое письмо.
3. Откройте письмо: тема «Подтверждение регистрации», в тексте — приветствие и ссылка вида  
   `http://localhost:5173/verify?token=...`
4. Клик по ссылке в Mailpit открывает фронт с токеном в query; фронт может отправить токен на бэкенд для подтверждения email.

Переключение провайдера: в `.env` измените только `EMAIL_PROVIDER` (например на `console` — письма будут только в логах).
