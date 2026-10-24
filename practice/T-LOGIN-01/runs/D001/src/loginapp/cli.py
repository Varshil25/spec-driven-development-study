"""Command line: `adduser` and `serve`."""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from . import users

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INVALID = 2
EXIT_EXISTS = 3

SECRET_ENV = "LOGINAPP_SECRET"
MIN_SECRET_BYTES = 32  # HS256 keys should be at least as long as the hash output


def _error(message: str) -> None:
    print(f"loginapp: error: {message}", file=sys.stderr)


def _read_password_line() -> str | None:
    """Read one line from standard input, without its line ending.

    The line is decoded as UTF-8 whatever the locale, to match how the login
    form is decoded. At a terminal the password is not echoed. Returns None
    if no valid UTF-8 line can be read.
    """
    stdin = sys.stdin
    if stdin is None:
        return None
    try:
        if stdin.isatty():
            return getpass.getpass("Password: ")
        raw = stdin.buffer.readline()
        line = raw.decode("utf-8")
    except (OSError, ValueError, EOFError, AttributeError):  # ValueError covers UnicodeDecodeError
        return None
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def cmd_adduser(args: argparse.Namespace) -> int:
    if not users.is_valid_username(args.username):
        _error("username must be 3 to 32 letters, digits or underscores")
        return EXIT_INVALID
    password = _read_password_line()
    if password is None:
        _error("could not read the password from standard input")
        return EXIT_INVALID
    if not users.is_valid_password(password):
        _error(f"password must be at least {users.MIN_PASSWORD_LENGTH} characters")
        return EXIT_INVALID
    try:
        users.add_user(args.users, args.username, password)
    except users.UserExistsError:
        _error(f"user {args.username!r} already exists")
        return EXIT_EXISTS
    except users.UsersFileError as exc:
        _error(str(exc))
        return EXIT_ERROR
    print(f"added {args.username}", flush=True)
    return EXIT_OK


def cmd_serve(args: argparse.Namespace) -> int:
    from . import server  # imported here so `adduser` stays light

    secret = os.environ.get(SECRET_ENV)
    if not secret:
        _error(f"the environment variable {SECRET_ENV} must be set to the session signing secret")
        return EXIT_ERROR
    if not 0 < args.port < 65536:
        _error("--port must be between 1 and 65535")
        return EXIT_INVALID
    try:
        accounts = users.load_users(args.users)
    except users.UsersFileError as exc:
        _error(str(exc))
        return EXIT_ERROR
    if not accounts:
        print(f"loginapp: warning: no accounts in {args.users}", file=sys.stderr, flush=True)

    secret_bytes = os.fsencode(secret)
    if len(secret_bytes) < MIN_SECRET_BYTES:
        print(f"loginapp: warning: {SECRET_ENV} is shorter than {MIN_SECRET_BYTES} bytes; "
              "use a long random value", file=sys.stderr, flush=True)

    try:
        httpd = server.LoginServer((server.HOST, args.port), server.App(args.users, secret_bytes))
    except OSError as exc:
        _error(f"cannot listen on {server.HOST}:{args.port}: {exc.strerror or exc}")
        return EXIT_ERROR
    with httpd:
        print(f"listening on {server.HOST}:{args.port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m loginapp",
                                     description="A small web application with a login page.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    add = commands.add_parser("adduser", help="add an account; the password is read from standard input")
    add.add_argument("username", metavar="USERNAME")
    add.add_argument("--users", required=True, metavar="FILE", help="the users file")
    add.set_defaults(handler=cmd_adduser)

    serve = commands.add_parser("serve", help=f"run the web server (needs {SECRET_ENV})")
    serve.add_argument("--port", required=True, type=int, metavar="PORT")
    serve.add_argument("--users", required=True, metavar="FILE", help="the users file")
    serve.set_defaults(handler=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
