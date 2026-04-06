import argparse
import os
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable

import astropy.units as u
import kadi.commands as kc
import parse_cm.paths
from cxotime import CxoTime

from mazy import __version__

SKA = os.environ["SKA"]


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

    The CLI accepts an initial ``resource`` positional argument, followed by
    optional positional tokens that are classified as obsid, AGASC ID, load
    name, or date. It also supports mutually exclusive content location
    switches.

    Examples
    --------
    mazy starcheck 43474 APR2924A 2024:125:06:22:32 --print-url
    mazy mica 43474 --occweb
    mazy centroid_dashboard 2024:125:06:22:32 --local

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for the ``mazy`` command.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Resolve positional inputs as obsid, AGASC ID, load name, and/or\n date,"
            "then open the selected content resource. Note that a date must be provided in "
            "a string format (float CXC seconds are not accepted)."
        ),
        epilog=(
            "Examples:\n"
            "  mazy starcheck APR2924A --occweb\n"
            "  mazy mica 43474\n"
            "  mazy centroid_dashboard 2024:125:06:22:32 --local\n"
            "  mazy star_history 701368208\n"
            "  mazy agasc 701368208\n"
            "  mazy chaser 43474\n"
            "  mazy fot-daily-plots 2024:125:06:22:32"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "resource",
        help=(
            "Content resource name: starcheck, mica, agasc, star_history, "
            "centroid_dashboard, chaser, fot-daily-plots"
        ),
    )
    parser.add_argument(
        "args",
        nargs="*",
        help="Positional arguments: date, obsid, load_name, AGASC ID",
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


def get_starcheck_url(opt: argparse.Namespace, args: Args) -> str:
    """
    Get the URL for the Starcheck resource for the given arguments.
    """
    if args.has_exact_args("load_name"):
        load_name = args.load_name
        obsid = None
    else:
        obs = get_observation(args, archive_only=opt.archive_only)
        load_name = obs["source"]
        obsid = obs.get("obsid_sched", obs["obsid"])

    if opt.occweb:
        server = "occweb"
    elif opt.local:
        # Note: using file:///path_to_starcheck/starcheck.html#obsid<obsid> does not
        # work. The #obsid<obsid> bit gets stripped on Mac because the application
        # is looking for a pure file name (according to AI).
        raise ValueError("local server not allowed for starcheck")
    else:
        server = "icxc"

    url = parse_cm.paths.load_url_from_load_name(load_name, server=server)
    url += "/starcheck.html"
    if obsid is not None:
        url += f"#obsid{obsid}"

    return url


def get_mica_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the MICA resource for the given arguments.

    Like:
    https://kadi.cfa.harvard.edu/mica/?obsid_or_date=43474&load_name=APR2924A
    """
    if args.obsid is None or args.load_name is None:
        obs = get_observation(args, archive_only=opt.archive_only)
        load_name = obs["source"]
        obsid = obs.get("obsid_sched", obs["obsid"])
    else:
        load_name = args.load_name
        obsid = args.obsid

    return (
        "https://kadi.cfa.harvard.edu/mica/"
        f"?obsid_or_date={obsid}&load_name={load_name}"
    )


def get_agasc_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the AGASC page for the AGASC ID.

    Like:
    https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/070/701368208/index.html
    """
    if opt.local or opt.occweb:
        raise ValueError("AGASC page is not available on local or OCCweb")

    if args.agasc_id is None:
        raise ValueError("agasc_id must be specified to generate an AGASC URL")
    prefix = f"{args.agasc_id:010d}"[:3]
    return (
        "https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/"
        f"{prefix}/{args.agasc_id}/index.html"
    )


def get_star_history_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the Star History page for AGASC ID.

    Like:
    https://kadi.cfa.harvard.edu/star_hist/?agasc_id=701368208
    """
    if opt.local or opt.occweb:
        raise ValueError("AGASC page is not available on local or OCCweb")

    if args.agasc_id is None:
        raise ValueError("agasc_id must be specified to generate a Star History URL")
    return f"https://kadi.cfa.harvard.edu/star_hist/?agasc_id={args.agasc_id}"


def get_centroid_dashboard_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the Centroid Dashboard resource for the given arguments.

    Like:
    https://icxc.cfa.harvard.edu/aspect/centroid_reports//2025/MAR1025B/28365/index.html
    """
    if args.obsid is None or args.load_name is None:
        obs = get_observation(args, archive_only=opt.archive_only)
        load_name = obs["source"]
        obsid = obs.get("obsid_sched", obs["obsid"])
    else:
        load_name = args.load_name
        obsid = args.obsid

    *_, load_year = parse_cm.parse_load_name(load_name)

    if opt.occweb:
        raise ValueError("no centroid dashboard on OCCweb")

    if opt.local:
        out = (
            f"file://{SKA}/data/centroid_dashboard/centroid_reports/"
            f"{load_year}/{load_name}/{obsid}/index.html"
        )
    else:
        out = (
            "https://icxc.cfa.harvard.edu/aspect/centroid_reports/"
            f"{load_year}/{load_name}/{obsid}/index.html"
        )
    return out


def get_chaser_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the Chaser resource for the given arguments.

    Like:
    https://cda.cfa.harvard.edu/chaser/startViewer.do?menuItem=details&obsid=31041
    """
    if opt.local or opt.occweb:
        raise ValueError("Chaser is not available on local or OCCweb")

    if args.obsid is None:
        obs = get_observation(args, archive_only=opt.archive_only)
        obsid = obs.get("obsid_sched", obs["obsid"])
    else:
        obsid = args.obsid

    return (
        "https://cda.cfa.harvard.edu/chaser/startViewer.do"
        f"?menuItem=details&obsid={obsid}"
    )


def get_fot_daily_plots_url(opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for the FOT daily plots resource for the given arguments.

    Like:
    https://occweb.cfa.harvard.edu/occweb/FOT/engineering/reports/dailies/2024/MAY/may04_125/
    """
    if opt.local:
        raise ValueError("fot-daily-plots is not available on local")

    if args.obsid is not None:
        obs = get_observation(args, archive_only=opt.archive_only)
        date = CxoTime(obs["obs_start"])
    elif args.date is not None:
        date = CxoTime(args.date)
    else:
        raise ValueError("fot-daily-plots requires either obsid or date")

    dt = date.datetime
    year = dt.year
    month_upper = dt.strftime("%b").upper()
    month_lower = dt.strftime("%b").lower()
    day = dt.day
    doy = dt.timetuple().tm_yday

    return (
        "https://occweb.cfa.harvard.edu/occweb/FOT/engineering/reports/dailies/"
        f"{year}/{month_upper}/{month_lower}{day:02d}_{doy:03d}/"
    )


def get_resource_url(resource: str, opt: argparse.Namespace, args: Args) -> str:
    """Get the URL for a content resource for the given arguments.

    TODO:
    - Support test loads:
        - On HEAD disk /data/mpcrit1/mplogs/OFLS_testing/2026/JAN2626
        - URL https://icxc.harvard.edu/mp/mplogs/OFLS_testing/2026/JAN2626/scheduled_t/JAN2626T.html
        - Where do FOT test loads live? Any network-visible location?
    """
    resource_funcs = {
        "starcheck": get_starcheck_url,
        "mica": get_mica_url,
        "agasc": get_agasc_url,
        "star_history": get_star_history_url,
        "centroid_dashboard": get_centroid_dashboard_url,
        "chaser": get_chaser_url,
        "fot-daily-plots": get_fot_daily_plots_url,
        "fot_daily_plots": get_fot_daily_plots_url,
    }

    try:
        func = resource_funcs[resource]
    except KeyError as err:
        raise ValueError(f"unknown resource '{resource}'") from err
    return func(opt, args)


def main() -> None:
    """Run the command-line interface entry point."""
    parser = get_opt()
    opt = parser.parse_args()
    args = get_arg_values(opt)
    url = get_resource_url(opt.resource, opt, args)

    if opt.print_url:
        print(url)
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
