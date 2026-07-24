import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export function sendMessage(message, threadId = 'default') {
  return api.post('/chat', { message, thread_id: threadId })
}

export function streamMessage(message, threadId, onToken, onDone, onError, filePaths = []) {
  return fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId, file_paths: filePaths }),
  }).then(async (response) => {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.done) {
            onDone(data.thread_id)
          } else if (data.token) {
            onToken(data.token)
          } else if (data.error) {
            onError(data.error)
          }
        } catch (e) {
          // ignore parse errors
        }
      }
    }
  }).catch(onError)
}

export function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getHistoryList() {
  return api.get('/history')
}

export function getHistoryDetail(id) {
  return api.get(`/history/${id}`)
}

export function saveHistory(threadId, messages, title) {
  return api.post('/history/save', { thread_id: threadId, messages, title })
}

export function deleteHistory(threadId) {
  return api.delete(`/history/${threadId}`)
}

export function convertDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/convert', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
