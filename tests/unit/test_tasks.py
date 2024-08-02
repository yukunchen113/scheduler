""" 
Tests task driven changes
"""
import pytest
from pprint import pformat

from datetime import datetime

from plex.daily.base import process_daily_lines

CUR_DATESTR = datetime.now().date().isoformat()

@pytest.mark.parametrize("str_input,str_output", [
    # task shifting recalculation
    (
        # Input:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "\t8:27-9:12:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t7:42-8:27:\tasdf dasf as d |fgxp:1| (45)\t\n"

        "\t12:12-13:27:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t10:12-12:12:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t9:12-10:12:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        ,
        # Output:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "\t7:30-8:15:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t8:15-8:27:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t8:27-9:12:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\t9:12-10:27:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t10:27-12:27:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t12:27-13:27:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
    )
],
)
def test_task_reorder_calc(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize("str_input,str_output", [
    # user defined times start and end
    (
        # Input:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12\n"
        "\t8:27-9:12:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t7:42-8:27:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t12:12-13:27:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t10:12-12:12:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t9:12-10:12:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "10pm\n"
        ,
        # Output:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12:00\n"
        "\t12:00-12:45:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t12:45-12:57:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t12:57-13:42:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t16:30-17:45:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t17:45-19:45:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t19:45-20:45:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t20:45-22:00:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "22:00\n"
    )
],
)
def test_task_user_defined_start_ends(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    
    
@pytest.mark.parametrize("str_input,str_output", [
    # start and end diffs
    (
        # Input:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12\n"
        "-20\t8:27-9:12:\tasdf dasf as d |fgxp:2| (45)\t+10\n"
        "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t7:42-8:27:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t12:12-13:27:\tasdf dasf as d |fgxp:5| (1h15)\t+10\n"
        "-10\t10:12-12:12:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t9:12-10:12:\tasdf dasf as d |fgxp:3| (1h)\t+10\n"
        "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "10pm\n"
        ,
        # Output:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12:00\n"
        "-20\t11:40-12:35:\tasdf dasf as d |fgxp:2| (45)\t+10\n"
        "\t12:35-12:47:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t12:47-13:32:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t16:30-17:55:\tasdf dasf as d |fgxp:5| (1h15)\t+10\n"
        "-10\t17:45-19:45:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t19:45-20:55:\tasdf dasf as d |fgxp:3| (1h)\t+10\n"
        "\t20:55-22:10:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "22:00\n"
    )
],
)
def test_task_diffs(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize("str_input,str_output", [
    # subtask shifting
    (
        # Input:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12:00\n"
        "\t12:00-12:45:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t\t12:45-12:57:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t12:57-13:42:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t16:30-17:45:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t17:45-19:45:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t\t19:45-20:45:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t\t\t20:45-22:00:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "22:00\n"
        ,
        # Output:
        "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2\n"
        "-------------\n\n"
        "12:00\n"
        "\t12:00-12:45:\tasdf dasf as d |fgxp:2| (45)\t\n"
        "\t\t12:00-12:12:\tasdf dasf as d |fgxp:0| (12)\t\n"
        "\t12:45-13:30:\tasdf dasf as d |fgxp:1| (45)\t\n"
        "\n"
        "\t18:45-20:00:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
        "\t20:00-22:00:\tasdf dasf as d |fgxp:4| (2h)\t\n"
        "\t\t20:00-21:00:\tasdf dasf as d |fgxp:3| (1h)\t\n"
        "\t\t\t20:00-21:15:\tasdf dasf as d |fgxp:6| (1h15)\t\n"
        "22:00\n"
    )
],
)
def test_task_subtasks(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
