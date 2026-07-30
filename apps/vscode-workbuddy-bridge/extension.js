/**
 * WorkBuddy Bridge — VS Code 扩展（纯 JS）
 * 主审：MCP（vscode-as-mcp-server → code_checker 等）
 * 辅：本机 getDiagnostics；弱规则仅作最后兜底。
 */
const vscode = require("vscode");
const http = require("http");
const https = require("https");
const { URL } = require("url");
const crypto = require("crypto");
const path = require("path");
const fs = require("fs");
const { runMcpCodeReview } = require("./mcpClient");
const { readWorkspaceFiles, toWorkspaceRelative } = require("./localFiles");

let bridgeId = "";
let timer = null;
let statusBar = null;
let connected = false;
let tickBusy = false;
let extContext = null;
/** 最近一次心跳上报的工程根（内存白名单） */
let lastAllowedRoots = [];

function cfg() {
  const c = vscode.workspace.getConfiguration("workbuddy");
  const argsRaw = String(c.get("mcpArgs") || "-y,vscode-as-mcp-server");
  const mcpArgs = argsRaw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return {
    api: String(c.get("apiBaseUrl") || "http://127.0.0.1:8765").replace(/\/$/, ""),
    token: String(c.get("token") || "").trim(),
    mcpEnabled: c.get("mcpEnabled") === true,
    mcpCommand: String(c.get("mcpCommand") || "npx").trim() || "npx",
    mcpArgs,
    mcpTool: String(c.get("mcpTool") || "code_checker").trim() || "code_checker",
    mcpTimeoutSec: Number(c.get("mcpTimeoutSec") || 12) || 12,
    allowFallbackRules: c.get("allowFallbackRules") !== false,
    autoConnect: c.get("autoConnect") !== false,
    extensionVersion: "0.4.3",
  };
}

function workspaceInfo() {
  const folders = vscode.workspace.workspaceFolders || [];
  if (!folders.length) {
    return { root: "", ready: false };
  }
  return { root: folders[0].uri.fsPath, ready: true };
}

function rememberWorkspace(root) {
  if (!extContext || !root) return;
  const abs = path.resolve(root);
  if (!fs.existsSync(abs) || !fs.statSync(abs).isDirectory()) return;
  const key = "workbuddy.recentWorkspaces";
  const prev = extContext.globalState.get(key) || [];
  const next = [abs, ...prev.filter((p) => path.resolve(String(p)) !== abs)].slice(0, 15);
  extContext.globalState.update(key, next);
}

async function collectRecentWorkspaces() {
  const items = [];
  const seen = new Set();
  const add = (p) => {
    const abs = path.resolve(String(p || "").trim());
    if (!abs || seen.has(abs)) return;
    try {
      if (!fs.existsSync(abs) || !fs.statSync(abs).isDirectory()) return;
    } catch {
      return;
    }
    seen.add(abs);
    items.push({
      path: abs,
      name: path.basename(abs),
      current: false,
    });
  };

  const cur = workspaceInfo();
  if (cur.root) {
    rememberWorkspace(cur.root);
    add(cur.root);
  }

  try {
    const recent = await vscode.commands.executeCommand("_workbench.getRecentlyOpened");
    for (const entry of recent?.workspaces || []) {
      if (entry?.folderUri?.fsPath) add(entry.folderUri.fsPath);
      else if (entry?.workspace?.configPath) {
        add(path.dirname(entry.workspace.configPath));
      }
    }
  } catch {
    // 内部命令不可用时忽略，仍有本扩展记录
  }

  const tracked = (extContext && extContext.globalState.get("workbuddy.recentWorkspaces")) || [];
  for (const p of tracked) add(p);

  // 凡上报过的工程都记入白名单记忆，供 resolveTaskWorkspace 校验
  for (const it of items) rememberWorkspace(it.path);

  if (cur.root) {
    const curAbs = path.resolve(cur.root);
    for (const it of items) {
      it.current = path.resolve(it.path) === curAbs;
    }
    items.sort((a, b) => Number(b.current) - Number(a.current));
  }
  lastAllowedRoots = items.map((it) => path.resolve(it.path));
  return items.slice(0, 12);
}

