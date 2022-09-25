# mypy: ignore-errors
import inkex
import pytest

from inkex_bh.constants import BH_RAT_GUIDE_MODE
from inkex_bh.constants import BH_RAT_PLACEMENT
from inkex_bh.constants import NSMAP
from inkex_bh.hide_rats import _dwim_rat_layer_name
from inkex_bh.hide_rats import _move_offset_to_transform
from inkex_bh.hide_rats import _xp_str
from inkex_bh.hide_rats import BadRats
from inkex_bh.hide_rats import bounding_box
from inkex_bh.hide_rats import clone_rat_layer
from inkex_bh.hide_rats import containing_layer
from inkex_bh.hide_rats import find_exclusions
from inkex_bh.hide_rats import find_rat_layer
from inkex_bh.hide_rats import get_rat_boundary
from inkex_bh.hide_rats import HideRats
from inkex_bh.hide_rats import RatGuide
from inkex_bh.hide_rats import RatPlacer


pytestmark = pytest.mark.usefixtures("assert_quiet")


@pytest.fixture(scope="session")
def eval_xpath():
    dummy_etree = inkex.load_svg("<svg />")
    return dummy_etree.xpath


@pytest.mark.parametrize("val", ["simple", 'Joe\'s "house"'])
def test_xp_str(val, eval_xpath):
    quoted = _xp_str(val)
    assert eval_xpath(quoted) == val


def test_containing_layer(svg_maker):
    group = svg_maker.add_group()
    rect = svg_maker.add_rectangle(parent=group)
    assert containing_layer(rect) is svg_maker.layer1


def test_containing_layer_none(svg_maker):
    rect = svg_maker.add_rectangle(parent=svg_maker.svg)
    assert containing_layer(rect) is None


def test_bounding_box(svg_maker):
    g1 = svg_maker.add_group()
    g2 = svg_maker.add_group(parent=g1)
    rect = svg_maker.add_rectangle(parent=g2, x=0, y=0, width=1, height=2)
    g1.set("transform", "translate(0, 10)")
    g2.set("transform", "translate(5, 0)")
    rect.set("transform", "scale(2)")

    bbox = bounding_box(rect)
    assert bbox.left == pytest.approx(5)
    assert bbox.top == pytest.approx(10)
    assert bbox.height == pytest.approx(4)
    assert bbox.width == pytest.approx(2)


def test_RatGuide(svg_maker):
    exclusions = []
    rat_layer = svg_maker.add_layer("Blind 1", parent=svg_maker.layer1)
    rg = RatGuide(exclusions, rat_layer)
    assert rg.exclusions == exclusions
    # Check guide layer was created
    (guide_layer,) = svg_maker.svg.xpath(
        "//svg:g[@bh:rat-guide-mode='layer']", namespaces=NSMAP
    )
    assert guide_layer.get("inkscape:label").startswith("[h] ")


def test_RatGuide_adds_notation(svg_maker):
    exclusions = [inkex.BoundingBox((1, 2), (3, 5))]
    rat_layer = svg_maker.add_layer("Blind 1", parent=svg_maker.layer1)
    rg = RatGuide(exclusions, rat_layer)
    assert rg.exclusions == exclusions
    # Check guide layer was created
    (rect,) = svg_maker.layer1.xpath(
        "./*/svg:rect[@bh:rat-guide-mode='notation']", namespaces=NSMAP
    )
    assert rect.bounding_box() == exclusions[0]


def test_RatGuide_finds_existing_guide_layer(svg_maker):
    guide_layer = svg_maker.add_layer("Guide Layer", parent=svg_maker.layer1)
    guide_layer.set(BH_RAT_GUIDE_MODE, "layer")
    # Create a user exclusion rectangle in the existing guide layer
    svg_maker.add_rectangle(parent=guide_layer, x=1, y=2, width=3, height=4)
    rat_layer = svg_maker.add_layer("Blind 1", parent=svg_maker.layer1)
    rg = RatGuide([], rat_layer)
    # Make sure user exclusion was found
    assert rg.exclusions == [inkex.BoundingBox((1, 4), (2, 6))]


