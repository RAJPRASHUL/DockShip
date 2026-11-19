from pathlib import Path

from dockship.nginx import render


def test_nginx_render_matches_golden_file():
    expected = Path(__file__).parent.joinpath("golden", "hello.conf").read_text()
    assert render("hello", 9001) == expected
