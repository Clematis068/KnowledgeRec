import request from './index'

export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

export function register({ username, password, gender, email, tag_ids }) {
  return request.post('/auth/register', { username, password, gender, email, tag_ids })
}

export function getMe() {
  return request.get('/auth/me')
}

export function getTags() {
  return request.get('/auth/tags')
}

export function getDomains() {
  return request.get('/auth/domains')
}

export function sendEmailCode(email) {
  return request.post('/auth/send-email-code', { email })
}

export function verifyEmailCode(email, code) {
  return request.post('/auth/verify-email-code', { email, code })
}

export function sendResetPasswordCode(email) {
  return request.post('/auth/send-reset-password-code', { email })
}

export function verifyResetPasswordCode(email, code) {
  return request.post('/auth/verify-reset-password-code', { email, code })
}

export function resetPassword({ email, password }) {
  return request.post('/auth/reset-password', { email, password })
}