def test_RatGuide_cleans_existing_notation(svg_maker):
    guide_layer = svg_maker.add_layer("Guide Layer", parent=svg_maker.layer1)
    guide_layer.set(BH_RAT_GUIDE_MODE, "layer")
    notation = svg_maker.add_rectangle(parent=guide_layer, x=1, y=2, width=3, height=4)
    notation.set(BH_RAT_GUIDE_MODE, "notation")
    exclusions = [inkex.BoundingBox((1, 2), (3, 5))]
    rat_layer = svg_maker.add_layer("Blind 1", parent=svg_maker.layer1)
    rg = RatGuide(exclusions, rat_layer)

    assert rg.exclusions == exclusions
    # Check guide layer was created
    (rect,) = svg_maker.layer1.xpath(
        "./*/svg:rect[@bh:rat-guide-mode='notation']", namespaces=NSMAP
    )
    assert rect.bounding_box() == exclusions[0]


def test_RatGuide_add_exclusion(svg_maker):
    exclusion = inkex.BoundingBox((10, 11), (5, 6))
    rg = RatGuide([], svg_maker.layer1)
    rg.add_exclusion(exclusion)
    assert rg.exclusions == [exclusion]


def test_RatGuide_add_exclusion_is_persistent(svg_maker):
    exclusion = inkex.BoundingBox((10, 11), (5, 6))
    rg = RatGuide([], svg_maker.layer1)
    rg.add_exclusion(exclusion)

    rg2 = RatGuide([], svg_maker.layer1)
    assert rg2.exclusions == [exclusion]


def test_RatGuide_reset_clears_exclusions(svg_maker):
    exclusion = inkex.BoundingBox((10, 11), (5, 6))
    rg = RatGuide([], svg_maker.layer1)
    rg.add_exclusion(exclusion)

    RatGuide([], svg_maker.layer1).reset()

    rg2 = RatGuide([], svg_maker.layer1)
    assert rg2.exclusions == []


def test_move_offset_to_transform(svg_maker):
    sym = svg_maker.add_symbol()
    use = svg_maker.add_use(sym, x=10, y=20)
    _move_offset_to_transform(use)
    assert use.transform == inkex.Transform("translate(10, 20)")
    assert use.get("x") == "0"
    assert use.get("y") == "0"


def test_move_offset_to_transform_no_offset(svg_maker):
    sym = svg_maker.add_symbol()
    use = svg_maker.add_use(sym)
    use.transform = inkex.Transform("translate(10, 20)")
    _move_offset_to_transform(use)
    assert use.transform == inkex.Transform("translate(10, 20)")
    assert use.get("x") == "0"
    assert use.get("y") == "0"


def test_RatPlacer_place_rat(svg_maker, monkeypatch):
    tube = svg_maker.add_symbol(id="rat")
    svg_maker.add_rectangle(width=20, height=20, parent=tube)
    rat = svg_maker.add_use(tube)
    monkeypatch.setattr("random.uniform", lambda x0, x1: (x0 + x1) / 2)
    placer = RatPlacer(inkex.BoundingBox((0, 100), (0, 100)), [])
    placer.place_rat(rat)
    assert rat.transform == inkex.Transform("translate(40, 40)")


def test_RatPlacer_place_bboxless_rat(svg_maker, monkeypatch):
    tube = svg_maker.add_symbol(id="rat")
    rat = svg_maker.add_use(tube)
    monkeypatch.setattr("random.uniform", lambda x0, x1: (x0 + x1) / 2)
    placer = RatPlacer(inkex.BoundingBox((0, 100), (0, 100)), [])
    placer.place_rat(rat)
    assert rat.transform == inkex.Transform("translate(50, 50)")


def test_RatPlacer_random_position(monkeypatch):
    monkeypatch.setattr("random.uniform", lambda x0, x1: (x0 + x1) / 2)
    placer = RatPlacer(inkex.BoundingBox((0, 100), (0, 100)), [])
    pos = placer.random_position(inkex.BoundingBox((1000, 1020), (1000, 1020)))
    assert tuple(pos) == (40, 40)


def test_RatPlacer_random_position_warns(monkeypatch, capsys):
    monkeypatch.setattr("random.uniform", lambda x0, x1: (x0 + x1) / 2)
    placer = RatPlacer(
        inkex.BoundingBox((0, 100), (0, 100)), [inkex.BoundingBox((50, 51), (50, 51))]
    )
    pos = placer.random_position(inkex.BoundingBox((1000, 1020), (1000, 1020)))
    assert tuple(pos) == (40, 40)
    assert "Can not find non-excluded location" in capsys.readouterr().err