/** 解析任务目标工程：仅允许当前打开或最近工程列表中的目录 */
function resolveTaskWorkspace(task) {
  const preferred = String(task?.workspace_root || "").trim();
  const cur = workspaceInfo();
  if (!preferred) {
    return { root: cur.root, ready: cur.ready, source: "current" };
  }
  const abs = path.resolve(preferred);
  try {
    if (!fs.existsSync(abs) || !fs.statSync(abs).isDirectory()) {
      return {
        root: "",
        ready: false,
        source: "missing",
        error: `工程目录不存在: ${preferred}`,
      };
    }
  } catch (e) {
    return { root: "", ready: false, source: "error", error: String(e.message || e) };
  }

  // 企业级：目标目录必须是当前打开 / 最近上报 / 本扩展记忆中的工程
  const allowed = new Set();
  if (cur.root) allowed.add(path.resolve(cur.root));
  for (const p of lastAllowedRoots || []) {
    if (p) allowed.add(path.resolve(String(p)));
  }
  try {
    const tracked = (extContext && extContext.globalState.get("workbuddy.recentWorkspaces")) || [];
    for (const p of tracked) {
      if (p) allowed.add(path.resolve(String(p)));
    }
  } catch {
    /* ignore */
  }
  if (!allowed.has(abs)) {
    return {
      root: "",
      ready: false,
      source: "not_allowed",
      error: `工程不在允许列表（当前打开/最近工程）: ${preferred}`,
    };
  }

  rememberWorkspace(abs);
  return { root: abs, ready: true, source: "selected" };
}

function request(method, urlStr, token, body, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const lib = u.protocol === "https:" ? https : http;
    const payload = body == null ? null : JSON.stringify(body);
    const req = lib.request(
      {
        protocol: u.protocol,
        hostname: u.hostname,
        port: u.port || (u.protocol === "https:" ? 443 : 80),
        path: u.pathname + u.search,
        method,
        headers: {
          Accept: "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(payload
            ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) }
            : {}),
        },
        timeout: timeoutMs,
      },
      (res) => {
        const chunks = [];
        res.on("data", (d) => chunks.push(d));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let data = {};
          try {
            data = text ? JSON.parse(text) : {};
          } catch {
            data = { raw: text };
          }
          if (res.statusCode && res.statusCode >= 400) {
            reject(new Error(`HTTP ${res.statusCode}: ${text.slice(0, 300)}`));
            return;
          }
          resolve(data);
        });
      }
    );
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("timeout"));
    });
    if (payload) req.write(payload);
    req.end();
  });
}

function setStatus(text, tooltip) {
  if (!statusBar) return;
  statusBar.text = text;
  statusBar.tooltip = tooltip || text;
}

function relPath(root, filePath) {
  const r = path.resolve(root);
  const f = path.resolve(filePath);
  if (f === r || f.startsWith(r + path.sep)) {
    return path.relative(r, f).split(path.sep).join("/");
  }
  return f;
}

function severityOf(vsSev) {
  if (vsSev === 0) return "P0";
  if (vsSev === 1) return "P1";
  return "P2";
}

function collectDiagnostics(root, pathFilter) {
  const findings = [];
  const files = new Set();
  const diags = vscode.languages.getDiagnostics();
  const filters = (pathFilter || []).map((p) => String(p).replace(/\\/g, "/"));

  for (const [uri, list] of diags) {
    if (uri.scheme !== "file") continue;
    const rel = relPath(root, uri.fsPath);
    if (filters.length) {
      const ok = filters.some(
        (f) => rel === f || rel.endsWith("/" + f) || rel.includes(f)
      );
      if (!ok) continue;
    }
    files.add(rel);
    for (const d of list || []) {
      findings.push({
        severity: severityOf(d.severity),
        path: rel,
        line: (d.range?.start?.line || 0) + 1,
        rule: String(d.source || d.code || "vscode-diagnostic"),
        message: d.message || "",
        suggestion: "在 VS Code 问题面板中定位并修复",
      });
    }
  }
  return { findings, files: [...files] };
}

