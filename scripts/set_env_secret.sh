#!/usr/bin/env bash
# Safely set ONE secret in an .env file.
#
# - the value is typed at a hidden prompt: not echoed, not in shell history,
#   not in argv or `ps` (only bash builtins ever see it);
# - only the line KEY=... is replaced, every other line, the file owner and
#   mode are kept; a 0600 backup of the previous file is made first;
# - the value is never printed.
#
# Usage (interactive terminal required, run on the host that owns the file):
#   bash scripts/set_env_secret.sh /path/to/.env TELEGRAM_BOT_TOKEN [--verify]
#
#   --verify  TELEGRAM_BOT_TOKEN only: call Telegram getMe (no message is sent,
#             no polling) and print just "ok @username" or the HTTP status.
#   --stdin   read both prompts from stdin instead of a terminal (tests only;
#             never pipe a real secret through a command line or history).
set -euo pipefail
umask 077

die() { echo "ERROR: $*" >&2; exit 1; }

ENV_FILE=${1:-}; KEY=${2:-}
[ -n "$ENV_FILE" ] && [ -n "$KEY" ] || die "usage: $0 <env-file> <KEY> [--verify] [--stdin]"
shift 2
VERIFY=0; FROM_STDIN=0
for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    --stdin) FROM_STDIN=1 ;;
    *) die "unknown option: $arg" ;;
  esac
done

[[ $KEY =~ ^[A-Z][A-Z0-9_]*$ ]] || die "invalid key name"
[ -f "$ENV_FILE" ] || die "env file not found: $ENV_FILE"
[ -w "$ENV_FILE" ] || die "env file is not writable: $ENV_FILE"
if [ "$VERIFY" = 1 ] && [ "$KEY" != "TELEGRAM_BOT_TOKEN" ]; then die "--verify works only with TELEGRAM_BOT_TOKEN"; fi
if [ "$FROM_STDIN" = 0 ] && [ ! -t 0 ]; then die "an interactive terminal is required (use ssh -t)"; fi

if [ "$FROM_STDIN" = 1 ]; then
  IFS= read -r VALUE; IFS= read -r REPEAT
else
  read -rsp "New value for $KEY (hidden): " VALUE; echo >&2
  read -rsp "Repeat the value (hidden): " REPEAT; echo >&2
fi

[ -n "$VALUE" ] || die "empty value"
[ "$VALUE" = "$REPEAT" ] || die "values do not match; nothing was changed"
[[ $VALUE =~ ^[A-Za-z0-9_:.+/=-]+$ ]] || die "value contains spaces, quotes or special characters; nothing was changed"
if [ "$KEY" = "TELEGRAM_BOT_TOKEN" ]; then
  [[ $VALUE =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]] || die "does not look like a Telegram bot token; nothing was changed"
fi
unset REPEAT

BACKUP="$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
cp -p "$ENV_FILE" "$BACKUP"
chmod 600 "$BACKUP"

TMP=$(mktemp "$ENV_FILE.XXXXXX")
trap 'rm -f "$TMP"' EXIT
FOUND=0
while IFS= read -r LINE || [ -n "$LINE" ]; do
  if [[ $LINE == "$KEY="* ]]; then
    printf '%s=%s\n' "$KEY" "$VALUE" >>"$TMP"; FOUND=1
  else
    printf '%s\n' "$LINE" >>"$TMP"
  fi
done <"$ENV_FILE"
[ "$FOUND" = 1 ] || printf '%s=%s\n' "$KEY" "$VALUE" >>"$TMP"
unset VALUE LINE

if ! chmod --reference="$ENV_FILE" "$TMP" 2>/dev/null; then
  chmod 600 "$TMP"
fi
chown --reference="$ENV_FILE" "$TMP" 2>/dev/null || true
mv "$TMP" "$ENV_FILE"
trap - EXIT
echo "OK: $KEY updated in $ENV_FILE (previous file kept as $BACKUP, mode 0600)"

if [ "$VERIFY" = 1 ]; then
  python3 - "$ENV_FILE" <<'PY'
import json, sys, urllib.error, urllib.request
token = ""
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        token = line.split("=", 1)[1].strip()
try:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=20) as r:
        data = json.load(r)
    print("getMe: ok @" + str(data["result"].get("username")) if data.get("ok") else "getMe: rejected")
except urllib.error.HTTPError as exc:
    print(f"getMe: HTTP {exc.code} (token rejected)")
    sys.exit(2)
except Exception as exc:  # never print the exception text: it may contain the URL
    print(f"getMe: failed ({type(exc).__name__})")
    sys.exit(2)
PY
fi
