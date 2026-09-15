# Local dev without Docker: SQLite backend + Next.js frontend.
# Usage: ./scripts/run_local.sh   (or run the two commands separately on Windows)
set -e
(cd backend && python -m uvicorn app.main:app --reload --port 8000) &
BACK=$!
(cd frontend && npm run dev) &
FRONT=$!
trap "kill $BACK $FRONT" EXIT
wait
