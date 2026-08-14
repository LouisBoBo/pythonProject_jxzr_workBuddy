/**
 * 预加载脚本：P0 不向渲染进程暴露 Node API。
 * 业务 UI 与网页共用 apps/web，仅走同源 /api。
 */
'use strict'

// 刻意留空：contextIsolation + 无 contextBridge，防桌面特权泄露到前端。
