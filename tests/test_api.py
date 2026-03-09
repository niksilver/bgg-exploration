from unittest.mock import MagicMock, patch
from bgg.api import BGGClient, GameSearchResult, GameDetails

SEARCH_XML = """<?xml version="1.0" encoding="utf-8"?>
<items total="2">
    <item type="boardgame" id="266192">
        <name type="primary" sortindex="1" value="Wingspan"/>
        <yearpublished value="2019"/>
    </item>
    <item type="boardgame" id="293260">
        <name type="primary" sortindex="1" value="Wingspan: European Expansion"/>
        <yearpublished value="2019"/>
    </item>
</items>"""

FETCH_XML = """<?xml version="1.0" encoding="utf-8"?>
<items>
    <item type="boardgame" id="266192">
        <name type="primary" sortindex="1" value="Wingspan"/>
        <yearpublished value="2019"/>
        <statistics page="1">
            <ratings>
                <average value="8.07"/>
                <ranks>
                    <rank type="subtype" id="1" name="boardgame"
                          friendlyname="Board Game Rank" value="21"
                          bayesaverage="8.01"/>
                </ranks>
            </ratings>
        </statistics>
    </item>
</items>"""

EMPTY_XML = """<?xml version="1.0" encoding="utf-8"?>
<items total="0"/>"""


def _mock_response(text: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    return resp


def test_search_returns_results():
    session = MagicMock()
    session.get.return_value = _mock_response(SEARCH_XML)
    client = BGGClient(session=session)

    results = client.search("Wingspan")

    assert len(results) == 2
    assert results[0] == GameSearchResult(bgg_id=266192, name="Wingspan", year=2019)
    assert results[1].bgg_id == 293260


def test_search_returns_empty_list_when_no_results():
    session = MagicMock()
    session.get.return_value = _mock_response(EMPTY_XML)
    client = BGGClient(session=session)

    results = client.search("xyzzy")

    assert results == []


def test_fetch_returns_game_details():
    session = MagicMock()
    session.get.return_value = _mock_response(FETCH_XML)
    client = BGGClient(session=session)

    details = client.fetch(266192)

    assert details == GameDetails(
        bgg_id=266192, name="Wingspan", year=2019,
        rating_avg=8.07, bgg_rank=21,
    )


def test_fetch_returns_none_when_item_missing():
    session = MagicMock()
    session.get.return_value = _mock_response(EMPTY_XML)
    client = BGGClient(session=session)

    assert client.fetch(999999) is None


def test_fetch_retries_on_429():
    session = MagicMock()
    session.get.side_effect = [
        _mock_response("", 429),
        _mock_response("", 429),
        _mock_response(FETCH_XML),
    ]
    client = BGGClient(session=session)

    with patch("bgg.api.time.sleep"):
        details = client.fetch(266192)

    assert details is not None
    assert details.bgg_id == 266192
    assert session.get.call_count == 3
