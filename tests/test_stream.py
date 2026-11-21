from conftest import req

from elevator_sim.models import Request
from elevator_sim.stream import RequestStream


def ids(requests):
    return [r.passenger_id for r in requests]


def make_stream():
    """Requests at times 0, 0, 3 and 7, in that input order."""
    return RequestStream([req(0, "a", 1, 5), req(0, "b", 2, 6), req(3, "c", 4, 1), req(7, "d", 9, 2)])


def test_pop_until_returns_requests_due_now_in_input_order():
    stream = make_stream()
    assert ids(stream.pop_until(0)) == ["a", "b"]


def test_pop_until_returns_nothing_when_no_request_is_due():
    stream = make_stream()
    stream.pop_until(0)
    assert stream.pop_until(2) == []


def test_each_request_is_returned_only_once():
    stream = make_stream()
    stream.pop_until(0)
    stream.pop_until(2)
    assert ids(stream.pop_until(3)) == ["c"]
    assert stream.pop_until(3) == []


def test_pop_until_releases_everything_remaining_and_marks_exhausted():
    stream = make_stream()
    stream.pop_until(3)
    assert not stream.exhausted
    assert ids(stream.pop_until(10)) == ["d"]
    assert stream.exhausted


def test_empty_stream_is_exhausted_immediately():
    stream = RequestStream([])
    assert stream.exhausted
    assert stream.total == 0
    assert stream.pop_until(0) == []


def test_unsorted_input_is_released_in_time_order():
    stream = RequestStream([req(7, "late", 1, 2), req(0, "first", 1, 2), req(3, "middle", 1, 2)])
    assert ids(stream.pop_until(10)) == ["first", "middle", "late"]


def test_same_time_ties_use_input_order_not_list_position():
    second = Request(time=2, passenger_id="second", source=1, dest=2, input_order=1)
    first = Request(time=2, passenger_id="first", source=1, dest=2, input_order=0)
    stream = RequestStream([second, first])
    assert ids(stream.pop_until(2)) == ["first", "second"]


def test_earlier_time_after_a_later_one_returns_nothing():
    stream = make_stream()
    stream.pop_until(3)
    assert stream.pop_until(1) == []
    assert ids(stream.pop_until(7)) == ["d"]


def test_total_counts_all_requests_and_never_changes():
    stream = make_stream()
    assert stream.total == 4
    stream.pop_until(3)
    assert stream.total == 4
    stream.pop_until(10)
    assert stream.total == 4


def test_changing_the_original_list_does_not_affect_the_stream():
    requests = [req(0, "a", 1, 5), req(3, "b", 2, 6)]
    stream = RequestStream(requests)
    requests.append(req(1, "added", 1, 2))
    requests.pop(0)
    assert stream.total == 2
    assert ids(stream.pop_until(10)) == ["a", "b"]


def test_stream_offers_no_way_to_look_ahead():
    stream = make_stream()
    public = {name for name in dir(stream) if not name.startswith("_")}
    assert public == {"pop_until", "exhausted", "total"}
    for hidden in ("__iter__", "__len__", "__getitem__"):
        assert not hasattr(stream, hidden)
