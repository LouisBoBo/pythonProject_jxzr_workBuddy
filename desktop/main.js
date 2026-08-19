/**
 * WorkBuddy 桌面壳（Electron）
 *
 * - 单实例
 * - 探测空闲端口（默认 18765，避开开发 8765）
 * - 拉起探活沙箱 + API（开发态用系统 Python；安装包可改为打包的 API 可执行文件）
 * - /health 就绪后打开 BrowserWindow
 * - 退出时结束子进程
 *
 * 不修改业务代码路径语义；仅注入 WORKBUDDY_DESKTOP / WEB_DIST_DIR / DATA_DIR 等环境变量。
 */
'use strict'

const { app, BrowserWindow, dialog } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const net = require('net')
const fs = require('fs')
const path = require('path')

const API_PORT_START = Number(process.env.WORKBUDDY_DESKTOP_API_PORT || 18765)
const SANDBOX_PORT_START = Number(process.env.WORKBUDDY_DESKTOP_SANDBOX_PORT || 18001)

/** @type {import('child_process').ChildProcess[]} */
const children = []
/** @type {BrowserWindow | null} */
let mainWindow = null
let shuttingDown = false

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

function repoRoot() {
  // desktop/ → 仓库根；打包后 resources 旁无完整仓库时需 WORKBUDDY_REPO_ROOT 或内置 API
  if (process.env.WORKBUDDY_REPO_ROOT) {
    return path.resolve(process.env.WORKBUDDY_REPO_ROOT)
  }
  if (app.isPackaged) {
    return path.dirname(process.resourcesPath)
  }
  return path.resolve(__dirname, '..')
}

function resolveWebDist(root) {
  if (process.env.WEB_DIST_DIR) {
    return path.resolve(process.env.WEB_DIST_DIR)
  }
  if (app.isPackaged) {
    const packed = path.join(process.resourcesPath, 'web-dist')
    if (fs.existsSync(path.join(packed, 'index.html'))) return packed
  }
  const devDist = path.join(root, 'apps', 'web', 'dist')
  if (fs.existsSync(path.join(devDist, 'index.html'))) return devDist
  return ''
}

function binName(base) {
  return process.platform === 'win32' ? `${base}.cmd` : base
}

function findRuntimeBinary(name) {
  const file = binName(name)
  const candidates = []
  if (name === 'workbuddy-api' && process.env.WORKBUDDY_API_BIN) {
    candidates.push(process.env.WORKBUDDY_API_BIN)
  }
  if (name === 'workbuddy-sandbox' && process.env.WORKBUDDY_SANDBOX_BIN) {
    candidates.push(process.env.WORKBUDDY_SANDBOX_BIN)
  }
  if (typeof app !== 'undefined' && app.isPackaged) {
    candidates.push(path.join(process.resourcesPath, 'runtime', 'bin', file))
  }
  const root = repoRoot()
  candidates.push(path.join(root, 'desktop', 'runtime', 'bin', file))
  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c
  }
  return ''
}

function resolvePython() {
  return process.env.WORKBUDDY_PYTHON || 'python3'
}

function resolveApiEntry(root) {
  const packed = findRuntimeBinary('workbuddy-api')
  if (packed) {
    return { cmd: packed, args: [], cwd: path.dirname(packed) }
  }
  if (app.isPackaged) {
    throw new Error(
      '安装包缺少内置 API（runtime/workbuddy-api）。请重新运行 ./scripts/package-desktop.sh 完整打包。'
    )
  }
  const py = resolvePython()
  const mainPy = path.join(root, 'apps', 'api', 'main.py')
  return { cmd: py, args: [mainPy], cwd: path.join(root, 'apps', 'api') }
}

function resolveSandboxEntry(root) {
  const packed = findRuntimeBinary('workbuddy-sandbox')
  if (packed) {
    return { cmd: packed, args: [], cwd: path.dirname(packed) }
  }
  if (app.isPackaged) {
    throw new Error(
      '安装包缺少内置探活沙箱（runtime/workbuddy-sandbox）。请重新完整打包。'
    )
  }
  const py = resolvePython()
  const script = path.join(root, 'apps', 'sandbox', 'server.py')
  return { cmd: py, args: [script], cwd: root }
}

function portFree(port) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(port, '127.0.0.1')
  })
}

