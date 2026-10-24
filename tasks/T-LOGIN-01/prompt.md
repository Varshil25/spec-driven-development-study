Build a small web application with a secure login page, using only Python's standard library (for example `http.server`).

User accounts are kept in a file and added from the command line:

- `python -m loginapp adduser USERNAME --users FILE` reads a password from standard input (one line) and adds the account to FILE, creating the file if needed, and prints `added USERNAME`. A username is 3 to 32 letters, digits or underscores, and a password must be at least 12 characters; otherwise it exits with status 2. An existing username exits with status 3.
- `python -m loginapp serve --port PORT --users FILE` starts the web server on 127.0.0.1 at PORT and prints `listening on 127.0.0.1:PORT` once it is ready. Sessions are signed with the secret in the environment variable `LOGINAPP_SECRET`; if it is not set, the server prints an error and exits with a non-zero status.

Pages (HTML responses use `Content-Type: text/html; charset=utf-8`):

- `GET /login` shows a login form that posts the fields `username` and `password` to `/login`.
- `POST /login` (form-encoded) checks the credentials. On success it responds `303 See Other` with `Location: /dashboard` and starts a session by setting a cookie named `session`. On failure it responds `401` with the login page and the message `Invalid username or password`.
- `GET /dashboard` with a valid session shows `Welcome, USERNAME`. Without a valid session it responds `303` with `Location: /login`.
- `POST /logout` ends the session: it clears the `session` cookie and responds `303` with `Location: /login`.
- Any other path gets `404`.

The session cookie holds a JWT signed with HS256 using `LOGINAPP_SECRET`, with the claims `sub` (the username), `iat` and `exp`. A session lasts 30 minutes: `exp` is `iat` plus 1800 seconds, and an expired token is not accepted.

Use Python 3.11 or newer and the standard library only. Put the code in a package named `loginapp` under `src/`, so that it runs with `python -m loginapp` when `src/` is on `PYTHONPATH`.

Examples:

```
$ printf 'correct-horse-battery\n' | python -m loginapp adduser alice --users users.json
added alice
$ LOGINAPP_SECRET=change-me python -m loginapp serve --port 8000 --users users.json
listening on 127.0.0.1:8000

$ curl -s -i -d 'username=alice&password=correct-horse-battery' 127.0.0.1:8000/login
HTTP/1.0 303 See Other
Location: /dashboard
Set-Cookie: session=eyJ...; ...
$ curl -s -b 'session=<the token from Set-Cookie>' 127.0.0.1:8000/dashboard
... Welcome, alice ...
$ curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:8000/dashboard
303
$ curl -s -o /dev/null -w '%{http_code}\n' -d 'username=alice&password=wrong-password-1' 127.0.0.1:8000/login
401
```
