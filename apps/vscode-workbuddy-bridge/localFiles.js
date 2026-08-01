/**
 * 工作区安全读文件（与 Python local_files.py 对齐）。
 */
const fs = require("fs");
const path = require("path");

const MAX_FILE_BYTES = 80 * 1024;
const MAX_TOTAL_BYTES = 320 * 1024;
const MAX_FILES = 5;
const BATCH_SIZE = 5;
const MAX_REPO_FILES = 200;

const CODE_SUFFIXES = new Set([
  ".java",
  ".cs",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".vue",
  ".py",
  ".go",
  ".kt",
  ".kts",
  ".rs",
  ".php",
  ".rb",
  ".swift",
  ".c",
  ".cc",
  ".cpp",
  ".h",
  ".hpp",
  ".scala",
  ".groovy",
  ".sql",
]);
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
  "coverage",
  ".next",
  ".nuxt",
  "unpackage",
  "miniprogram_npm",
  "uni_modules",
  "wxcomponents",
  "nativeplugins",
  "uview-ui",
  "uview-plus",
  "colorui",
  "tuniao-ui",
  "static",
  "assets",
  "public",
  "locale",
  "locales",
  "i18n",
  "mock",
  "mocks",
  "fixtures",
  "__tests__",
  "e2e",
]);
const SKIP_DIRS_AT_SRC_OR_ROOT = new Set([
  "test",
  "tests",
  "example",
  "examples",
  "docs",
  "doc",
]);
const SKIP_BASENAMES = new Set([
  "package-lock.json",
  "yarn.lock",
  "pnpm-lock.yaml",
  "composer.lock",
  "Gemfile.lock",
  "poetry.lock",
  "Cargo.lock",
  "package.json",
  "pom.xml",
  "build.gradle",
  "build.gradle.kts",
  "settings.gradle",
  "requirements.txt",
  "pyproject.toml",
  "go.mod",
  "go.sum",
  "Cargo.toml",
  "manifest.json",
  "pages.json",
  "Dockerfile",
  "docker-compose.yml",
  "docker-compose.yaml",
  "application.properties",
  "application.yml",
  "application.yaml",
  "appsettings.json",
  "vue.config.js",
  "vite.config.js",
  "vite.config.ts",
  "webpack.config.js",
  "babel.config.js",
  "babel.config.cjs",
  "jest.config.js",
  "jest.config.ts",
  "jsconfig.json",
  "tsconfig.json",
  "tsconfig.node.json",
  "project.config.json",
  "project.private.config.json",
  "uni.promisify.adaptor.js",
  "uni.scss",
  "README.md",
  "LICENSE",
  "CHANGELOG.md",
  ".eslintrc.js",
  ".eslintrc.cjs",
  ".prettierrc",
  ".prettierrc.js",
  "prettier.config.js",
]);
const SKIP_NAME_RE =
  /\.(min|bundle)\.js$|\.d\.ts$|\.(test|spec)\.(js|jsx|ts|tsx)$|(^|\/)(mock|mocks|__mocks__)(\/|$)|(^|\/)(locale|locales|i18n)(\/|$)|(^|\/)(static|assets|public)(\/|$)|\.(css|scss|sass|less|styl)$|\.(md|map|lock)$|\.(json|yml|yaml|toml|properties|xml|gradle)$/i;

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

function shouldSkipDir(name, relDir) {
  if (SKIP_DIRS.has(name)) return true;
  if (SKIP_DIRS_AT_SRC_OR_ROOT.has(name)) {
    const parent = String(relDir || "")
      .replace(/\\/g, "/")
      .replace(/^\/+|\/+$/g, "");
    if (!parent || parent === "src" || parent.endsWith("/src")) return true;
  }
  return false;
}

function isFunctionalSourceRel(rel) {
  const r = String(rel || "").replace(/\\/g, "/").trim();
  if (!r) return false;
  const base = path.basename(r);
  if (SKIP_BASENAMES.has(base) || base.startsWith(".")) return false;
  if (SKIP_NAME_RE.test(r)) return false;
  if (isSensitiveRel(r)) return false;
  const low = base.toLowerCase();
  for (const suf of CODE_SUFFIXES) {
    if (low.endsWith(suf)) return true;
  }
  return false;
}

function listWorkspaceSourceFiles(root, opts = {}) {
  const maxFiles = opts.maxFiles || MAX_REPO_FILES;
  const batchSize = Math.max(1, opts.batchSize || BATCH_SIZE);
  const rootResolved = path.resolve(root);
  if (!fs.existsSync(rootResolved) || !fs.statSync(rootResolved).isDirectory()) {
    return {
      status: "error",
      message: `工程目录不存在: ${root}`,
      files: [],
      batches: [],
      total: 0,
      batch_size: batchSize,
      batch_count: 0,
    };
  }

  const seen = new Set();
  const files = [];
  let truncated = false;

  const add = (rel) => {
    if (!rel || seen.has(rel) || files.length >= maxFiles) return;
    if (!isFunctionalSourceRel(rel)) return;
    const abs = path.join(rootResolved, rel);
    if (fs.existsSync(abs) && fs.statSync(abs).isFile()) {
      seen.add(rel);
      files.push(rel);
    }
  };

  const walk = (absDir, relDir, depth) => {
    if (files.length >= maxFiles || depth > 8) {
      if (files.length >= maxFiles) truncated = true;
      return;
    }
    let entries;
    try {
      entries = fs.readdirSync(absDir, { withFileTypes: true });
    } catch {
      return;
    }
    entries.sort((a, b) => {
      const af = a.isFile() ? 0 : 1;
      const bf = b.isFile() ? 0 : 1;
      if (af !== bf) return af - bf;
      return a.name.localeCompare(b.name);
    });
    for (const ent of entries) {
      if (files.length >= maxFiles) {
        truncated = true;
        return;
      }
      if (ent.name.startsWith(".")) continue;
      if (ent.isDirectory()) {
        if (shouldSkipDir(ent.name, relDir)) continue;
        walk(
          path.join(absDir, ent.name),
          relDir ? `${relDir}/${ent.name}` : ent.name,
          depth + 1
        );
        continue;
      }
      add(relDir ? `${relDir}/${ent.name}` : ent.name);
    }
  };

  walk(rootResolved, "", 0);

  const batches = [];
  for (let i = 0; i < files.length; i += batchSize) {
    batches.push(files.slice(i, i + batchSize));
  }

  return {
    status: "ok",
    workspace_root: rootResolved,
    files,
    total: files.length,
    batch_size: batchSize,
    batch_count: batches.length,
    batches,
    truncated,
    provider: "vscode",
    filter: "functional_source_only",
    raw_summary:
      `共 ${files.length} 个功能源码文件（已排除配置/锁文件/样式/文档等），` +
      `分成 ${batches.length} 批（每批 ${batchSize} 个）` +
      (truncated ? "；已达枚举上限" : ""),
    next_step:
      "按 batch 依次 request_ide_read_batch → 批纪要 → 终稿。禁止只审首批就结案。",
  };
}

module.exports = {
  toWorkspaceRelative,
  readWorkspaceFiles,
  listWorkspaceSourceFiles,
  isFunctionalSourceRel,
  isSensitiveRel,
  MAX_FILE_BYTES,
  MAX_TOTAL_BYTES,
  MAX_FILES,
  BATCH_SIZE,
  MAX_REPO_FILES,
};
