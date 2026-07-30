/**
 * 工作区安全读文件（与 Python local_files.py 对齐）。
 */
const fs = require("fs");
const path = require("path");

const MAX_FILE_BYTES = 80 * 1024;
const MAX_TOTAL_BYTES = 240 * 1024;
const MAX_FILES = 8;

const SENSITIVE_BASENAMES = new Set([
  ".env",
  ".env.local",
  ".env.production",
  ".env.development",
  ".env.staging",
  "id_rsa",
  "id_dsa",
  "id_ecdsa",
  "id_ed25519",
  "credentials.json",
  "service-account.json",
  "secrets.json",
  ".npmrc",
  ".pypirc",
]);
const SENSITIVE_SUFFIXES = [".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"];

function isSensitiveRel(rel) {
  const r = String(rel || "").replace(/\\/g, "/");
  const base = path.basename(r);
  if (SENSITIVE_BASENAMES.has(base)) return `拒绝读取敏感文件: ${rel}`;
  const low = base.toLowerCase();
  for (const suf of SENSITIVE_SUFFIXES) {
    if (low.endsWith(suf)) return `拒绝读取敏感文件: ${rel}`;
  }
  if (/(^|\/)\.env(\.|$)/i.test(r) || /(^|\/)id_(rsa|dsa|ecdsa|ed25519)$/i.test(r)) {
    return `拒绝读取敏感文件: ${rel}`;
  }
  return null;
}

function toWorkspaceRelative(root, raw) {
  const s = String(raw || "").trim();
  if (!s) return { error: "空路径" };
  const rootResolved = path.resolve(root);
  let abs;
  if (path.isAbsolute(s)) {
    abs = path.resolve(s);
  } else {
    if (s.split(/[/\\]/).includes("..")) return { error: `拒绝路径穿越: ${s}` };
    abs = path.resolve(rootResolved, s);
  }
  const rel = path.relative(rootResolved, abs);
  if (rel.startsWith("..") || path.isAbsolute(rel)) {
    return { error: `路径不在工作区内: ${s}` };
  }
  const posix = rel.split(path.sep).join("/");
  const sens = isSensitiveRel(posix);
  if (sens) return { error: sens };
  return { rel: posix };
}

function readWorkspaceFiles(root, paths, opts = {}) {
  const maxFiles = opts.maxFiles || MAX_FILES;
  const maxFileBytes = opts.maxFileBytes || MAX_FILE_BYTES;
  const maxTotalBytes = opts.maxTotalBytes || MAX_TOTAL_BYTES;
  const rawPaths = (paths || []).map((p) => String(p).trim()).filter(Boolean);
  const items = [];
  const errors = [];
  let total = 0;

  for (const raw of rawPaths.slice(0, Math.max(1, maxFiles))) {
    const { rel, error } = toWorkspaceRelative(root, raw);
    if (error || !rel) {
      errors.push(error || `无效路径: ${raw}`);
      continue;
    }
    const abs = path.join(root, rel);
    if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
      errors.push(`文件不存在: ${rel}`);
      continue;
    }
    let buf;
    try {
      buf = fs.readFileSync(abs);
    } catch (e) {
      errors.push(`读取失败 ${rel}: ${e.message || e}`);
      continue;
    }
    let truncated = false;
    if (buf.length > maxFileBytes) {
      buf = buf.subarray(0, maxFileBytes);
      truncated = true;
    }
    if (total + buf.length > maxTotalBytes) {
      errors.push(`达到总字节上限，跳过后续（已读 ${items.length} 个）`);
      break;
    }
    const content = buf.toString("utf8");
    total += buf.length;
    items.push({ path: rel, content, bytes: buf.length, truncated });
  }

  return {
    status: items.length ? "ok" : "error",
    workspace_root: root,
    file_contents: items,
    files: items.map((i) => i.path),
    errors,
    provider: "vscode",
    raw_summary: `已读取 ${items.length} 个文件（共 ${total} 字节）`,
  };
}

module.exports = {
  toWorkspaceRelative,
  readWorkspaceFiles,
  isSensitiveRel,
  MAX_FILE_BYTES,
  MAX_TOTAL_BYTES,
  MAX_FILES,
};
