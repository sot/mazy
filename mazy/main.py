import argparse
import dataclasses
import os
import re
import webbrowser
from typing import Any

import astropy.units as u
import kadi.commands as kc
import parse_cm.paths
from cxotime import CxoTime

from mazy import __version__

SKA = os.environ["SKA"]


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
    mazy centroid-dashboard 2024:125:06:22:32 --local

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
            "  mazy centroid-dashboard 2024:125:06:22:32 --local\n"
            "  mazy star-history 701368208\n"
            "  mazy agasc 701368208\n"
            "  mazy chaser 43474\n"
            "  mazy fot-daily-plots 2024:125:06:22:32"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "resource",
        help=(
            "Content resource name: starcheck, mica, agasc, star-history, "
            "centroid-dashboard, chaser, fot-daily-plots"
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


class ParserBase:
    """Base class for argument parsers."""

    name: str | None = None
    subclasses: dict[str, type["ParserBase"]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        base_name = cls.__name__[len("Parser") :]
        step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", base_name)
        cls.name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1).lower()
        ParserBase.subclasses[cls.name] = cls

    @staticmethod
    def parse(arg: str):
        """Parse ``arg`` and return parsed value or ``None``."""
        raise NotImplementedError


class ParserDate(ParserBase):
    """Parser for Chandra date/time values."""

    @staticmethod
    def parse(arg: str) -> CxoTime | None:
        try:
            out = CxoTime(arg)
        except Exception:
            out = None
        return out


class ParserLoadName(ParserBase):
    """Parser for load names."""

    @staticmethod
    def parse(arg: str) -> str | None:
        try:
            parse_cm.paths.parse_load_name(arg)
            out = arg
        except Exception:
            out = None
        return out


class ParserAgascId(ParserBase):
    """Parser for AGASC ID values."""

    @staticmethod
    def parse(arg: str) -> int | None:
        try:
            out = int(arg)
            if out <= 65536:
                out = None
        except Exception:
            out = None
        return out


class ParserObsid(ParserBase):
    """Parser for OBSID values."""

    @staticmethod
    def parse(arg: str) -> int | None:
        try:
            out = int(arg)
            if not (0 <= out <= 65535):
                out = None
        except Exception:
            out = None
        return out


class ResourceBase:
    """Base class for Resources

    Attributes
    ----------
    opt : argparse.ArgumentParser
        Input options
    """

    name: str | None = None
    subclasses: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        base_name = cls.__name__[len("Resource") :]
        step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", base_name)
        cls.name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", step1).lower()
        ResourceBase.subclasses[cls.name] = cls

    def has_exact_args(self, *args: tuple[str, ...]):
        """True if each of `args` attributes is not None and others are None"""
        has = all(getattr(self, arg) is not None for arg in args)
        not_has_rest = all(
            getattr(self, field) is None
            for field in set(self.__dataclass_fields__) - set(args)
        )
        return has and not_has_rest

    def __post_init__(self):
        field_names = [f.name for f in dataclasses.fields(self)]
        parsers = [
            (name, parser_cls.parse)
            for name, parser_cls in ParserBase.subclasses.items()
            if name in field_names
        ]

        for value in self.opt.args:
            for parser_name, parser_func in parsers:
                if getattr(self, parser_name) is not None:
                    continue
                if (value_parsed := parser_func(value)) is not None:
                    setattr(self, parser_name, value_parsed)
                    break
            else:
                raise ValueError(
                    f"{value} is not an allowed input for {self.name} resource"
                )

    def get_url(self) -> str:
        """Get URL for the resource."""
        raise NotImplementedError


@dataclasses.dataclass
class ResourceStarcheck(ResourceBase):
    opt: argparse.Namespace | None = None
    obsid: int | None = None
    load_name: str | None = None
    date: CxoTime | None = None

    def get_url(self) -> str:
        """Get the URL for the Starcheck resource for the given arguments."""
        if self.has_exact_args("load_name"):
            load_name = self.load_name
            obsid = None
        else:
            obs = get_observation(self, archive_only=self.opt.archive_only)
            load_name = obs["source"]
            obsid = obs.get("obsid_sched", obs["obsid"])

        if self.opt.occweb:
            server = "occweb"
        elif self.opt.local:
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


class NotUniqueObservationError(Exception):
    """Raised when the arguments do not specify a unique observation."""


def get_observation(resource: ResourceBase, *, archive_only=False) -> dict[str, Any]:
    """Get a unique observation matching the given arguments."""
    date = getattr(resource, "date", None)
    obsid = getattr(resource, "obsid", None)
    load_name = getattr(resource, "load_name", None)

    if date is None and obsid is None and load_name is None:
        raise ValueError("need to specify at least one of date, obsid, or load_name")

    kwargs = {}
    if archive_only:
        kwargs["scenario"] = "flight"
    if date:
        kwargs["start"] = date
        kwargs["stop"] = date + 15 * u.s  # cover gap from NMAN to manvr start
        if date < CxoTime("-30d"):
            kwargs["scenario"] = "flight"  # update to "archive-only" when possible
    if obsid:
        kwargs["obsid_sched"] = obsid
    if load_name:
        kwargs["source"] = load_name

    obss = kc.get_observations(**kwargs)
    if len(obss) == 1:
        return obss[0]
    else:
        raise NotUniqueObservationError(
            "found "
            f"{len(obss)} observations (instead of one) for resource {resource.name}"
        )


@dataclasses.dataclass
class ResourceMica(ResourceBase):
    """MICA resource URL builder.

    Allowed args: date, obsid, load_name
    """

    opt: argparse.Namespace | None = None
    date: CxoTime | None = None
    obsid: int | None = None
    load_name: str | None = None

    def get_url(self) -> str:
        """Get the URL for the MICA resource for the given arguments."""
        if self.obsid is None or self.load_name is None:
            obs = get_observation(self, archive_only=self.opt.archive_only)
            load_name = obs["source"]
            obsid = obs.get("obsid_sched", obs["obsid"])
        else:
            load_name = self.load_name
            obsid = self.obsid

        return (
            "https://kadi.cfa.harvard.edu/mica/"
            f"?obsid_or_date={obsid}&load_name={load_name}"
        )


@dataclasses.dataclass
class ResourceAgasc(ResourceBase):
    """AGASC resource URL builder.

    Allowed args: agasc_id
    """

    opt: argparse.Namespace | None = None
    agasc_id: int | None = None

    def get_url(self) -> str:
        """Get the URL for the AGASC page for the AGASC ID."""
        if self.opt.local or self.opt.occweb:
            raise ValueError("AGASC page is not available on local or OCCweb")

        if self.agasc_id is None:
            raise ValueError("agasc_id must be specified to generate an AGASC URL")
        prefix = f"{self.agasc_id:010d}"[:3]
        return (
            "https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/"
            f"{prefix}/{self.agasc_id}/index.html"
        )


@dataclasses.dataclass
class ResourceStarHistory(ResourceBase):
    """Star History resource URL builder.

    Allowed args: agasc_id
    """

    opt: argparse.Namespace | None = None
    agasc_id: int | None = None

    def get_url(self) -> str:
        """Get the URL for the Star History resource for AGASC ID."""
        if self.opt.local or self.opt.occweb:
            raise ValueError("AGASC page is not available on local or OCCweb")

        if self.agasc_id is None:
            raise ValueError("agasc_id must be specified to generate a Star History URL")
        return f"https://kadi.cfa.harvard.edu/star_hist/?agasc_id={self.agasc_id}"


@dataclasses.dataclass
class ResourceCentroidDashboard(ResourceBase):
    """Centroid Dashboard resource URL builder.

    Allowed args: date, obsid, load_name
    """

    opt: argparse.Namespace | None = None
    date: CxoTime | None = None
    obsid: int | None = None
    load_name: str | None = None

    def get_url(self) -> str:
        """Get the URL for the Centroid Dashboard resource for the given arguments."""
        if self.obsid is None or self.load_name is None:
            obs = get_observation(self, archive_only=self.opt.archive_only)
            load_name = obs["source"]
            obsid = obs.get("obsid_sched", obs["obsid"])
        else:
            load_name = self.load_name
            obsid = self.obsid

        *_, load_year = parse_cm.parse_load_name(load_name)

        if self.opt.occweb:
            raise ValueError("no centroid dashboard on OCCweb")

        if self.opt.local:
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


@dataclasses.dataclass
class ResourceChaser(ResourceBase):
    """Chaser resource URL builder.

    Allowed args: obsid, date, load_name
    """

    opt: argparse.Namespace | None = None
    obsid: int | None = None
    date: CxoTime | None = None
    load_name: str | None = None

    def get_url(self) -> str:
        """Get the URL for the Chaser resource for the given arguments."""
        if self.opt.local or self.opt.occweb:
            raise ValueError("Chaser is not available on local or OCCweb")

        if self.obsid is None:
            obs = get_observation(self, archive_only=self.opt.archive_only)
            obsid = obs.get("obsid_sched", obs["obsid"])
        else:
            obsid = self.obsid

        return (
            "https://cda.cfa.harvard.edu/chaser/startViewer.do"
            f"?menuItem=details&obsid={obsid}"
        )


@dataclasses.dataclass
class ResourceFotDailyPlots(ResourceBase):
    """FOT daily plots resource URL builder.

    Allowed args: date, obsid, load_name
    """

    opt: argparse.Namespace | None = None
    date: CxoTime | None = None
    obsid: int | None = None
    load_name: str | None = None

    def get_url(self) -> str:
        """Get the URL for the FOT daily plots resource for the given arguments."""
        if self.opt.local:
            raise ValueError("fot-daily-plots is not available on local")

        if self.obsid is not None:
            obs = get_observation(self, archive_only=self.opt.archive_only)
            date = CxoTime(obs["obs_start"])
        elif self.date is not None:
            date = CxoTime(self.date)
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


def get_resource_url(resource: str, opt: argparse.Namespace) -> str:
    """Get the URL for a content resource for the given arguments.

    TODO:
    - Support test loads:
        - On HEAD disk /data/mpcrit1/mplogs/OFLS_testing/2026/JAN2626
        - URL https://icxc.harvard.edu/mp/mplogs/OFLS_testing/2026/JAN2626/scheduled_t/JAN2626T.html
        - Where do FOT test loads live? Any network-visible location?
    """
    try:
        resource_cls = ResourceBase.subclasses[resource]
    except KeyError as err:
        raise ValueError(f"unknown resource '{resource}'") from err
    return resource_cls(opt=opt).get_url()


def main() -> None:
    """Run the command-line interface entry point."""
    parser = get_opt()
    opt = parser.parse_args()
    url = get_resource_url(opt.resource, opt)

    if opt.print_url:
        print(url)
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
