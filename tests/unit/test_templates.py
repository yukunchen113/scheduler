"""
Tests template driven changes
"""

from datetime import datetime
from pprint import pformat
from unittest.mock import MagicMock, patch

import pytest

from plex.daily.base import process_daily_lines

CUR_DATESTR = datetime.now().date().isoformat()
MOCK_TEMPLATE_BASE_DR = "tests/sample_routines"


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "{daily:morning}",
            # Output:
            "wake up |daily-morning/0| [20]\n"
            "- wakeup pt 1 |daily-morning/1| [10]\n"
            "get ready |daily-morning/2| [30]\n"
            "-------------\n"
            "\n"
            "\t7:30-7:50:\twake up |daily-morning/0:0| (20)\t\n"
            "\t\t7:30-7:40:\twakeup pt 1 |daily-morning/1:0| (10)\t\n"
            "\t7:50-8:20:\tget ready |daily-morning/2:0| (30)\t\n",
        ),
    ],
)
@patch("plex.daily.template.routines.get_template_base_dir", autospec=True)
def test_subtask_user_specified_start(
    mock_get_template_base_dir: MagicMock, str_input: str, str_output: str
) -> None:
    mock_get_template_base_dir.return_value = MOCK_TEMPLATE_BASE_DR
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    mock_get_template_base_dir.assert_called()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "{standard}",
            # Output:
            "@oncl\n"
            "{todo}\n"
            "{daily:morning}\n"
            "{work:oncl}\n"
            "{software:competitive_leetcode_contest}\n"
            "{daily:night}\n",
        ),
    ],
)
@patch("plex.daily.template.routines.get_template_base_dir", autospec=True)
def test_no_tasks_generated_from_templates(
    mock_get_template_base_dir: MagicMock, str_input: str, str_output: str
) -> None:
    mock_get_template_base_dir.return_value = MOCK_TEMPLATE_BASE_DR
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    mock_get_template_base_dir.assert_called()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "{food:order}\n",
            # Output:
            "order lunch |food-order/0| [15] (10am) #expense\n"
            "lunch |food-order/1| [1h] (12pm)\n"
            "\n"
            "-------------\n"
            "\n"
            "10:00\n"
            "\t10:00-10:15:\torder lunch |food-order/0:0| (15)\t\n"
            "\n"
            "12:00\n"
            "\t12:00-13:00:\tlunch |food-order/1:0| (1h)\t\n",
        ),
    ],
)
@patch("plex.daily.template.routines.get_template_base_dir", autospec=True)
def test_user_specified_time_from_template(
    mock_get_template_base_dir: MagicMock, str_input: str, str_output: str
) -> None:
    mock_get_template_base_dir.return_value = MOCK_TEMPLATE_BASE_DR
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    mock_get_template_base_dir.assert_called()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "{daily:night}\n",
            # Output:
            "cleanup/wash dishes |test-night/0| [10]\n"
            "schedule |daily-night/0| [25]\n"
            "get ready for bed |daily-night/1| [20]\n"
            "\n"
            "-------------\n"
            "\n"
            "\t7:30-7:40:\tcleanup/wash dishes |test-night/0:0| (10)\t\n"
            "\t7:40-8:05:\tschedule |daily-night/0:0| (25)\t\n"
            "\t8:05-8:25:\tget ready for bed |daily-night/1:0| (20)\t\n",
        ),
    ],
)
@patch("plex.daily.template.routines.get_template_base_dir", autospec=True)
def test_user_specified_time_from_template(
    mock_get_template_base_dir: MagicMock, str_input: str, str_output: str
) -> None:
    mock_get_template_base_dir.return_value = MOCK_TEMPLATE_BASE_DR
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    mock_get_template_base_dir.assert_called()


