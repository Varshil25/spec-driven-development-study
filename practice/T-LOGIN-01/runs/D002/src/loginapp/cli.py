"""Command-line interface: `python -m loginapp COMMAND ...` (contracts/cli.md)."""

import argparse
import os
import re
import sys

from loginapp import accounts, server


class StoreOnce(argparse.Action):
    """Store an option's value, refusing a second occurrence (no silent "last wins")."""

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest, None) is not None:
            parser.error(f"argument {option_string}: may be given only once")
        setattr(namespace, self.dest, values)


def fail(message, status):
    """Write one `loginapp: error: ...` line to stderr and return the exit status."""
    sys.stderr.write(f"loginapp: error: {message}\n")
    sys.stderr.flush()
    return status


def read_password_line():
    """Read the first stdin line as bytes and remove one trailing `\\r\\n` or `\\n`."""
    line = sys.stdin.buffer.readline()
    if line.endswith(b"\r\n"):
        return line[:-2]
    if line.endswith(b"\n"):
        return line[:-1]
    return line


def cmd_adduser(args):
    name, path = args.username, args.users
    try:
        accounts.check_username(name)
    except ValueError as e:
        return fail(str(e), 2)
    try:
        password = read_password_line().decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return fail(accounts.PASSWORD_ERROR, 2)
    try:
        accounts.check_password(password)
    except ValueError as e:
        return fail(str(e), 2)
    try:
        existing = accounts.load(path, missing_ok=True)
    except accounts.AccountsFileError as e:
        return fail(str(e), 1)
    if name in existing:
        return fail(f"username {name!r} already exists", 3)
    existing[name] = accounts.make_record(password)
    try:
        accounts.save(path, existing)
    except OSError as e:
        return fail(f"cannot write accounts file {path!r}: {e.strerror or type(e).__name__}", 1)
    print(f"added {name}")
    return 0


def port_type(text):
    """Accept only 1-5 ASCII digits with a value from 1 to 65535."""
    if re.fullmatch(r"[0-9]{1,5}", text) and 1 <= int(text) <= 65535:
        return int(text)
    raise argparse.ArgumentTypeError(f"invalid port {text!r}: must be a whole number from 1 to 65535")


def cmd_serve(args):
    secret = os.environ.get("LOGINAPP_SECRET", "")
    if not secret:
        return fail("LOGINAPP_SECRET is not set or is empty", 1)
    try:
        secret.encode("utf-8")
    except UnicodeEncodeError:
        return fail("LOGINAPP_SECRET is not valid UTF-8 text", 1)
    try:
        accounts.load(args.users, missing_ok=False)
    except accounts.AccountsFileError as e:
        return fail(str(e), 1)
    try:
        srv = server.make_server(args.port, args.users, secret)
    except OSError as e:
        return fail(f"cannot listen on 127.0.0.1:{args.port}: {e.strerror or type(e).__name__}", 1)
    print(f"listening on 127.0.0.1:{args.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()
        sys.stderr.write("loginapp: stopped\n")
        sys.stderr.flush()
        return 130


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m loginapp",
        usage="%(prog)s COMMAND ...",
        allow_abbrev=False,
        add_help=False,
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND", required=True, prog="python -m loginapp")

    adduser = commands.add_parser("adduser", add_help=False, allow_abbrev=False)
    adduser.add_argument("username", metavar="USERNAME")
    adduser.add_argument("--users", metavar="FILE", required=True, action=StoreOnce)
    adduser.set_defaults(handler=cmd_adduser)

    serve = commands.add_parser("serve", add_help=False, allow_abbrev=False)
    serve.add_argument("--port", metavar="PORT", required=True, type=port_type, action=StoreOnce)
    serve.add_argument("--users", metavar="FILE", required=True, action=StoreOnce)
    serve.set_defaults(handler=cmd_serve)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.handler(args)
