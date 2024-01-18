from plex.daily.timing import process_minutes


def test_process_minutes() -> None:
    input_str = "asdf dasf as d [12] [45]*2 [1hr] [2h] [1h15]*2"
    output_list = process_minutes(input_str)
    assert output_list == [12, 45, 45, 60, 120, 75, 75]
