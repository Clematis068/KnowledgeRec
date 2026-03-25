#!/usr/bin/env bash
set -euo pipefail

host="${API_HOST:-anyrouter.top}"

claude_cli="$(command -v claude || true)"

if [[ -z "$claude_cli" ]]; then
  echo "Error: claude command not found in PATH" >&2
  exit 1
fi

pnpm_path="$(
  grep "node_modules/@anthropic-ai/claude-code/cli.js" "$claude_cli" \
    | tail -n 1 \
    | tr ' ' '\n' \
    | grep basedir || true
)"

if [[ -n "$pnpm_path" ]]; then
  claude_cli="$(eval echo "$pnpm_path")"
fi

pnpm_path="$(realpath "$pnpm_path" 2>/dev/null || true)"

case "$(uname -s)" in
  Darwin)
    sed -i '' "s/\"api.anthropic.com\"/\"$host\"/g" "$claude_cli"
    ;;
  Linux)
    sed -i "s/\"api.anthropic.com\"/\"$host\"/g" "$claude_cli"
    ;;
  *)
    echo "错误：不支持的操作系统" >&2
    ;;
esac