@pytest.mark.parametrize(
    "labels, expect",
    [
        ([], "Blind 1"),
        (["[o|blinds] Blind 3", "[o|blinds] Blind 1"], "[o|blinds] Blind 4"),
        (["[o|blinds] Blind 3", "[o|blinds-n] Blind 1"], "Blind 4"),
    ],
)
def test_dwim_rat_layer_name(labels, expect):
    assert _dwim_rat_layer_name(labels) == expect


def test_clone_rat_layer(svg_maker):
    tube = svg_maker.add_symbol(id="rat1")
    blind1 = svg_maker.add_layer("[o|blinds] Blind 1", parent=svg_maker.layer1)
    rat = svg_maker.add_use(tube, parent=blind1)
    clone, new_rats = clone_rat_layer(blind1, [rat])
    assert clone.getnext() is blind1
    assert len(new_rats) == 1
    new_rat = new_rats.pop()
    assert new_rat.href is tube
    assert new_rat.getparent() is clone


def test_find_exclusions(svg_maker):
    r1 = svg_maker.add_rectangle(width=30, height=40)
    r1.set(BH_RAT_PLACEMENT, "exclude")
    exclusions = find_exclusions(svg_maker.svg)
    assert len(exclusions) == 1
    assert tuple(exclusions[0]) == ((0, 30), (0, 40))


def test_find_exclusions_in_symbol(svg_maker):
    sym = svg_maker.add_symbol()
    r1 = svg_maker.add_rectangle(width=10, height=20, parent=sym)
    r1.set(BH_RAT_PLACEMENT, "exclude")

    svg_maker.add_use(sym, x=100, y=200)
    exclusions = find_exclusions(svg_maker.svg)
    assert len(exclusions) == 1
    assert tuple(exclusions[0]) == ((100, 110), (200, 220))


def test_find_exclusions_in_scaled_symbol(svg_maker):
    sym = svg_maker.add_symbol()
    r1 = svg_maker.add_rectangle(width=10, height=20, parent=sym)
    r1.set(BH_RAT_PLACEMENT, "exclude")

    use = svg_maker.add_use(sym, x=1, y=2)
    use.transform.add_translate(10, 10)
    use.transform.add_scale(2)
    exclusions = find_exclusions(svg_maker.svg)
    assert len(exclusions) == 1
    assert tuple(exclusions[0]) == ((12, 32), (14, 54))


def test_find_exclusions_bad_nonresolvable_href(svg_maker, capsys):
    sym = svg_maker.add_symbol()
    use = svg_maker.add_use(sym)
    use.set("xlink:href", "#bad")
    exclusions = find_exclusions(svg_maker.svg)
    assert len(exclusions) == 0
    captured = capsys.readouterr()
    assert "Invalid href" in captured.err


def test_get_rat_boundary(svg_maker):
    rect = svg_maker.add_rectangle(x=100, y=200, width=10, height=20)
    rect.set(BH_RAT_PLACEMENT, "boundary")
    boundary = get_rat_boundary(svg_maker.svg)
    assert list(boundary) == [(100, 110), (200, 220)]


def test_get_rat_boundary_computes_hull(svg_maker):
    r1 = svg_maker.add_rectangle(x=100, y=200, width=10, height=20)
    r2 = svg_maker.add_rectangle(x=300, y=400, width=30, height=40)
    r1.set(BH_RAT_PLACEMENT, "boundary")
    r2.set(BH_RAT_PLACEMENT, "boundary")
    boundary = get_rat_boundary(svg_maker.svg)
    assert list(boundary) == [(100, 330), (200, 440)]


def test_get_rat_boundary_returns_page_bbox(svg_maker):
    boundary = get_rat_boundary(svg_maker.svg)
    assert list(boundary) == [(0, 816), (0, 1056)]


def test_find_rat_layers(svg_maker):
    rat_tube = svg_maker.add_symbol(id="rat-tube")
    rat_layer = svg_maker.add_layer()
    rat1 = svg_maker.add_use(rat_tube, parent=rat_layer)
    rat2 = svg_maker.add_use(rat_tube, parent=rat_layer)
    assert find_rat_layer([rat1, rat2]) is rat_layer


