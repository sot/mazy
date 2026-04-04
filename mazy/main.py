import argparse

import kadi.commands as kc
import parse_cm.paths
from cxotime import CxoTime

from mazy import __version__


def get_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument("args", nargs="*")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def as_date(arg):
    try:
        out = CxoTime(arg)
    except Exception:
        out = None
    return out

def as_load_name(arg):
    try:
        parse_cm.paths.parse_load_name(arg)
        out = arg
    except Exception:
        out = None
    return out

def as_obsid(arg):
    # Integer between 0 and 65535
    try:
        out = int(arg)
        if not (0 <= out <= 65535):
            out = None
    except Exception:
        out = None
    return out


def main():
    parser = get_opt()
    opt = parser.parse_args()
    values = {
        "date": None,
        "obsid": None,
        "load_name": None,
    }
    matchers = [
        ("date", as_date),
        ("obsid", as_obsid),
        ("load_name", as_load_name),
    ]

    for arg in opt.args:
        match = False
        for key, matcher in matchers:
            if values[key] is None:
                parsed = matcher(arg)
                if parsed is not None:
                    values[key] = parsed
                    match = True
                    break
        if not match:
            print(f"Unrecognized argument: {arg}")

    print(
        "date: {date}, obsid: {obsid}, load_name: {load_name}".format(
            **values,
        )
    )

if __name__ == "__main__":
    main()
