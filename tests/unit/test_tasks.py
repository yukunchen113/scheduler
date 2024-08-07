"""
Tests task driven changes
"""

from datetime import datetime
from pprint import pformat

import pytest

from plex.daily.base import process_daily_lines

CUR_DATESTR = datetime.now().date().isoformat()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
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
            "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n",
            # Output:
            "asdf dasf as d |fgxp| [12][45]*2[1h][2h][1h15]*2\n"
            "-------------\n\n"
            "\t7:30-8:15:\tasdf dasf as d |fgxp:2| (45)\t\n"
            "\t8:15-8:27:\tasdf dasf as d |fgxp:0| (12)\t\n"
            "\t8:27-9:12:\tasdf dasf as d |fgxp:1| (45)\t\n"
            "\t9:12-10:27:\tasdf dasf as d |fgxp:5| (1h15)\t\n"
            "\t10:27-12:27:\tasdf dasf as d |fgxp:4| (2h)\t\n"
            "\t12:27-13:27:\tasdf dasf as d |fgxp:3| (1h)\t\n"
            "\t13:27-14:42:\tasdf dasf as d |fgxp:6| (1h15)\t\n",
        )
    ],
)
def test_task_reorder_calc(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert actual == str_output, f"Expected:\n{str_output}\n\nActual:\n{actual}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
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
            "10pm\n",
            # Output:
            "asdf dasf as d |fgxp| [12][45]*2[1h][2h][1h15]*2\n"
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
            "22:00\n",
        )
    ],
)
def test_task_user_defined_start_ends(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
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
            "10pm\n",
            # Output:
            "asdf dasf as d |fgxp| [12][45]*2[1h][2h][1h15]*2\n"
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
            "22:00\n",
        )
    ],
)
def test_task_diffs(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
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
            "22:00\n",
            # Output:
            "asdf dasf as d |fgxp| [12][45]*2[1h][2h][1h15]*2\n"
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
            "22:00\n",
        ),
        (
            # Input:
            "test |8oio| [0]\n"
            "\n"
            "test1 |8oi2| [0]\n"
            "- test2 |8oi3| [0]\n"
            "-------------\n\n"
            "\t7:30-7:30:\ttest |8oio1:0| (0)\t\n"
            "\n"
            "\t7:30-7:30:\ttest1 |8oi2:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi31:0| (0)\t\n",
            # Output:
            "test |8oio| [0]\n"
            "\n"
            "test1 |8oi2| [0]\n"
            "- test2 |8oi3| [0]\n"
            "-------------\n\n"
            "\t7:30-7:30:\ttest1 |8oi2:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:0| (0)\t\n"
            "\t7:30-7:30:\ttest |8oio:0| (0)\t\n",
        ),
    ],
)
def test_task_subtasks(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        # subtask shifting
        (
            # Input:
            "test |8oio| [0] (9)# test\n"
            "- notes\n"
            "\n"
            "\n"
            "notes:\n"
            "test1 |8oi2| [0] (10e)\n"
            "- notes\n"
            "- test2 |8oi3| [0][0]*3[0] # test\n"
            "\t- test notes\n"
            "-------------\n"
            "\n"
            "\t7:30-7:30:\ttest |8oio:0| (-)\t\n"
            "\n"
            "\t7:30-7:30:\ttest1 |8oi2:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:1| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:2| (-)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:3| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:4| (0)\t\n"
            "\t\t7:30-7:30:\ttest3 |8oi3:5| (0)\t\n",
            # Output:
            "- notes\n"
            "\n"
            "\n"
            "notes:\n"
            "test1 |8oi2| [0] (10ame)\n"
            "- notes\n"
            "- test2 |8oi3| [0][0]*2[0] # test\n"
            "\t- test notes\n"
            "-------------\n"
            "\n"
            "\t7:30-7:30:\ttest1 |8oi2:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:0| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:1| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:3| (0)\t\n"
            "\t\t7:30-7:30:\ttest2 |8oi3:2| (0)\t\n",
        )
    ],
)
def test_task_induced_deletion(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize(
    "str_input",
    [
        # subtask shifting
        (
            # Input:
            "wake up |daily-morning/0| [20] (7:30am)\n"
            "skincare |daily-morning/1| [15]\n"
            "- test 1 |rtxv| [1]\n"
            "- test 2 |o86w| [1]\n"
            "- test 3 |l2v3| [1]\n"
            "get ready |daily-morning/2| [10]\n"
            "\n"
            "go to lunch |food-out/0| [15]\n"
            "lunch |food-out/1| [1h] #expense\n"
            "come back from lunch |food-out/2| [15]\n"
            "\n"
            "evaluate medium term goals |goals-plan/0| [1h45]\n"
            "\n"
            "start recording |software-competitive_advent/2| [10]\n"
            "new AoC - open book approach guidelines |software-competitive_advent/0| [1h30]\n"
            "competitive programing retro |software-competitive_advent/1| [20]\n"
            "\n"
            "budget:plan |software-project/0| [2h]\n"
            "\n"
            "dishes |daily-night/0| [15]\n"
            "schedule |daily-night/1| [20]\n"
            "get ready for bed |daily-night/2| [20]\n"
            "sleep |daily-night/3| [5]\n"
            "\n"
            "-------------\n"
            "\n"
            "9\n"
            "\n"
            "11:00\n"
            "\t11:00-11:20:\twake up |daily-morning/0:0| (20)\t\n"
            "\t\t- test 1\n"
            "\n"
            "\t\t\t\t- test 2\n"
            "\t\t- test 3\n"
            "\n"
            "\t11:20-11:35:\tskincare |daily-morning/1:0| (15)\t\n"
            "\t11:22\n"
            "\t\t11:22-11:23:\ttest 3 |l2v3:0| (1)\t\n"
            "\t\t11:23-11:24:\ttest 2 |o86w:0| (1)\t\n"
            "\t\t11:24-11:25:\ttest 1 |rtxv:0| (1)\t\n"
            "\n"
            "\t11:35-11:45:\tget ready |daily-morning/2:0| (10)\t\n"
            "\n"
            "\t11:45-12:00:\tgo to lunch |food-out/0:0| (15)\t\n"
            "\t12:00-13:00:\tlunch |food-out/1:0| (1h)\t\n"
            "\t13:00-13:15:\tcome back from lunch |food-out/2:0| (15)\t\n"
            "\n"
            "\t13:15-15:00:\tevaluate medium term goals |goals-plan/0:0| (1h45)\t\n"
            "\n"
            "4pm\n"
            "asdf\n"
            "\n"
            "\t15:00-15:10:\tstart recording |software-competitive_advent/2:0| (10)\t\n"
            "\t15:10-16:40:\tnew AoC - open book approach guidelines |software-competitive_advent/0:0| (1h30)\t\n"
            "\t16:40-17:00:\tcompetitive programing retro |software-competitive_advent/1:0| (20)\t\n"
            "\n"
            "\t\tasdfg\n"
            "\n"
            "abdcd\n"
            "\n"
            "\t17:00-19:00:\tbudget:plan |software-project/0:0| (2h)\t\n"
            "\n"
            "\tasvb45\n"
            "\n"
            "\t{food:out\n"
            "\n"
            "\t22:30-22:45:\tdishes |daily-night/0:0| (15)\t\n"
            "\t22:45-23:05:\tschedule |daily-night/1:0| (20)\t\n"
            "23:05\n"
            "\n"
            "\t23:05-23:25:\tget ready for bed |daily-night/2:0| (20)\t\n"
            "\n"
            "\t23:25-23:30:\tsleep |daily-night/3:0| (5)\t\n"
            "23:30\n"
            "\n"
            "asfgg\n"
        )
    ],
)
def test_task_invariance(str_input: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_input
    ), f"Expected:\n{pformat(str_input)}\n\nActual:\n{pformat(actual)}"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "asdf |fgxp| [1h]\n"
            "- asdf1 |fgxp1| [10]\n"
            "- asdf2 |fgxp2| [10]\n"
            "-------------\n"
            "\n"
            "\t7:30-8:30:\tasdf |fgxp:0| (1h)\t\n"
            "\t7:40\n"
            "\t\t7:30-7:40:\tasdf1 |fgxp1:0| (10)\t\n"
            "\n"
            "\t8:00\n"
            "\t\t7:40-7:50:\tasdf2 |fgxp2:0| (10)\t\n",
            # Output:
            "asdf |fgxp| [1h]\n"
            "- asdf1 |fgxp1| [10]\n"
            "- asdf2 |fgxp2| [10]\n"
            "-------------\n"
            "\n"
            "\t7:30-8:30:\tasdf |fgxp:0| (1h)\t\n"
            "\t7:40\n"
            "\t\t7:40-7:50:\tasdf1 |fgxp1:0| (10)\t\n"
            "\n"
            "\t8:00\n"
            "\t\t8:00-8:10:\tasdf2 |fgxp2:0| (10)\t\n",
        ),
        (
            # Input:
            "asdf |fgxp| [1h]\n"
            "- asdf1 |fgxp1| [10]\n"
            "- asdf2 |fgxp2| [10]\n"
            "-------------\n"
            "\n"
            "\t7:30-8:30:\tasdf |fgxp:0| (1h)\t\n"
            "\t\t7:30-7:40:\tasdf1 |fgxp1:0| (10)\t\n"
            "\t7:50\n"
            "\n"
            "\t\t7:40-7:50:\tasdf2 |fgxp2:0| (10)\t\n"
            "\t8:10\n",
            # Output:
            "asdf |fgxp| [1h]\n"
            "- asdf1 |fgxp1| [10]\n"
            "- asdf2 |fgxp2| [10]\n"
            "-------------\n"
            "\n"
            "\t7:30-8:30:\tasdf |fgxp:0| (1h)\t\n"
            "\t\t7:40-7:50:\tasdf1 |fgxp1:0| (10)\t\n"
            "\t7:50\n"
            "\n"
            "\t\t8:00-8:10:\tasdf2 |fgxp2:0| (10)\t\n"
            "\t8:10\n",
        ),
    ],
)
def test_subtask_user_specified_start(str_input: str, str_output: str) -> None:
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
