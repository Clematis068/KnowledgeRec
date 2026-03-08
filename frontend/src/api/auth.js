import request from './index'

export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

export function register({ username, password, gender, tag_ids }) {
  return request.post('/auth/register', { username, password, gender, tag_ids })
}

export function getMe() {
  return request.get('/auth/me')
}

export function getTags() {
  return request.get('/auth/tags')
}
