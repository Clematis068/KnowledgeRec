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
    // connected
  })

  socket.on('disconnect', () => {
    // disconnected
  })

  socket.on('connect_error', () => {
    // connection error
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
