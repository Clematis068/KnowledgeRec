import { io } from 'socket.io-client'

let socket = null

export function connectSocket(token) {
  if (socket?.connected) return

  socket = io('/', {
    auth: { token },
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 2000,
    reconnectionAttempts: 10,
  })

  socket.on('connect', () => {
    console.log('[WS] connected', socket.id)
  })

  socket.on('disconnect', (reason) => {
    console.log('[WS] disconnected:', reason)
  })

  socket.on('connect_error', (err) => {
    console.warn('[WS] connect error:', err.message)
  })
}

export function disconnectSocket() {
  if (socket) {
    socket.disconnect()
    socket = null
  }
}

export function onSocketEvent(event, callback) {
  if (socket) {
    socket.on(event, callback)
  }
}

export function offSocketEvent(event, callback) {
  if (socket) {
    socket.off(event, callback)
  }
}

export function getSocket() {
  return socket
}
