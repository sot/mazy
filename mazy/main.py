import argparse
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable

import astropy.units as u
import kadi.commands as kc
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

    def has_exact_args(self, *args: tuple[str, ...]):
        """True if each of `args` attributes is not None and others are None"""
        has = all(getattr(self, arg) is not None for arg in args)
        not_has_rest = all(
            getattr(self, field) is None
            for field in set(self.__dataclass_fields__) - set(args)
        )
        return has and not_has_rest


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
    parser.add_argument(
        "--archive-only",
        action="store_true",
        help="Use archive-only (flight scenario) for kadi commands",
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help="Print the URL that would be opened instead of opening it in a browser",
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
    mode_group = content_type.add_mutually_exclusive_group(required=True)
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

    # if opt.starcheck:
    #     # date
    #     # obsid
    #     # obsid, load_name
    #     # load_name
    #     # NOT agasc_id
    #     check_args(
    #         args, [("date",), ("obsid",), ("obsid", "load_name"), ("load_name",)]
    #     )

    return args


def check_args(args: Args, allowed_combinations: list[tuple[str, ...]]) -> None:
    """Check that the given ``Args`` instance matches one of the allowed combinations.

    Parameters
    ----------
    args : Args
        Parsed arguments to check.
    allowed_combinations : list of tuple of str
        List of allowed argument combinations. Each tuple contains the names
        of the fields that must be set for that combination to be valid.

    Raises
    ------
    ValueError
        Raised if the arguments do not match any of the allowed combinations.
    """
    for combo in allowed_combinations:
        if args.has_exact_args(*combo):
            return

    allowed = "\n".join(f"  - {', '.join(combo)}" for combo in allowed_combinations)
    raise ValueError(
        f"Arguments {args} do not match any allowed combination:\n{allowed}"
    )


class NotUniqueObservationError(Exception):
    """Raised when the arguments do not specify a unique observation."""


def get_observation(args: Args, *, archive_only=False) -> dict[str, Any]:
    """Get a unique observation matching the given arguments."""
    if args.date is None and args.obsid is None and args.load_name is None:
        raise ValueError("need to specify at least one of date, obsid, or load_name")

    kwargs = {}
    if archive_only:
        kwargs["scenario"] = "flight"
    if args.date:
        kwargs["start"] = args.date
        kwargs["stop"] = args.date + 15 * u.s  # cover gap from NMAN to manvr start
        if args.date < CxoTime("-30d"):
            kwargs["scenario"] = "flight"  # update to "archive-only" when possible
    if args.obsid:
        kwargs["obsid_sched"] = args.obsid
    if args.load_name:
        kwargs["source"] = args.load_name

    obss = kc.get_observations(**kwargs)
    if len(obss) == 1:
        return obss[0]
    else:
        raise NotUniqueObservationError(
            f"found {len(obss)} observations (instead of one) for arguments {args}"
        )


def get_starcheck_url(
    opt: argparse.Namespace,
    args: Args,
) -> str:
    """
    Get the URL for the Starcheck page for the given arguments.
    """
    if args.has_exact_args("load_name"):
        load_name = args.load_name
        obsid = None
    else:
        obs = get_observation(args, archive_only=opt.archive_only)
        load_name = obs["source"]
        obsid = obs.get("obsid_sched", obs["obsid"])

    server = "occweb" if opt.occweb else "icxc"
    url = parse_cm.paths.load_url_from_load_name(load_name, server=server)
    url += "/starcheck.html"
    if obsid is not None:
        url += f"#obsid{obsid}"
    return url


def get_mica_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the MICA page for the given arguments."""
    raise NotImplementedError("MICA URL generation is not implemented yet")


def get_agasc_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the AGASC page for the given arguments."""
    raise NotImplementedError("AGASC URL generation is not implemented yet")


def get_star_history_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the Star History page for the given arguments."""
    raise NotImplementedError("Star History URL generation is not implemented yet")


def get_centroid_dashboard_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the Centroid Dashboard page for the given arguments."""
    raise NotImplementedError(
        "Centroid Dashboard URL generation is not implemented yet"
    )


def main() -> None:
    """Run the command-line interface entry point."""
    parser = get_opt()
    opt = parser.parse_args()
    args = get_arg_values(opt)

    if opt.starcheck:
        func = get_starcheck_url
    elif opt.mica:
        func = get_mica_url
    elif opt.agasc:
        func = get_agasc_url
    elif opt.star_history:
        func = get_star_history_url
    elif opt.centroid_dashboard:
        func = get_centroid_dashboard_url
    else:
        raise ValueError("Expected exactly one content type option")

    url = func(opt, args)

    if opt.print_url:
        print(url)
    else:
        webbrowser.open(url)

if __name__ == "__main__":
    main()
