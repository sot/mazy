import argparse
from dataclasses import dataclass
from typing import Callable

import parse_cm.paths
from cxotime import CxoTime

from mazy import __version__


@dataclass
class Args:
    """Parsed positional argument values.

    Attributes
    ----------
    date : CxoTime or None
        Parsed date argument.
    obsid : int or None
        Parsed observation ID.
    agasc_id : int or None
        Parsed AGASC ID.
    load_name : str or None
        Parsed load name.
    """

    date: CxoTime | None = None
    obsid: int | None = None
    agasc_id: int | None = None
    load_name: str | None = None


def get_opt() -> argparse.ArgumentParser:
    """Create the command-line parser used by ``mazy``.

    The CLI accepts one or more positional tokens and classifies each token as
    an obsid, AGASC ID, load name, or date. It also supports mutually
    exclusive content location and content type switches.

    Examples
    --------
    mazy 12312 MAR2422A 2024:001 --starcheck
    mazy 12312 --agasc --occweb

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for the ``mazy`` command.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Resolve positional inputs as obsid, AGASC ID, load name, and/or\n date,"
            "then open the selected content page. Note that a date must be provided in "
            "a string format (float CXC seconds are not accepted)."
        ),
        epilog=(
            "Examples:\n"
            "  mazy MAR2422A --starcheck\n"
            "  mazy 12312 --mica\n"
            "  mazy 2024:001 --cent --local  # abbreviations OK"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "args", nargs="+", help="Positional arguments: date, obsid, load_name, AGASC ID"
    )

    content_location = parser.add_argument_group(
        "Content location (choose one, default=cxc/icxc)"
    )
    content_location_group = content_location.add_mutually_exclusive_group()
    content_location_group.add_argument(
        "--local", action="store_true", help="Use local content"
    )
    content_location_group.add_argument(
        "--occweb", action="store_true", help="Use OCC web content"
    )

    content_type = parser.add_argument_group("Content type (choose one)")
    mode_group = content_type.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--starcheck", action="store_true", help="Open the Starcheck page"
    )
    mode_group.add_argument("--mica", action="store_true", help="Open the MICA page")
    mode_group.add_argument("--agasc", action="store_true", help="Open the AGASC page")
    mode_group.add_argument(
        "--star-history", action="store_true", help="Open the Star History page"
    )
    mode_group.add_argument(
        "--centroid-dashboard",
        action="store_true",
        help="Open the Centroid Dashboard page",
    )

    parser.add_argument("--version", action="version", version=__version__)

    return parser


def as_date(arg: str) -> CxoTime | None:
    """Parse an argument as a Chandra date/time.

    Parameters
    ----------
    arg : str
        Input token to parse.

    Returns
    -------
    CxoTime or None
        Parsed ``CxoTime`` if valid, otherwise ``None``.
    """
    try:
        out = CxoTime(arg)
    except Exception:
        out = None
    return out


def as_load_name(arg: str) -> str | None:
    """Parse an argument as a load name.

    Parameters
    ----------
    arg : str
        Input token to parse.

    Returns
    -------
    str or None
        Original argument if it is a valid load name, otherwise ``None``.
    """
    try:
        parse_cm.paths.parse_load_name(arg)
        out = arg
    except Exception:
        out = None
    return out


def as_agasc_id(arg: str) -> int | None:
    """Parse an argument as an AGASC ID.

    It must be an integer > 65536.
    """
    try:
        out = int(arg)
        if out <= 65536:
            out = None
    except Exception:
        out = None
    return out


def as_obsid(arg: str) -> int | None:
    """Parse an argument as an observation ID.

    Parameters
    ----------
    arg : str
        Input token to parse.

    Returns
    -------
    int or None
        Integer value if in the inclusive range [0, 65535], otherwise ``None``.
    """
    try:
        out = int(arg)
        if not (0 <= out <= 65535):
            out = None
    except Exception:
        out = None
    return out


def get_arg_values(opt: argparse.Namespace) -> Args:
    """Match free-form CLI arguments to known value types.

    Parameters
    ----------
    opt : argparse.Namespace
        Parsed command-line options with positional ``args``.

    Returns
    -------
    Args
        Dataclass containing ``date``, ``obsid``, ``agasc_id``, and
        ``load_name``.

    Raises
    ------
    ValueError
        Raised when any positional argument cannot be matched.
    """
    args = Args()
    matchers: list[tuple[str, Callable[[str], CxoTime | int | str | None]]] = [
        ("obsid", as_obsid),
        ("agasc_id", as_agasc_id),
        ("load_name", as_load_name),
        ("date", as_date),
    ]

    # For each token, assign it to the first unset field whose parser accepts it.
    for arg in opt.args:
        match = False
        for key, matcher in matchers:
            if getattr(args, key) is None:
                parsed = matcher(arg)
                if parsed is not None:
                    setattr(args, key, parsed)
                    match = True
                    break
        if not match:
            raise ValueError(f"Unrecognized argument: {arg}")

    return args


def open_starcheck_page(
    opt: argparse.Namespace,
    args: Args,
) -> None:
    """
    Open the Starcheck page for the given arguments.
    """


def main() -> None:
    """Run the command-line interface entry point."""
    parser = get_opt()
    opt = parser.parse_args()
    args = get_arg_values(opt)

    print(opt)
    print(args)

    if opt.starcheck:
        open_starcheck_page(opt, args)


if __name__ == "__main__":
    main()