@pytest.mark.parametrize(
    "str_input,str_output",
    [
        (
            # Input:
            "{daily:night}\n" "{daily:night}\n",
            # Output:
            "cleanup/wash dishes |test-night/0| [10]\n"
            "schedule |daily-night/0| [25]\n"
            "get ready for bed |daily-night/1| [20]\n"
            "cleanup/wash dishes |test-night/1| [10]\n"
            "schedule |daily-night/2| [25]\n"
            "get ready for bed |daily-night/3| [20]\n"
            "\n"
            "-------------\n"
            "\n"
            "\t7:30-7:40:\tcleanup/wash dishes |test-night/0:0| (10)\t\n"
            "\t7:40-8:05:\tschedule |daily-night/0:0| (25)\t\n"
            "\t8:05-8:25:\tget ready for bed |daily-night/1:0| (20)\t\n"
            "\t8:25-8:35:\tcleanup/wash dishes |test-night/1:0| (10)\t\n"
            "\t8:35-9:00:\tschedule |daily-night/2:0| (25)\t\n"
            "\t9:00-9:20:\tget ready for bed |daily-night/3:0| (20)\t\n",
        ),
        (
            # Input:
            "cleanup/wash dishes |test-night/0| [10]\n"
            "schedule |daily-night/0| [25]\n"
            "get ready for bed |daily-night/1| [20]\n"
            "\n"
            "{daily:night}\n"
            "-------------\n"
            "\n"
            "\t7:30-7:40:\tcleanup/wash dishes |test-night/0:0| (10)\t\n"
            "\t7:40-8:05:\tschedule |daily-night/0:0| (25)\t\n"
            "\t8:05-8:25:\tget ready for bed |daily-night/1:0| (20)\t\n"
            "\n"
            "\t{daily:night}\n"
            "\n"
            "\t{daily:night}\n",
            # Output:
            "cleanup/wash dishes |test-night/0| [10]\n"
            "schedule |daily-night/0| [25]\n"
            "get ready for bed |daily-night/1| [20]\n"
            "\n"
            "cleanup/wash dishes |test-night/3| [10]\n"
            "schedule |daily-night/6| [25]\n"
            "get ready for bed |daily-night/7| [20]\n"
            "cleanup/wash dishes |test-night/1| [10]\n"
            "schedule |daily-night/2| [25]\n"
            "get ready for bed |daily-night/3| [20]\n"
            "cleanup/wash dishes |test-night/2| [10]\n"
            "schedule |daily-night/4| [25]\n"
            "get ready for bed |daily-night/5| [20]\n"
            "-------------\n"
            "\n"
            "\t7:30-7:40:\tcleanup/wash dishes |test-night/0:0| (10)\t\n"
            "\t7:40-8:05:\tschedule |daily-night/0:0| (25)\t\n"
            "\t8:05-8:25:\tget ready for bed |daily-night/1:0| (20)\t\n"
            "\n"
            "\t8:25-8:35:\tcleanup/wash dishes |test-night/1:0| (10)\t\n"
            "\t8:35-9:00:\tschedule |daily-night/2:0| (25)\t\n"
            "\t9:00-9:20:\tget ready for bed |daily-night/3:0| (20)\t\n"
            "\n"
            "\t9:20-9:30:\tcleanup/wash dishes |test-night/2:0| (10)\t\n"
            "\t9:30-9:55:\tschedule |daily-night/4:0| (25)\t\n"
            "\t9:55-10:15:\tget ready for bed |daily-night/5:0| (20)\t\n"
            "\t10:15-10:25:\tcleanup/wash dishes |test-night/3:0| (10)\t\n"
            "\t10:25-10:50:\tschedule |daily-night/6:0| (25)\t\n"
            "\t10:50-11:10:\tget ready for bed |daily-night/7:0| (20)\t\n",
        ),
    ],
)
@patch("plex.daily.template.routines.get_template_base_dir", autospec=True)
def test_multiple_specified_templates(
    mock_get_template_base_dir: MagicMock, str_input: str, str_output: str
) -> None:
    mock_get_template_base_dir.return_value = MOCK_TEMPLATE_BASE_DR
    lines_input = [i + "\n" for i in str_input.split("\n")]
    actual = "".join(process_daily_lines(CUR_DATESTR, lines_input))
    assert (
        actual == str_output
    ), f"Expected:\n{pformat(str_output)}\n\nActual:\n{pformat(actual)}"
    mock_get_template_base_dir.assert_called()
