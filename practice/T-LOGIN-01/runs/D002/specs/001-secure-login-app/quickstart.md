# Quickstart and Validation Guide: Secure Login Web Application

**Feature**: `001-secure-login-app` | **Plan**: [plan.md](plan.md)

This guide shows how to run the application and check the main behaviours by hand. The full behaviour is defined in [contracts/cli.md](contracts/cli.md), [contracts/http.md](contracts/http.md) and [data-model.md](data-model.md). The automated suite (`python3 -m pytest`) is what proves every FR.

## Prerequisites

- Python 3.11 or newer. Nothing else is needed at run time (FR-032, SC-008).
- pytest, for the automated tests only.
- `curl`, for the manual checks below (optional).
- Run every command from the repository root.

## 1. Run the automated suite

```bash
python3 -m pytest
```

- **Expected**: every test passes, with none skipped or xfailed, except the Python 3.11 smoke test. That test skips only when no `python3.11` is installed.
- **Time**: about 2–3 minutes, because every sign-in in the suite uses the real scrypt settings (see [research.md](research.md#r11-test-strategy-principle-iii-sc-009)).
- **Coverage check (SC-009)**: every FR ID must appear in the test suite:

```bash
for n in $(seq -w 1 32); do grep -rqE "FR-0$n\b" tests/ || echo "FR-0$n has no test"; done
```

**Expected**: no output.

## 2. Create accounts (User Story 1)

```bash
export PYTHONPATH=src
rm -f users.json
printf 'correct-horse-battery\n' | python3 -m loginapp adduser alice --users users.json; echo "exit=$?"
```

| Step | Command | Expected |
|------|---------|----------|
| first account | the command above | stdout `added alice`, `exit=0` |
| file permissions | `stat -c '%a' users.json` | `600` |
| no plain password | `grep -c correct-horse users.json` | `0` |
| second account | `printf 'another-long-pass\n' \| python3 -m loginapp adduser bob --users users.json` | `added bob`; the file now holds both accounts |
| duplicate | the first command again | stderr says `'alice' already exists`, exit 3, stdout empty |
| bad username | `printf 'correct-horse-battery\n' \| python3 -m loginapp adduser al-ice --users users.json` | stderr names `'al-ice'` and the rule, exit 2 |
| short password | `printf 'short-pass1\n' \| python3 -m loginapp adduser carol --users users.json` | stderr states the 12-character minimum, exit 2 |
| order of checks | `printf 'short\n' \| python3 -m loginapp adduser alice --users users.json` | exit **2**, not 3 (FR-004) |
| missing folder | `printf 'correct-horse-battery\n' \| python3 -m loginapp adduser dave --users no/such/dir/u.json` | stderr names the file, exit 1 |

## 3. Start the server (User Story 2)

```bash
LOGINAPP_SECRET=change-me python3 -m loginapp serve --port 8000 --users users.json
```

**Expected**: `listening on 127.0.0.1:8000` appears at once, and the process keeps running. Leave it running in its own terminal for the checks below.

Startup failures. Each check needs the port to be free, except the one that needs it in use. None of them prints `listening on`:

| Command | Expected |
|---------|----------|
| `env -u LOGINAPP_SECRET python3 -m loginapp serve --port 8001 --users users.json` | stderr names `LOGINAPP_SECRET`, exit 1 |
| `LOGINAPP_SECRET=x python3 -m loginapp serve --port 70000 --users users.json` | exit 2 |
| `LOGINAPP_SECRET=x python3 -m loginapp serve --port 8001 --users missing.json` | stderr names the file, exit 1 |
| `LOGINAPP_SECRET=x python3 -m loginapp serve --port 8000 --users users.json` (while the first server runs) | stderr names the port, exit 1 |

## 4. Sign in, view the dashboard, sign out (User Stories 2, 3 and 5)

In a second terminal:

```bash
curl -s -i 127.0.0.1:8000/login | head -20
```

**Expected**:

- status 200;
- `Content-Type: text/html; charset=utf-8`;
- `Cache-Control: no-store`, `X-Frame-Options: DENY` and `X-Content-Type-Options: nosniff`;
- a form posting `username` and `password` to `/login`.

```bash
curl -s -i -d 'username=alice&password=correct-horse-battery' 127.0.0.1:8000/login
```

**Expected**:

- `303 See Other` and `Location: /dashboard`;
- `Set-Cookie: session=eyJ…; HttpOnly; SameSite=Strict; Path=/; Max-Age=1800`.

Copy the token from that header (the text after `session=`, up to the first `;`), then:

```bash
TOKEN='<paste here>'
curl -s -b "session=$TOKEN" 127.0.0.1:8000/dashboard        # page shows "Welcome, alice" and a Sign out button
curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/dashboard                # 303 (no cookie)
curl -s -o /dev/null -w '%{http_code}\n' -b "session=${TOKEN}A" 127.0.0.1:8000/dashboard    # 303 (tampered)
```

Check the token's claims (`exp` must equal `iat + 1800`):

```bash
python3 -c "import base64,json,sys; p=sys.argv[1].split('.')[1]; print(json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4))))" "$TOKEN"
```

Sign out, then try the kept copy:

```bash
curl -s -i -X POST -b "session=$TOKEN" 127.0.0.1:8000/logout | grep -iE '^(HTTP|Location|Set-Cookie)'
# 303, Location: /login, Set-Cookie: session=; ...; Max-Age=0
curl -s -o /dev/null -w '%{http_code}\n' -b "session=$TOKEN" 127.0.0.1:8000/dashboard   # 303 (signed out)
```

## 5. Failed sign-ins and the lock (User Story 4)

```bash
for i in 1 2 3; do
  curl -s -o /dev/null -w '%{http_code}\n' -d "username=nobody&password=wrong-password-$i" 127.0.0.1:8000/login
done                                                                                # 401 three times
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w '%{http_code}\n' -d "username=bob&password=wrong-password-$i" 127.0.0.1:8000/login
done                                                                                # 401 five times, bob is now locked
curl -s -o /dev/null -w '%{http_code}\n' -d 'username=bob&password=another-long-pass' 127.0.0.1:8000/login
# 401: locked, even with the correct password
curl -s -o /dev/null -w '%{http_code}\n' -d 'username=alice&password=correct-horse-battery' 127.0.0.1:8000/login
# 303: alice is not affected
```

- **Indistinguishable failures**: compare `curl -s -i` output for an unknown username, a wrong password for `alice`, and the locked `bob`. Apart from `Date`, they must be byte-identical.
- **Lock expiry**: the lock ends 900 s after the fifth failure. The automated suite checks this boundary with a controlled clock. To check it by hand, wait 15 minutes, or restart the server, which also clears locks.

## 6. Restart ends all sessions (FR-027)

1. Sign in as `alice` and keep the token.
2. Stop the server (Ctrl+C) and start it again with the same `LOGINAPP_SECRET`.
3. Send the kept token to the dashboard:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -b "session=$TOKEN" 127.0.0.1:8000/dashboard   # 303
```

## 7. Accounts added while running (FR-011)

With the server running:

```bash
printf 'a-third-long-pass\n' | python3 -m loginapp adduser carol --users users.json
curl -s -o /dev/null -w '%{http_code}\n' -d 'username=carol&password=a-third-long-pass' 127.0.0.1:8000/login   # 303
```

## Clean up

Stop the server, then:

```bash
rm -f users.json
```
