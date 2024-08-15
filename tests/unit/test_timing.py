"""
This set of tests show how tasks (or timings) are affected after changes in timings.
"""

from datetime import datetime

import pytest

from plex.daily.base import process_daily_lines

CUR_DATESTR = datetime.now().date().isoformat()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # timing standard
        (
            # Input:
            "asdf dasf as d |fgxp| [12][45]*2[1hr][2h] [1h15]*2",
            # Output:
            "asdf dasf as d |fgxp| [12][45]*2[1h][2h][1h15]*2\n"
            "-------------\n\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
            "\t7:42-8:27:\tasdf dasf as d |fgxp:1| (45)\t\n"
            "\t8:27-9:12:\tasdf dasf as d |fgxp:2| (45)\t\n"
            "\t9:12-10:12:\tasdf dasf as d |fgxp:3| (1h)\t\n"
            "\t10:12-12:12:\tasdf dasf as d |fgxp:4| (2h)\t\n"
            "\t12:12-13:27:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
            "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n",
        )
    ],
)
def test_timing_standard(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # timing deletion in tasks
        (
            # Input:
            "asdf dasf as d |fgxp| [45]\n"
            "-------------\n\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
            "\t7:42-8:27:\tasdf dasf as d |fgxp:1| (45)\t\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp2:0| (12)\t\n",
            # Output:
            "asdf dasf as d |fgxp| [45]\n"
            "-------------\n\n"
            "\t7:30-8:15:\tasdf dasf as d |fgxp:0| (45)\t\n",
        ),
        # timing additions
        (
            # Input:
            "asdf dasf as d |fgxp| [12]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n",
            # Output:
            "asdf dasf as d |fgxp| [12]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
            "\t7:42-7:54:\tasdf dasf as d |fgxp2:0| (12)\t\n",
        ),
    ],
)
def test_timing_addition_deletions(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # timing time change
        (
            # Input:
            "asdf dasf as d |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:42:\tasdf dasf as d |fgxp:0| (12)\t\n"
            "\t7:42-7:54:\tasdf dasf as d |fgxp2:0| (12)\t\n",
            # Output:
            "asdf dasf as d |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf as d |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
        ),
        # timing name change
        (
            # Input:
            "asdf dasf |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf as d |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
            # Output:
            "asdf dasf |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
        ),
    ],
)
def test_timing_existing_timing_changes(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # timing in task area updates
        (
            # Input:
            "asdf dasf |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf as d |fgxp:0| (13)\t\n"
            "asdf dasf |fgxp3| [14]*2\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n"
            "\tasdf dasf |fgxp4| [7]\n",
            # Output:
            "asdf dasf |fgxp| [13]\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "asdf dasf |fgxp3| [14]*2\n"
            "asdf dasf |fgxp4| [7]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf |fgxp:0| (13)\t\n"
            "\t7:43-7:57:\tasdf dasf |fgxp3:0| (14)\t\n"
            "\t7:57-8:11:\tasdf dasf |fgxp3:1| (14)\t\n"
            "\t8:11-8:23:\tasdf dasf as d |fgxp2:0| (12)\t\n"
            "\t\t8:11-8:18:\tasdf dasf |fgxp4:0| (7)\t\n",
        )
    ],
)
def test_timing_task_area_changes(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # timing order change for invariance
        (
            # Input:
            "asdf dasf as d |fgxp2| [12]\n"
            "asdf dasf |fgxp| [13]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf as d |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
            # Output:
            "asdf dasf as d |fgxp2| [12]\n"
            "asdf dasf |fgxp| [13]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
        ),
        # non timing changes for equivariance
        (
            # Input:
            "testing non timing: \n\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "asdf dasf |fgxp| [13]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf as d |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
            # Output:
            "testing non timing: \n\n"
            "asdf dasf as d |fgxp2| [12]\n"
            "asdf dasf |fgxp| [13]\n"
            "-------------\n\n"
            "\t7:30-7:43:\tasdf dasf |fgxp:0| (13)\t\n"
            "\t7:43-7:55:\tasdf dasf as d |fgxp2:0| (12)\t\n",
        ),
    ],
)
def test_timing_invariance_changes(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"
