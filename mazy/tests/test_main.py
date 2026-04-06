import pytest

from mazy import main as mm


def make_opt(**overrides):
    opt = {
        "resource": "",
        "args": [],
        "archive_only": False,
        "print_url": False,
        "local": False,
        "occweb": False,
        "cxc": False,
    }
    opt.update(overrides)
    return opt


@pytest.mark.parametrize(
    "resource_cls, allowed_locations",
    [
        (mm.ResourceStarcheck, ("occweb", "cxc")),
        (mm.ResourceMica, ("cxc",)),
        (mm.ResourceAgasc, ("cxc",)),
        (mm.ResourceStarHistory, ("cxc",)),
        (mm.ResourceCentroidDashboard, ("cxc", "local")),
        (mm.ResourceChaser, ("cxc",)),
        (mm.ResourceFotDailyPlots, ("occweb",)),
    ],
)
def test_resource_locations_attr(resource_cls, allowed_locations):
    assert resource_cls.locations == allowed_locations


@pytest.mark.parametrize(
    "resource_cls,args,location",
    [
        (mm.ResourceStarcheck, ["2025:001"], "local"),
        (mm.ResourceMica, ["43474", "APR2924A"], "occweb"),
        (mm.ResourceAgasc, ["701368208"], "occweb"),
        (mm.ResourceStarHistory, ["701368208"], "local"),
        (mm.ResourceCentroidDashboard, ["43474", "APR2924A"], "occweb"),
        (mm.ResourceChaser, ["43474"], "occweb"),
        (mm.ResourceFotDailyPlots, ["2024:125:06:22:32"], "local"),
    ],
)
def test_resource_disallowed_location_raises(resource_cls, args, location):
    with pytest.raises(ValueError, match=f"not available on {location}"):
        resource_cls(args=args, opt=make_opt(**{location: True}))


def test_starcheck_url_regression_occweb(monkeypatch):
    monkeypatch.setattr(
        mm,
        "get_observation",
        lambda **kwargs: {"source": "DEC2324B", "obsid": 28365},
    )
    monkeypatch.setattr(
        mm.parse_cm.paths,
        "load_url_from_load_name",
        lambda load_name, server: f"https://{server}.example/{load_name}",
    )

    resource = mm.ResourceStarcheck(args=["2025:001"], opt=make_opt(occweb=True))
    assert (
        resource.get_url()
        == "https://occweb.example/DEC2324B/starcheck.html#obsid28365"
    )


def test_starcheck_url_regression_cxc(monkeypatch):
    monkeypatch.setattr(
        mm,
        "get_observation",
        lambda **kwargs: {"source": "DEC2324B", "obsid": 28365},
    )
    monkeypatch.setattr(
        mm.parse_cm.paths,
        "load_url_from_load_name",
        lambda load_name, server: f"https://{server}.example/{load_name}",
    )

    resource = mm.ResourceStarcheck(args=["2025:001"], opt=make_opt(cxc=True))
    assert (
        resource.get_url() == "https://icxc.example/DEC2324B/starcheck.html#obsid28365"
    )


def test_mica_url_regression():
    resource = mm.ResourceMica(
        obsid=43474, load_name="APR2924A", opt=make_opt(cxc=True)
    )
    assert (
        resource.get_url()
        == "https://kadi.cfa.harvard.edu/mica/?obsid_or_date=43474&load_name=APR2924A"
    )


def test_agasc_url_regression():
    resource = mm.ResourceAgasc(agasc_id=701368208, opt=make_opt(cxc=True))
    assert (
        resource.get_url()
        == "https://cxc.cfa.harvard.edu/mta/ASPECT/agasc/supplement_reports/stars/070/701368208/index.html"
    )


def test_star_history_url_regression():
    resource = mm.ResourceStarHistory(agasc_id=701368208, opt=make_opt(cxc=True))
    assert (
        resource.get_url()
        == "https://kadi.cfa.harvard.edu/star_hist/?agasc_id=701368208"
    )


def test_centroid_dashboard_url_regression_cxc(monkeypatch):
    monkeypatch.setattr(
        mm.parse_cm, "parse_load_name", lambda name: ("APR", "2924", "A", 2024)
    )
    resource = mm.ResourceCentroidDashboard(
        obsid=43474,
        load_name="APR2924A",
        opt=make_opt(cxc=True),
    )
    assert (
        resource.get_url()
        == "https://icxc.cfa.harvard.edu/aspect/centroid_reports/2024/APR2924A/43474/index.html"
    )


def test_centroid_dashboard_url_regression_local(monkeypatch):
    monkeypatch.setattr(
        mm.parse_cm, "parse_load_name", lambda name: ("APR", "2924", "A", 2024)
    )
    resource = mm.ResourceCentroidDashboard(
        obsid=43474,
        load_name="APR2924A",
        opt=make_opt(local=True),
    )
    assert (
        resource.get_url()
        == f"file://{mm.SKA}/data/centroid_dashboard/centroid_reports/2024/APR2924A/43474/index.html"
    )


def test_chaser_url_regression():
    resource = mm.ResourceChaser(obsid=43474, opt=make_opt(cxc=True))
    assert (
        resource.get_url()
        == "https://cda.cfa.harvard.edu/chaser/startViewer.do?menuItem=details&obsid=43474"
    )


def test_fot_daily_plots_url_regression():
    resource = mm.ResourceFotDailyPlots(
        date=mm.CxoTime("2024:125:06:22:32"), opt=make_opt(occweb=True)
    )
    assert (
        resource.get_url()
        == "https://occweb.cfa.harvard.edu/occweb/FOT/engineering/reports/dailies/2024/MAY/may04_125/"
    )


@pytest.mark.parametrize(
    "resource_cls,opt_kwargs,error_substr",
    [
        (mm.ResourceStarcheck, {"occweb": True}, "need to specify at least one"),
        (mm.ResourceMica, {"cxc": True}, "need to specify at least one"),
        (mm.ResourceAgasc, {"cxc": True}, "agasc_id must be specified"),
        (mm.ResourceStarHistory, {"cxc": True}, "agasc_id must be specified"),
        (mm.ResourceCentroidDashboard, {"cxc": True}, "need to specify at least one"),
        (mm.ResourceChaser, {"cxc": True}, "need to specify at least one"),
        (mm.ResourceFotDailyPlots, {"occweb": True}, "requires either obsid or date"),
    ],
)
def test_resource_get_url_exceptions(resource_cls, opt_kwargs, error_substr):
    resource = resource_cls(opt=make_opt(**opt_kwargs))
    with pytest.raises(ValueError, match=error_substr):
        resource.get_url()
