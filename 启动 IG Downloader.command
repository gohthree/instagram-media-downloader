#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  if [[ -x /opt/homebrew/bin/python3 ]]; then
    PY=/opt/homebrew/bin/python3
  elif command -v python3 >/dev/null 2>&1; then
    PY=$(command -v python3)
  else
    echo '请先安装 Python 3.10 或更新版本。'
    read '?按 Enter 退出...'
    exit 1
  fi
  "$PY" -m venv .venv || exit 1
fi
.venv/bin/python -m pip install -r requirements.txt || { read '?依赖安装失败，按 Enter 退出...'; exit 1; }
.venv/bin/python app.py
read '?按 Enter 关闭窗口...'