def test_find_rat_layers_fishy_rats(svg_maker):
    rat = svg_maker.add_rectangle()
    with pytest.raises(BadRats) as exc_info:
        find_rat_layer([rat])
    assert exc_info.match(r"Fishy")


def test_find_rat_layers_no_rats_selected():
    with pytest.raises(BadRats) as exc_info:
        find_rat_layer([])
    assert exc_info.match(r"No rats selected")


def test_find_rat_layers_rats_are_not_on_same_level(svg_maker):
    rat_tube = svg_maker.add_symbol(id="rat-tube")
    rat_layer = svg_maker.add_layer()
    rat1 = svg_maker.add_use(rat_tube, parent=rat_layer)
    rat2 = svg_maker.add_use(rat_tube, parent=svg_maker.layer1)
    with pytest.raises(BadRats) as exc_info:
        find_rat_layer([rat1, rat2])
    assert exc_info.match(r"not all on the same layer")


def test_find_rat_layers_rats_are_not_on_a_layer(svg_maker):
    rat_tube = svg_maker.add_symbol(id="rat-tube")
    rat = svg_maker.add_use(rat_tube, parent=svg_maker.svg)
    with pytest.raises(BadRats) as exc_info:
        find_rat_layer([rat])
    assert exc_info.match(r"not on a layer")


@pytest.fixture
def effect() -> inkex.EffectExtension:
    return HideRats()


def test_HideRats(svg_maker, run_effect):
    tube = svg_maker.add_symbol(id="rat-tube")
    svg_maker.add_rectangle(width=20, height=20, parent=tube)
    blind1 = svg_maker.add_layer("[o|blinds] Blind 1", parent=svg_maker.layer1)
    rat1_id = svg_maker.add_use(tube, parent=blind1).get_id()
    svg = run_effect("--id", rat1_id, svg_maker.as_file())
    (rat,) = svg.xpath("//svg:use")
    assert rat.transform.is_translate()
    assert rat.transform.e != 0
    assert rat.transform.f != 0


def test_HideRats_no_rats(svg_maker, run_effect, capsys):
    assert run_effect(svg_maker.as_file()) is None
    assert "No rats" in capsys.readouterr().err


def test_HideRats_restart(svg_maker, run_effect, capsys):
    tube = svg_maker.add_symbol(id="rat-tube")
    svg_maker.add_rectangle(width=20, height=20, parent=tube)
    blind1 = svg_maker.add_layer("[o|blinds] Blind 1", parent=svg_maker.layer1)
    guide = svg_maker.add_layer("Rat Guide", parent=svg_maker.layer1)
    guide.set(BH_RAT_GUIDE_MODE, "layer")
    exclusion = svg_maker.add_rectangle(width=10, height=10, parent=guide)
    exclusion.set(BH_RAT_GUIDE_MODE, "exclusion")
    rat1_id = svg_maker.add_use(tube, parent=blind1).get_id()
    svg = run_effect("--restart", "true", "--id", rat1_id, svg_maker.as_file())
    exclusions = svg.xpath("//*[@bh:rat-guide-mode='exclusion']", namespaces=NSMAP)
    assert len(exclusions) == 1


def test_HideRats_newblind(svg_maker, run_effect, capsys):
    tube = svg_maker.add_symbol(id="rat-tube")
    svg_maker.add_rectangle(width=20, height=20, parent=tube)
    blind1 = svg_maker.add_layer("[o|blinds] Blind 1", parent=svg_maker.layer1)
    rat1_id = svg_maker.add_use(tube, parent=blind1).get_id()
    svg_maker.add_text("Test", parent=blind1)

    svg = run_effect("--newblind", "true", "--id", rat1_id, svg_maker.as_file())

    blinds = svg.xpath(
        "//*[@inkscape:groupmode='layer' and contains(@inkscape:label, 'Blind')]",
        namespaces=NSMAP,
    )
    assert len(blinds) == 2

    # Ensure no text with mangled font size (from
    # workarounds.text_bbox_hack) were created
    saved_styles = svg.xpath("//@x-save-style")
    assert len(saved_styles) == 0
