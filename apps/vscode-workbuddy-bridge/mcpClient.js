/**
 * 最小 MCP stdio 客户端（Content-Length 帧），无第三方依赖。
 * 用于调用 vscode-as-mcp-server 等成熟 MCP 工具（如 code_checker）。
 */
const { spawn } = require("child_process");

class McpStdioClient {
  constructor(command, args, { cwd, timeoutMs } = {}) {
    this.command = command;
    this.args = args || [];
    this.cwd = cwd;
    this.timeoutMs = timeoutMs || 45000;
    this.proc = null;
    this.nextId = 1;
    this.pending = new Map();
    this.buffer = Buffer.alloc(0);
    this.stderrTail = [];
  }

  async start() {
    this.proc = spawn(this.command, this.args, {
      cwd: this.cwd,
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.proc.stdout.on("data", (chunk) => this._onStdout(chunk));
    this.proc.stderr.on("data", (chunk) => {
      const s = chunk.toString("utf8");
      this.stderrTail.push(s);
      if (this.stderrTail.length > 40) this.stderrTail.shift();
    });
    this.proc.on("error", (err) => {
      for (const [, slot] of this.pending) {
        slot.reject(err);
      }
      this.pending.clear();
    });

    await this.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "workbuddy-vscode-bridge", version: "0.2.0" },
    });
    this.notify("notifications/initialized", {});
  }

  close() {
    if (!this.proc) return;
    try {
      this.proc.stdin.end();
    } catch {
      /* ignore */
    }
    try {
      this.proc.kill();
    } catch {
      /* ignore */
    }
    this.proc = null;
  }

  notify(method, params) {
    const msg = { jsonrpc: "2.0", method };
    if (params !== undefined) msg.params = params;
    this._write(msg);
  }

  request(method, params) {
    const id = this.nextId++;
    const msg = { jsonrpc: "2.0", id, method };
    if (params !== undefined) msg.params = params;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`MCP 超时: ${method}`));
      }, this.timeoutMs);
      this.pending.set(id, {
        resolve: (v) => {
          clearTimeout(timer);
          resolve(v);
        },
        reject: (e) => {
          clearTimeout(timer);
          reject(e);
        },
      });
      try {
        this._write(msg);
      } catch (e) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(e);
      }
    });
  }

  async listTools() {
    const result = await this.request("tools/list", {});
    return Array.isArray(result?.tools) ? result.tools : [];
  }

  async callTool(name, args) {
    return this.request("tools/call", { name, arguments: args || {} });
  }

  getStderrTail() {
    return this.stderrTail.join("").slice(-2000);
  }

  _write(msg) {
    if (!this.proc || !this.proc.stdin.writable) {
      throw new Error("MCP 进程未启动");
    }
    const body = Buffer.from(JSON.stringify(msg), "utf8");
    const header = Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii");
    this.proc.stdin.write(Buffer.concat([header, body]));
  }

  _onStdout(chunk) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (true) {
      const headerEnd = this.buffer.indexOf("\r\n\r\n");
      if (headerEnd < 0) return;
      const header = this.buffer.slice(0, headerEnd).toString("ascii");
      const match = /Content-Length:\s*(\d+)/i.exec(header);
      if (!match) {
        this.buffer = this.buffer.slice(headerEnd + 4);
        continue;
      }
      const len = parseInt(match[1], 10);
      const total = headerEnd + 4 + len;
      if (this.buffer.length < total) return;
      const body = this.buffer.slice(headerEnd + 4, total).toString("utf8");
      this.buffer = this.buffer.slice(total);
      let msg;
      try {
        msg = JSON.parse(body);
      } catch {
        continue;
      }
      if (msg && msg.id != null && (msg.result !== undefined || msg.error !== undefined)) {
        const slot = this.pending.get(msg.id);
        if (!slot) continue;
        this.pending.delete(msg.id);
        if (msg.error) slot.reject(new Error(JSON.stringify(msg.error)));
        else slot.resolve(msg.result);
      }
    }
  }
}

/**
 * 把 MCP tools/call 结果尽量规范成 findings[]
 */