/** 弱规则兜底：MCP+诊断皆空时仍给出可执行 finding（含常见 Java 风险） */
function scanFilesFallback(root, paths, prompt) {
  const findings = [];
  const files = [];
  const targets = resolveReviewTargets(root, paths);

  const rules = [
    {
      severity: "P1",
      rule: "token-in-url-query",
      re: /(params\.get\(\s*['"]access_token['"]|params\.get\(\s*['"]token['"]|searchParams\.get\(\s*['"]access_token['"]|[?&]access_token=)/,
      message: "疑似从 URL query 读取 token，存在泄露面（日志/referrer）",
      suggestion: "写入 sessionStorage 后 replaceState 去掉 query",
    },
    {
      severity: "P0",
      rule: "dangerous-eval",
      re: /\beval\s*\(/,
      message: "出现 eval()，存在任意代码执行风险",
      suggestion: "改为安全解析，避免 eval",
    },
    {
      severity: "P0",
      rule: "java-sql-string-concat",
      re: /(createStatement\s*\(|\.execute(Query|Update)?\s*\(\s*["'][^"']*["']\s*\+|Statement\.execute|["']\s*SELECT\b[^"']*["']\s*\+)/i,
      message: "疑似 SQL 字符串拼接，存在注入风险",
      suggestion: "改用 PreparedStatement 参数绑定，禁止拼接用户输入",
    },
    {
      severity: "P0",
      rule: "java-runtime-exec",
      re: /Runtime\.getRuntime\s*\(\s*\)\s*\.exec\s*\(|ProcessBuilder\s*\(/,
      message: "出现 Runtime.exec / ProcessBuilder，存在命令注入风险",
      suggestion: "避免拼接外部输入；使用白名单参数或安全 API",
    },
    {
      severity: "P1",
      rule: "java-print-stack-trace",
      re: /\.printStackTrace\s*\(/,
      message: "printStackTrace 可能泄露内部信息到日志/控制台",
      suggestion: "使用统一日志框架记录异常，避免直接打印堆栈给终端用户",
    },
    {
      severity: "P1",
      rule: "java-object-input-stream",
      re: /new\s+ObjectInputStream\s*\(/,
      message: "反序列化 ObjectInputStream 存在远程代码执行历史风险",
      suggestion: "避免反序列化不可信数据；改用安全格式（JSON 等）",
    },
    {
      severity: "P1",
      rule: "hardcoded-secret",
      re: /(password|passwd|secret|api[_-]?key)\s*=\s*["'][^"']{4,}["']/i,
      message: "疑似硬编码口令/密钥",
      suggestion: "改为环境变量或密钥管理，勿提交明文密钥",
    },
    {
      severity: "P2",
      rule: "todo-fixme",
      re: /\b(TODO|FIXME|XXX)\b/,
      message: "存在 TODO/FIXME 标记，需确认是否遗留风险",
      suggestion: "关闭前确认并清理或登记跟踪",
    },
  ];

  for (const rel of targets) {
    const abs = path.join(root, rel);
    if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) continue;
    files.push(rel);
    let text;
    try {
      text = fs.readFileSync(abs, "utf8");
    } catch {
      continue;
    }
    const lines = text.split(/\r?\n/);
    lines.forEach((line, i) => {
      for (const rule of rules) {
        if (rule.re.test(line)) {
          findings.push({
            severity: rule.severity,
            path: rel,
            line: i + 1,
            rule: rule.rule,
            message: rule.message + (prompt ? `（关注：${prompt.slice(0, 40)}）` : ""),
            suggestion: rule.suggestion,
          });
        }
      }
    });
  }
  return { findings, files };
}

/** 将任务 paths（文件/目录/空）解析为可审文件相对路径 */
function resolveReviewTargets(root, paths, limit = 16) {
  const out = [];
  const seen = new Set();
  const CODE_RE =
    /\.(java|cs|aspx|ashx|ascx|vb|js|jsx|ts|tsx|vue|py|go|kt|kts|rs|php|rb|swift|m|mm|c|cc|cpp|h|hpp|scala|groovy|sql|xml|config|json|yml|yaml|properties|gradle|kts)$/i;
  const PRIORITY_FILES = [
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "requirements-dev.txt",
    "Pipfile",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "application.properties",
    "application.yml",
    "application.yaml",
    "appsettings.json",
    "appsettings.Development.json",
    "src/main/resources/application.properties",
    "src/main/resources/application.yml",
    "src/main/resources/application.yaml",
  ];
  const SKIP_DIRS = new Set([
    ".git",
    "node_modules",
    "target",
    "bin",
    "obj",
    "dist",
    "build",
    "vendor",
    "__pycache__",
    ".idea",
    ".vs",
    "packages",
  ]);
  const add = (rel) => {
    if (!rel || seen.has(rel) || out.length >= limit) return;
    const abs = path.join(root, rel);
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      seen.add(rel);
      out.push(rel);
    }
  };

  // 依赖/配置优先纳入（门禁必扫面）
  for (const rel of PRIORITY_FILES) add(rel);
  try {
    const resDir = path.join(root, "src/main/resources");
    if (fs.existsSync(resDir)) {
      for (const name of fs.readdirSync(resDir)) {
        if (/^application.*\.(properties|ya?ml)$/i.test(name)) {
          add(`src/main/resources/${name}`);
        }
      }
    }
  } catch {
    /* ignore */
  }

  const walkDir = (absDir, relDir, depth) => {
    if (out.length >= limit || depth > 5) return;
    let entries;
    try {
      entries = fs.readdirSync(absDir, { withFileTypes: true });
    } catch {
      return;
    }
    const files = [];
    const dirs = [];
    for (const ent of entries) {
      if (ent.name.startsWith(".")) continue;
      if (ent.isDirectory()) {
        if (!SKIP_DIRS.has(ent.name)) dirs.push(ent);
      } else {
        files.push(ent);
      }
    }
    for (const ent of files) {
      if (out.length >= limit) break;
      const isDocker = /^Dockerfile/i.test(ent.name);
      if (!isDocker && !CODE_RE.test(ent.name)) continue;
      const rel = relDir ? `${relDir}/${ent.name}` : ent.name;
      add(rel);
    }
    for (const ent of dirs) {
      if (out.length >= limit) break;
      const rel = relDir ? `${relDir}/${ent.name}` : ent.name;
      walkDir(path.join(absDir, ent.name), rel, depth + 1);
    }
  };

  const raw = (paths || []).map((p) => String(p || "").trim()).filter(Boolean);
  for (const item of raw) {
    const { rel } = toWorkspaceRelative(root, item);
    if (!rel) continue;
    const abs = path.join(root, rel);
    if (!fs.existsSync(abs)) continue;
    const st = fs.statSync(abs);
    if (st.isFile()) add(rel);
    else if (st.isDirectory()) walkDir(abs, rel, 0);
  }

  if (out.length < Math.min(4, limit)) {
    for (const seed of [
      "src/main/java",
      "src/main/resources",
      "src",
      "app",
      "apps",
      "Controllers",
      "Models",
      "Pages",
      "App_Code",
      "classes",
      "lib",
    ]) {
      const abs = path.join(root, seed);
      if (fs.existsSync(abs) && fs.statSync(abs).isDirectory()) {
        walkDir(abs, seed, 0);
      }
    }
  }
  if (out.length < Math.min(4, limit)) {
    walkDir(root, "", 0);
  }
  return out;
}

function countBySev(findings) {
  const out = { P0: 0, P1: 0, P2: 0 };
  for (const f of findings) {
    if (out[f.severity] != null) out[f.severity] += 1;
  }
  return out;
}

function dedupeFindings(list) {
  const seen = new Set();
  const out = [];
  for (const f of list) {
    const key = `${f.severity}|${f.path}|${f.line}|${f.rule}|${(f.message || "").slice(0, 80)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(f);
  }
  return out;
}

async function runReview(task) {
  const resolved = resolveTaskWorkspace(task);
  const root = resolved.root;
  const ready = resolved.ready;
  if (!ready || !root) {
    return {
      status: "no_workspace",
      findings: [],
      file_contents: [],
      diagnostics_count: { P0: 0, P1: 0, P2: 0 },
      raw_summary: resolved.error || "未指定有效工程目录",
      workspace_root: "",
      files: [],
      provider: "vscode",
      errors: [resolved.error || "no_workspace"],
      hint: "请在网页选择要审核的工程，或在 VS Code 中打开文件夹",
    };
  }

  const paths = Array.isArray(task.paths) ? task.paths : [];
  const prompt = String(task.prompt || "");
  const conf = cfg();
  const sources = [];
  let findings = [];
  let files = [];
  let mcpMeta = null;
  let mcpError = null;

  // 先诊断 + 规则 + 读源码（快路径），MCP 放最后且短超时，避免 npx 卡住拖死整次审核
  // 诊断仅对「当前已打开」工程有效；选中其它目录时跳过诊断
  const cur = workspaceInfo();
  const sameAsOpen =
    cur.root && path.resolve(cur.root) === path.resolve(root);
  if (sameAsOpen) {
    const diag = collectDiagnostics(root, paths);
    if (diag.findings.length) {
      sources.push("vscode-diagnostics");
      findings = findings.concat(diag.findings);
      files = diag.files;
    }
  } else {
    // 非当前打开目录：仍可读盘审源码；勿被 Agent 理解成 Bridge 离线
    sources.push("workspace:selected-not-open");
  }

  if (!findings.length && conf.allowFallbackRules) {
    const fb = scanFilesFallback(root, paths, prompt);
    if (fb.findings.length) {
      sources.push("fallback-rules");
      findings = fb.findings;
      files = fb.files;
    }
  }

  findings = dedupeFindings(findings);
  let reviewFiles = files.length
    ? files
    : resolveReviewTargets(root, paths);

  let file_contents = [];
  let readErrors = [];
  const wantContents = task.include_file_contents !== false;
  if (wantContents) {
    const toRead = [];
    const seen = new Set();
    for (const p of [...paths, ...reviewFiles]) {
      const { rel } = toWorkspaceRelative(root, p);
      if (rel && !seen.has(rel)) {
        const abs = path.join(root, rel);
        if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
          seen.add(rel);
          toRead.push(rel);
        } else if (fs.existsSync(abs) && fs.statSync(abs).isDirectory()) {
          for (const r of resolveReviewTargets(root, [rel], 8)) {
            if (!seen.has(r)) {
              seen.add(r);
              toRead.push(r);
            }
          }
        }
      }
    }
    if (!toRead.length) {
      for (const r of resolveReviewTargets(root, paths, 8)) {
        if (!seen.has(r)) {
          seen.add(r);
          toRead.push(r);
        }
      }
    }
    if (!toRead.length) {
      for (const f of findings) {
        if (f.path && !seen.has(f.path)) {
          seen.add(f.path);
          toRead.push(f.path);
        }
        if (toRead.length >= 8) break;
      }
    }
    if (toRead.length) {
      const packed = readWorkspaceFiles(root, toRead);
      file_contents = packed.file_contents || [];
      readErrors = packed.errors || [];
      if (file_contents.length) sources.push("file_contents");
      reviewFiles = reviewFiles.length
        ? reviewFiles
        : file_contents.map((f) => f.path);
    }
  }

  if (conf.mcpEnabled) {
    vscode.window.setStatusBarMessage("WorkBuddy: 调用 MCP code_checker…", 8000);
    const mcp = await runMcpCodeReview({
      command: conf.mcpCommand,
      args: conf.mcpArgs,
      cwd: root,
      toolName: conf.mcpTool,
      paths,
      prompt,
      timeoutMs: conf.mcpTimeoutSec * 1000,
    });
    mcpMeta = mcp.meta;
    if (mcp.ok) {
      sources.unshift(`mcp:${mcp.meta.toolUsed || conf.mcpTool}`);
      findings = dedupeFindings(findings.concat(mcp.findings || []));
    } else {
      mcpError = mcp.error;
      sources.push("mcp:failed");
    }
  }

  const emptyHint =
    "MCP/诊断未给出 finding。请基于下方 file_contents 做二次深度审查并产出 P0/P1/P2；禁止让用户粘贴代码。";

  let raw_summary;
  if (findings.length) {
    raw_summary = `审核完成（来源: ${sources.join(" + ")}）：${findings.length} 条 finding，附带 ${file_contents.length} 个文件内容`;
  } else {
    raw_summary =
      `未从 MCP/诊断得到 finding（来源: ${sources.join(", ") || "none"}）。` +
      (mcpError ? ` MCP 错误: ${mcpError}.` : "") +
      (file_contents.length
        ? ` 已附带 ${file_contents.length} 个文件内容——Agent 必须基于源码完成深度审查。`
        : ` ${emptyHint}`);
  }

  return {
    status: "ok",
    findings,
    file_contents,
    diagnostics_count: countBySev(findings),
    raw_summary,
    workspace_root: root,
    files: reviewFiles.length ? reviewFiles : file_contents.map((f) => f.path),
    provider: findings.length && sources[0]?.startsWith("mcp:") ? "mcp+vscode" : "vscode",
    sources,
    mcp_tool: mcpMeta?.toolUsed || null,
    mcp_tools_available: mcpMeta?.tools || [],
    mcp_error: mcpError || null,
    review_empty: findings.length === 0,
    hint: findings.length
      ? "请基于 findings 与 file_contents 撰写专业报告；勿再调用服务端 read_file。"
      : file_contents.length
        ? emptyHint
        : "未带回源码。请调用 request_ide_read_files 读取工作区相对路径后再审。",
    errors: [...(mcpError ? [mcpError] : []), ...readErrors],
    bridge_version: conf.extensionVersion,
  };
}

function runReadFiles(task) {
  const resolved = resolveTaskWorkspace(task);
  const root = resolved.root;
  const ready = resolved.ready;
  if (!ready || !root) {
    return {
      status: "no_workspace",
      file_contents: [],
      files: [],
      errors: [resolved.error || "no_workspace"],
      raw_summary: resolved.error || "未指定有效工程目录",
      hint: "请在网页选择要审核的工程，或在 VS Code 中打开文件夹",
      provider: "vscode",
    };
  }
  const paths = Array.isArray(task.paths) ? task.paths : [];
  const packed = readWorkspaceFiles(root, paths);
  packed.hint =
    "内容来自本机工作区。WorkBuddy 服务端 read_file 无法访问这些路径，请只用本结果。";
  packed.workspace_root = root;
  return packed;
}

async function tick() {
  if (!connected || tickBusy) return;
  tickBusy = true;
  try {
    const { api, token } = cfg();
    if (!token) {
      setStatus("$(warning) WorkBuddy: 未配置 token", "在设置中填写 workbuddy.token");
      return;
    }
    const ws = workspaceInfo();
    const recent = await collectRecentWorkspaces();
    try {
      await request(
        "POST",
        `${api}/api/ide/bridge/heartbeat`,
        token,
        {
          bridge_id: bridgeId,
          workspace_root: ws.root,
          workspace_ready: ws.ready,
          recent_workspaces: recent,
        },
        8000
      );
    } catch (e) {
      setStatus(`$(error) WorkBuddy: 心跳失败`, String(e.message || e));
      return;
    }

    setStatus(
      ws.ready
        ? `$(cloud) WorkBuddy: 已连接 v${cfg().extensionVersion}`
        : `$(cloud) WorkBuddy: 未开工程 v${cfg().extensionVersion}`,
      ws.ready ? ws.root : "请打开文件夹后再发起审核"
    );

    try {
      const polled = await request(
        "GET",
        `${api}/api/ide/bridge/poll?bridge_id=${encodeURIComponent(bridgeId)}&wait_sec=0`,
        token,
        null,
        8000
      );
      const task = polled && polled.task;
      if (!task) return;

      const taskId = String(task.task_id || "");
      const intent = String(task.intent || "code_review");
      vscode.window.setStatusBarMessage(
        `WorkBuddy: ${intent === "read_files" ? "读取" : "审核"} ${taskId.slice(0, 8)}…`,
        15000
      );
      const result =
        intent === "read_files" ? runReadFiles(task) : await runReview(task);
      await request(
        "POST",
        `${api}/api/ide/bridge/result`,
        token,
        { task_id: taskId, ...result },
        30000
      );
    } catch (e) {
      console.error("[workbuddy] poll/review", e);
    }
  } finally {
    tickBusy = false;
  }
}

async function promptAndSaveToken(existing) {
  const input = await vscode.window.showInputBox({
    prompt: "粘贴 WorkBuddy 登录后的 access_token（不要带 Bearer）",
    password: true,
    ignoreFocusOut: true,
    value: existing ? "" : undefined,
    placeHolder: existing ? "已有旧 token，粘贴新的以覆盖" : undefined,
  });
  if (!input) return null;
  const token = input.trim();
  await vscode.workspace
    .getConfiguration("workbuddy")
    .update("token", token, vscode.ConfigurationTarget.Global);
  return token;
}

async function connect() {
  let { api, token } = cfg();
  if (!token) {
    token = await promptAndSaveToken("");
    if (!token) return;
  }

  bridgeId = `vscode-${crypto.randomBytes(6).toString("hex")}`;
  const ws = workspaceInfo();
  if (ws.root) rememberWorkspace(ws.root);
  const recent = await collectRecentWorkspaces();
  try {
    await request("POST", `${api}/api/ide/bridge/register`, token, {
      bridge_id: bridgeId,
      workspace_root: ws.root,
      workspace_ready: ws.ready,
      carrier: "vscode",
      recent_workspaces: recent,
    });
  } catch (e) {
    const msg = String(e.message || e);
    const expired = /401|过期|Unauthorized|登录/i.test(msg);
    if (expired) {
      const pick = await vscode.window.showErrorMessage(
        `WorkBuddy 连接失败: ${msg}`,
        "重新输入 Token"
      );
      if (pick === "重新输入 Token") {
        const next = await promptAndSaveToken(token);
        if (next) {
          await connect();
        }
      }
      return;
    }
    vscode.window.showErrorMessage(`WorkBuddy 连接失败: ${msg}`);
    return;
  }

  connected = true;
  if (timer) clearInterval(timer);
  timer = setInterval(() => {
    tick().catch(() => {});
  }, 1500);
  await tick();

  if (!ws.ready) {
    vscode.window.showWarningMessage(
      "WorkBuddy 已连接，但当前未打开文件夹。请打开要审核的项目后再在网页发起审核。"
    );
  } else {
    const mcpOn = cfg().mcpEnabled;
    vscode.window.showInformationMessage(
      `WorkBuddy 已连接 v${cfg().extensionVersion}：${ws.root}` +
        (mcpOn ? "（MCP 主审已开）" : "（MCP 已关）") +
        "。若状态栏没有版本号，请执行 Developer: Reload Window。"
    );
  }
}

async function pairWithCode() {
  const { api } = cfg();
  const code = await vscode.window.showInputBox({
    prompt: "输入网页侧栏「配对 VS Code」显示的 6 位配对码",
    ignoreFocusOut: true,
    placeHolder: "例如 A3K9MX",
  });
  if (!code) return;
  try {
    const data = await request(
      "POST",
      `${api}/api/ide/bridge/pairing/redeem`,
      "",
      { code: code.trim() },
      15000
    );
    const token = String(data.access_token || "").trim();
    if (!token) {
      vscode.window.showErrorMessage("配对失败：未返回 access_token");
      return;
    }
    await vscode.workspace
      .getConfiguration("workbuddy")
      .update("token", token, vscode.ConfigurationTarget.Global);
    vscode.window.showInformationMessage(
      "配对成功：已写入长期凭证（约 90 天自动连接）。正在连接…"
    );
    await connect();
  } catch (e) {
    vscode.window.showErrorMessage(`配对失败: ${e.message || e}`);
  }
}

async function statusBarAction() {
  const pick = await vscode.window.showQuickPick(
    [
      { label: "WorkBuddy: Pair（网页配对码）", id: "pair" },
      { label: "WorkBuddy: Connect", id: "connect" },
      { label: "WorkBuddy: Disconnect", id: "disconnect" },
      { label: "WorkBuddy: Set Token（手动）", id: "token" },
    ],
    { placeHolder: "WorkBuddy Bridge" }
  );
  if (!pick) return;
  if (pick.id === "pair") await pairWithCode();
  else if (pick.id === "connect") await connect();
  else if (pick.id === "disconnect") {
    disconnect();
    vscode.window.showInformationMessage("WorkBuddy 已断开");
  } else if (pick.id === "token") {
    const next = await promptAndSaveToken(cfg().token);
    if (next) await connect();
  }
}

function disconnect() {
  connected = false;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  setStatus(
    `$(cloud-offline) WorkBuddy: 未连接 v${cfg().extensionVersion}`,
    "点击状态栏：Pair / Connect"
  );
}

function activate(context) {
  extContext = context;
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  statusBar.command = "workbuddy.statusMenu";
  statusBar.show();
  setStatus(
    `$(cloud-offline) WorkBuddy: 未连接 v${cfg().extensionVersion}`,
    "点击状态栏：Pair / Connect"
  );

  context.subscriptions.push(statusBar);
  context.subscriptions.push(
    vscode.commands.registerCommand("workbuddy.connect", () => connect())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("workbuddy.pair", () => pairWithCode())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("workbuddy.statusMenu", () => statusBarAction())
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("workbuddy.setToken", async () => {
      const next = await promptAndSaveToken(cfg().token);
      if (next) {
        vscode.window.showInformationMessage("Token 已保存，正在连接…");
        await connect();
      }
    })
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("workbuddy.disconnect", () => {
      disconnect();
      vscode.window.showInformationMessage("WorkBuddy 已断开");
    })
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      if (connected) tick().catch(() => {});
    })
  );

  if (cfg().autoConnect && cfg().token) {
    connect().catch(() => {});
  }
}

function deactivate() {
  disconnect();
}

module.exports = { activate, deactivate };