async function findFreePort(start, attempts = 40) {
  for (let i = 0; i < attempts; i++) {
    const p = start + i
    if (await portFree(p)) return p
  }
  throw new Error(`无空闲端口（自 ${start} 起试了 ${attempts} 个）`)
}

function waitHealth(port, timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (shuttingDown) {
        reject(new Error('已退出'))
        return
      }
      const req = http.get(
        { host: '127.0.0.1', port, path: '/health', timeout: 1500 },
        (res) => {
          res.resume()
          if (res.statusCode === 200) {
            resolve()
            return
          }
          retry()
        }
      )
      req.on('error', retry)
      req.on('timeout', () => {
        req.destroy()
        retry()
      })
    }
    const retry = () => {
      if (Date.now() > deadline) {
        reject(new Error(`API /health 超时（:${port}）`))
        return
      }
      setTimeout(tick, 250)
    }
    tick()
  })
}

function spawnLogged(label, cmd, args, env, cwd) {
  const child = spawn(cmd, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  const prefix = `[${label}]`
  child.stdout.on('data', (buf) => process.stdout.write(`${prefix} ${buf}`))
  child.stderr.on('data', (buf) => process.stderr.write(`${prefix} ${buf}`))
  child.on('exit', (code, signal) => {
    console.log(`${prefix} exit code=${code} signal=${signal}`)
  })
  children.push(child)
  return child
}

function killChildren() {
  for (const child of children.splice(0)) {
    try {
      if (!child.killed) {
        child.kill('SIGTERM')
      }
    } catch {
      /* ignore */
    }
  }
}

async function startBackend() {
  const root = repoRoot()
  const dataDir = process.env.DATA_DIR || path.join(app.getPath('userData'), 'data')
  fs.mkdirSync(dataDir, { recursive: true })

  const webDist = resolveWebDist(root)
  if (!webDist) {
    throw new Error(
      '未找到前端 dist。请先执行: (cd apps/web && npm run build)\n或设置 WEB_DIST_DIR。'
    )
  }

  const apiPort = await findFreePort(API_PORT_START)
  const sandboxPort = await findFreePort(SANDBOX_PORT_START)
  const sandboxUrl = `http://127.0.0.1:${sandboxPort}`

  const baseEnv = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    WORKBUDDY_DESKTOP: '1',
    USE_ERP: '1',
    LOCAL_DEV_AGENT: 'cursor_sdk',
    DATA_DIR: dataDir,
    MES_SERVER_HOST: '127.0.0.1',
    MES_SERVER_PORT: String(apiPort),
    MES_RELOAD: 'false',
    WEB_DIST_DIR: webDist,
    API_PROBE_SANDBOX_HOST: '127.0.0.1',
    API_PROBE_SANDBOX_PORT: String(sandboxPort),
    API_PROBE_SANDBOX_URL: sandboxUrl,
  }

  const sandbox = resolveSandboxEntry(root)
  spawnLogged('sandbox', sandbox.cmd, sandbox.args, baseEnv, sandbox.cwd)

  // 短等沙箱（失败不阻断：登录仍可能打 ERP）
  try {
    await waitHealth(sandboxPort, 15000)
  } catch (e) {
    console.warn('[desktop] 探活沙箱未就绪，继续启动 API:', e.message || e)
  }

  const api = resolveApiEntry(root)
  spawnLogged('api', api.cmd, api.args, baseEnv, api.cwd)
  await waitHealth(apiPort, 90000)

  return { apiPort, sandboxPort, dataDir, webDist }
}

function createWindow(apiPort) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    title: `ZR WorkBuddy v${app.getVersion()}`,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  mainWindow.loadURL(`http://127.0.0.1:${apiPort}/`)
  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(async () => {
  if (!gotLock) return
  try {
    const { apiPort, dataDir } = await startBackend()
    console.log(`[desktop] API :${apiPort}  DATA_DIR=${dataDir}`)
    createWindow(apiPort)
  } catch (err) {
    console.error(err)
    dialog.showErrorBox('ZR WorkBuddy 启动失败', String(err && err.message ? err.message : err))
    killChildren()
    app.quit()
  }
})

app.on('window-all-closed', () => {
  shuttingDown = true
  killChildren()
  app.quit()
})

app.on('before-quit', () => {
  shuttingDown = true
  killChildren()
})

process.on('exit', killChildren)
process.on('SIGINT', () => {
  killChildren()
  process.exit(0)
})
process.on('SIGTERM', () => {
  killChildren()
  process.exit(0)
})