function normalizeMcpFindings(result) {
  const findings = [];
  const text = contentText(result);

  const tryList = (list) => {
    if (!Array.isArray(list)) return false;
    let n = 0;
    for (const item of list) {
      if (item && typeof item === "object") {
        findings.push(coerceFinding(item));
        n += 1;
      }
    }
    return n > 0;
  };

  if (result && typeof result === "object") {
    if (tryList(result.findings) || tryList(result.diagnostics) || tryList(result.issues)) {
      return findings;
    }
  }
  if (tryList(result)) return findings;

  const stripped = text.trim();
  if (stripped.startsWith("{") || stripped.startsWith("[")) {
    try {
      return normalizeMcpFindings(JSON.parse(stripped));
    } catch {
      /* ignore */
    }
  }

  // 常见：按行 "path:line: message"
  const lineRe = /^(.+?):(\d+):\d+:\s*(.+)$/;
  for (const line of stripped.split(/\r?\n/)) {
    const m = lineRe.exec(line.trim());
    if (m) {
      findings.push({
        severity: "P1",
        path: m[1],
        line: parseInt(m[2], 10) || 0,
        rule: "mcp",
        message: m[3],
        suggestion: "",
      });
    }
  }
  if (findings.length) return findings;

  if (stripped) {
    findings.push({
      severity: "P2",
      path: "",
      line: 0,
      rule: "mcp-raw",
      message: stripped.slice(0, 1200),
      suggestion: "对照 MCP 原始输出确认",
    });
  }
  return findings;
}

function contentText(result) {
  if (result == null) return "";
  if (typeof result === "string") return result;
  if (typeof result === "object" && Array.isArray(result.content)) {
    return result.content
      .map((b) => (b && b.type === "text" ? b.text : JSON.stringify(b)))
      .join("\n");
  }
  try {
    return JSON.stringify(result);
  } catch {
    return String(result);
  }
}

function coerceFinding(item) {
  let sev = String(item.severity || item.level || item.severityCode || "P2");
  const low = sev.toLowerCase();
  if (["error", "critical", "high", "0"].includes(low)) sev = "P0";
  else if (["warning", "warn", "medium", "1"].includes(low)) sev = "P1";
  else if (["info", "hint", "low", "2", "3"].includes(low)) sev = "P2";
  if (!["P0", "P1", "P2"].includes(sev)) sev = "P2";
  let line = item.line || item.lineno || item.startLine || 0;
  line = parseInt(line, 10) || 0;
  return {
    severity: sev,
    path: String(item.path || item.file || item.uri || item.source || ""),
    line,
    rule: String(item.rule || item.code || item.source || "mcp"),
    message: String(item.message || item.msg || item.text || JSON.stringify(item)),
    suggestion: String(item.suggestion || item.fix || ""),
  };
}

async function runMcpCodeReview({ command, args, cwd, toolName, paths, prompt, timeoutMs }) {
  const client = new McpStdioClient(command, args, { cwd, timeoutMs });
  const meta = { tools: [], toolUsed: "", stderr: "" };
  try {
    await client.start();
    const tools = await client.listTools();
    meta.tools = tools.map((t) => t.name).filter(Boolean);
    const preferred = toolName || "code_checker";
    const pick =
      meta.tools.includes(preferred)
        ? preferred
        : meta.tools.find((n) => /check|diagnostic|lint|review/i.test(n)) || meta.tools[0];
    if (!pick) {
      throw new Error("MCP 未暴露任何 tool");
    }
    meta.toolUsed = pick;

    const argCandidates = [
      { paths: paths || [], prompt: prompt || "" },
      { path: (paths && paths[0]) || "", prompt: prompt || "" },
      {},
    ];
    let lastErr = null;
    let result = null;
    for (const a of argCandidates) {
      try {
        result = await client.callTool(pick, a);
        lastErr = null;
        break;
      } catch (e) {
        lastErr = e;
      }
    }
    if (lastErr && result == null) throw lastErr;

    const findings = normalizeMcpFindings(result);
    return {
      ok: true,
      findings,
      raw_summary: contentText(result).slice(0, 2000),
      meta,
    };
  } catch (e) {
    meta.stderr = client.getStderrTail();
    return {
      ok: false,
      error: String(e.message || e),
      findings: [],
      meta,
    };
  } finally {
    client.close();
  }
}

module.exports = {
  McpStdioClient,
  runMcpCodeReview,
  normalizeMcpFindings,
};
