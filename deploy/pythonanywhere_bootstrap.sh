#!/usr/bin/env bash
set -euo pipefail

USERNAME="${1:?Usage: bash deploy/pythonanywhere_bootstrap.sh <pythonanywhere-username>}"
PROJECT_DIR="/home/${USERNAME}/seulfit"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"
VENV_NAME="seulfit-venv"

cd "${PROJECT_DIR}"

if ! command -v workon >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source /usr/local/bin/virtualenvwrapper.sh
fi

if ! workon "${VENV_NAME}" >/dev/null 2>&1; then
  mkvirtualenv --python=/usr/bin/python3.12 "${VENV_NAME}"
else
  workon "${VENV_NAME}"
fi

cd "${BACKEND_DIR}"
pip install -r requirements.txt

cd "${FRONTEND_DIR}"
npm ci
npm run build

cd "${BACKEND_DIR}"
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check

echo "Done. Reload the PythonAnywhere web app after WSGI/static mappings are set."
