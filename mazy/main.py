import argparse
import dataclasses
import os
import re
import webbrowser
from typing import Any, ClassVar

import astropy.units as u
import kadi.commands as kc
import parse_cm.paths
from cxotime import CxoTime
from kadi import occweb

from mazy import __version__

SKA = os.environ["SKA"]

# TODO:
# - Support test loads:
#     - On HEAD disk /data/mpcrit1/mplogs/OFLS_testing/2026/JAN2626
#     - URL https://icxc.harvard.edu/mp/mplogs/OFLS_testing/2026/JAN2626/scheduled_t/JAN2626T.html
#     - Where do FOT test loads live? Any network-visible location?


def get_opt_parser() -> argparse.ArgumentParser:
    """Create the command-line parser used by ``mazy``.

    The CLI accepts an initial ``resource`` positional argument, followed by
    optional positional tokens that are classified as obsid, AGASC ID, load
    name, or date. It also supports mutually exclusive content location
    switches.

    The ``resource`` positional argument can be shortened to any unique abbreviation.

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
    resource_lines = []
    for resource_name in sorted(ResourceBase.subclasses):
        resource_cls = ResourceBase.subclasses[resource_name]
        doc = (resource_cls.__doc__ or "").strip().splitlines()
        summary = doc[0] if doc else ""
        resource_lines.append(f"- {resource_name}: {summary}")

    parser = argparse.ArgumentParser(
        description=(
            "Find a Chandra operations resource by observation, obsid, load_name, date, "
            "or AGASC ID as appropriate.\n\n"
            "Available resources:\n"
            + "\n".join(resource_lines)
        ),
        epilog=(
            "Examples:\n"
            "  mazy dot 43474\n"
            "  mazy dot APR2924A\n"
            "  mazy backstop 2024:125:06:22:32\n"
            "  mazy fot-daily-plots 2024:125:06:22:32\n"
            "  mazy fot 43474  # abbreviation\n"
            "  mazy maneuver 2025:001\n"
            "  mazy chaser 8008\n"
            "  mazy starcheck APR2924A --occweb\n"
            "  mazy mica 43474\n"
            "  mazy centroid-dashboard 2024:125:06:22:32 --local\n"
            "  mazy star-history 701368208\n"
            "  mazy agasc 701368208\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resources = ", ".join(ResourceBase.subclasses)
    positional_args = ", ".join(ParserBase.subclasses)
    parser.add_argument(
        "resource",
        help=f"Content resource name: {resources}",
    )
    parser.add_argument(
        "args",
        nargs="*",
        help=f"Positional arguments: {positional_args}",
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
        "Content location (choose one to override resource default locations)"
    )
    content_location_group = content_location.add_mutually_exclusive_group()
    content_location_group.add_argument(
        "--local", action="store_true", help="Use local content"
    )
    content_location_group.add_argument(
        "--occweb", action="store_true", help="Use OCC web content"
    )
    content_location_group.add_argument(
        "--cxc", action="store_true", help="Use CXC web content"
    )

    parser.add_argument("--version", action="version", version=__version__)

    return parser


def get_observation(
    *,
    date: CxoTime | None = None,
    obsid: int | None = None,
    load_name: str | None = None,
    archive_only: bool = False,
) -> dict[str, Any]:
    """Get a unique observation matching the given arguments."""
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
            f"{len(obss)} observations (instead of one) "
            f"for date={date}, obsid={obsid}, load_name={load_name}"
        )


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


@dataclasses.dataclass
class ResourceBase:
    """Base class for Resources

    Attributes
    ----------
    opt : dict[str, Any]
        Input options as a plain dictionary.
    args : list[str]
        Positional arguments to parse.
    """

    name: ClassVar[str | None] = None
    subclasses: ClassVar[dict[str, type["ResourceBase"]]] = {}
    locations: tuple[str, ...] = ()
    opt: dict[str, Any] = dataclasses.field(default_factory=dict)
    args: list[str] = dataclasses.field(default_factory=list)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.__name__.endswith("Base"):
            base_name = cls.__name__[len("Resource") :]
            step1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1-\2", base_name)
            cls.name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", step1).lower()
            ResourceBase.subclasses[cls.name] = cls

    def __post_init__(self):
        self.check_locations()
        field_names = [f.name for f in dataclasses.fields(self)]
        parsers = [
            (name, parser_cls.parse)
            for name, parser_cls in ParserBase.subclasses.items()
            if name in field_names
        ]

        for value in self.args:
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

    def check_locations(self) -> None:
        """Validate requested location flags against ``self.locations``."""
        for location in ("occweb", "cxc", "local"):
            if self.opt.get(location) and location not in self.locations:
                raise ValueError(f"{self.name} resource is not available on {location}")

    def get_url(self) -> str:
        """Get URL for the resource."""
        raise NotImplementedError


@dataclasses.dataclass
class ResourceObsidBase(ResourceBase):
    obsid: int | None = None
    load_name: str | None = None
    date: CxoTime | None = None

    def resolve_args_as_load_name_obsid(self) -> None:
        """Set self load_name and obsid for the given arguments."""
        obs = get_observation(
            date=self.date,
            obsid=self.obsid,
            load_name=self.load_name,
            archive_only=self.opt.get("archive_only"),
        )
        self.load_name = obs["source"]
        self.date = CxoTime(obs["obs_start"])
        self.obsid = obs.get("obsid_sched", obs["obsid"])


@dataclasses.dataclass
class ResourceStarcheck(ResourceObsidBase):
    """Starcheck ACA review page by observation or load name"""

    locations: tuple[str, ...] = ("occweb", "cxc")

    def get_url(self) -> str:
        """Get the URL for the Starcheck resource for the given arguments."""
        load_name_only = self.load_name and self.obsid is None and self.date is None
        if not load_name_only:
            self.resolve_args_as_load_name_obsid()

        server = "icxc" if self.opt.get("cxc") else "occweb"
        url = parse_cm.paths.load_url_from_load_name(self.load_name, server=server)
        url += "/starcheck.html"
        if not load_name_only:
            url += f"#obsid{self.obsid}"

        return url


@dataclasses.dataclass
class ResourceDOT(ResourceStarcheck):
    """DOT file by observation or load name"""

    def get_url(self) -> str:
        """Get URL for DOT file for the given arguments."""
        url = super().get_url()
        file_link = f"md{self.load_name}.dot.html#{self.obsid}"
        url = re.sub(r"starcheck\.html.*$", "starcheck/" + file_link, url)
        return url


@dataclasses.dataclass
class ResourceTLR(ResourceStarcheck):
    """Timeline Report file by observation or load name"""

    def get_url(self) -> str:
        """Get URL for timeline report file for the given arguments."""
        url = super().get_url()
        starcheck_html = occweb.get_occweb_page(url)
        # look for something like '"starcheck/CR\d+_\d+.tlr.html#\d+"'
        match = re.search(r"starcheck/CR\d+_\d+\.tlr\.html#", starcheck_html)
        if not match:
            raise ValueError(f"Backstop file not found in Starcheck page: {url}")
        # Replace starcheck.html.*$ in `url` with the matched backstop file
        file_link = match.group(0) + str(self.obsid)
        url = re.sub(r"starcheck\.html.*$", file_link, url)
        return url


@dataclasses.dataclass
class ResourceBackstop(ResourceStarcheck):
    """Backstop file by observation or load name"""

    def get_url(self) -> str:
        """Get URL for backstop file for the given arguments."""
        url = super().get_url()
        starcheck_html = occweb.get_occweb_page(url)
        # look for something like '"starcheck/CR\d+_\d+.backstop.html#\d+"'
        match = re.search(r"starcheck/CR\d+_\d+\.backstop\.html#", starcheck_html)
        if not match:
            raise ValueError(f"Backstop file not found in Starcheck page: {url}")
        # Replace starcheck.html.*$ in `url` with the matched backstop file
        backstop_file_link = match.group(0) + str(self.obsid)
        url = re.sub(r"starcheck\.html.*$", backstop_file_link, url)
        return url


@dataclasses.dataclass
class ResourceORList(ResourceStarcheck):
    """OR list file by observation or load name"""

    def get_url(self) -> str:
        """Get URL for OR List file for the given arguments."""
        # starcheck/DEC2925_B.or.html#31287
        url = super().get_url()
        or_list_link = (
            self.load_name[:-1] + "_" + self.load_name[-1] + f".or.html#{self.obsid}"
        )
        url = re.sub(r"starcheck\.html.*$", "starcheck/" + or_list_link, url)
        return url


@dataclasses.dataclass
class ResourceManeuverSummary(ResourceStarcheck):
    """Maneuver summary file by observation or load name"""

    def get_url(self) -> str:
        """Get URL for maneuver summary file for the given arguments."""
        # starcheck/mmDEC2324B.sum.html#28365
        url = super().get_url()
        mm_sum_link = f"mm{self.load_name}.sum.html#{self.obsid}"
        url = re.sub(r"starcheck\.html.*$", "starcheck/" + mm_sum_link, url)
        return url


class NotUniqueObservationError(Exception):
    """Raised when the arguments do not specify a unique observation."""


@dataclasses.dataclass
class ResourceMica(ResourceObsidBase):
    """Mica aspect page by observation"""

    locations: tuple[str, ...] = ("cxc",)

    def get_url(self) -> str:
        """Get the URL for the MICA resource for the given arguments."""
        if self.obsid is None or self.load_name is None:
            self.resolve_args_as_load_name_obsid()

        return (
            "https://kadi.cfa.harvard.edu/mica/"
            f"?obsid_or_date={self.obsid}&load_name={self.load_name}"
        )


@dataclasses.dataclass
class ResourceAgasc(ResourceBase):
    """AGASC summary for star by AGASC ID"""

    locations: tuple[str, ...] = ("cxc",)
    agasc_id: int | None = None

    def get_url(self) -> str:
        """Get the URL for the AGASC page for the AGASC ID."""
        if self.agasc_id is None:
            raise ValueError("agasc_id must be specified to generate an AGASC URL")
        prefix = f"{self.agasc_id:010d}"[:3]
        return (
            "https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/"
            f"{prefix}/{self.agasc_id}/index.html"
        )


@dataclasses.dataclass
class ResourceStarHistory(ResourceBase):
    """Star History by AGASC ID"""

    locations: tuple[str, ...] = ("cxc",)
    agasc_id: int | None = None

    def get_url(self) -> str:
        """Get the URL for the Star History page for AGASC ID."""
        if self.agasc_id is None:
            raise ValueError(
                "agasc_id must be specified to generate a Star History URL"
            )
        return f"https://kadi.cfa.harvard.edu/star_hist/?agasc_id={self.agasc_id}"


@dataclasses.dataclass
class ResourceCentroidDashboard(ResourceObsidBase):
    """Centroid Dashboard page by observation"""

    locations: tuple[str, ...] = ("cxc", "local")

    def get_url(self) -> str:
        """Get the URL for the Centroid Dashboard page for the given arguments."""
        if self.obsid is None or self.load_name is None:
            self.resolve_args_as_load_name_obsid()

        *_, load_year = parse_cm.parse_load_name(self.load_name)

        if self.opt.get("local"):
            out = (
                f"file://{SKA}/data/centroid_dashboard/centroid_reports/"
                f"{load_year}/{self.load_name}/{self.obsid}/index.html"
            )
        else:
            out = (
                "https://icxc.cfa.harvard.edu/aspect/centroid_reports/"
                f"{load_year}/{self.load_name}/{self.obsid}/index.html"
            )
        return out


@dataclasses.dataclass
class ResourceChaser(ResourceObsidBase):
    """Chaser page by observation"""

    locations: tuple[str, ...] = ("cxc",)

    def get_url(self) -> str:
        """Get the URL for the Chaser page for the given arguments."""
        if self.obsid is None:
            self.resolve_args_as_load_name_obsid()

        return (
            "https://cda.cfa.harvard.edu/chaser/startViewer.do"
            f"?menuItem=details&obsid={self.obsid}"
        )


@dataclasses.dataclass
class ResourceFotDailyPlots(ResourceObsidBase):
    """FOT daily plots page by observation or date"""

    locations: tuple[str, ...] = ("occweb",)

    def get_url(self) -> str:
        """Get the URL for the FOT daily plots page for the given arguments."""
        if self.date is not None:
            pass
        elif self.obsid is not None:
            self.resolve_args_as_load_name_obsid()
        else:
            raise ValueError("fot-daily-plots requires either obsid or date")

        dt = self.date.datetime
        year = dt.year
        month_upper = dt.strftime("%b").upper()
        month_lower = dt.strftime("%b").lower()
        day = dt.day
        doy = dt.timetuple().tm_yday

        return (
            "https://occweb.cfa.harvard.edu/occweb/FOT/engineering/reports/dailies/"
            f"{year}/{month_upper}/{month_lower}{day:02d}_{doy:03d}/"
        )


def main() -> None:
    """Run the command-line interface entry point."""
    parser = get_opt_parser()
    opt = parser.parse_args()
    resource = opt.resource
    opt_dict = vars(opt)

    # Allow for unique abbreviations of resources
    matching_resources = [
        name for name in ResourceBase.subclasses if name.startswith(resource)
    ]
    if len(matching_resources) == 1:
        opt_dict["resource"] = matching_resources[0]

    resource = opt_dict["resource"]

    try:
        resource_cls = ResourceBase.subclasses[resource]
    except KeyError:
        raise ValueError(
            f"unknown resource '{resource}', "
            f"available resources are: {list(ResourceBase.subclasses)}"
        ) from None

    url = resource_cls(args=opt.args, opt=opt_dict).get_url()

    if opt_dict.get("print_url"):
        print(url)
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
