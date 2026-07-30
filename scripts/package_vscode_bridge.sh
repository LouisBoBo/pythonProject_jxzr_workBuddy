#!/usr/bin/env bash
# 打包 VS Code 扩展为 .vsix（无需 vsce；用 zip）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/apps/vscode-workbuddy-bridge"
OUT_DIR="$ROOT/dist"
VER="$(python3 -c "import json; print(json.load(open('$EXT/package.json'))['version'])")"
NAME="workbuddy-workbuddy-bridge-${VER}.vsix"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/extension" "$OUT_DIR"
cp "$EXT/package.json" "$EXT/extension.js" "$EXT/localFiles.js" "$EXT/mcpClient.js" "$EXT/README.md" \
  "$STAGE/extension/"

cat > "$STAGE/[Content_Types].xml" <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="js" ContentType="application/javascript"/>
  <Default Extension="md" ContentType="text/markdown"/>
  <Default Extension="vsixmanifest" ContentType="text/xml"/>
</Types>
EOF

cat > "$STAGE/extension.vsixmanifest" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="workbuddy-bridge" Version="${VER}" Publisher="workbuddy"/>
    <DisplayName>WorkBuddy Bridge</DisplayName>
    <Description>Connect VS Code workspace to WorkBuddy for code review</Description>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  </Assets>
</PackageManifest>
EOF

(
  cd "$STAGE"
  zip -qr "$OUT_DIR/$NAME" extension.vsixmanifest "[Content_Types].xml" extension
)

echo "Wrote $OUT_DIR/$NAME"
echo "Install: code --install-extension $OUT_DIR/$NAME"
