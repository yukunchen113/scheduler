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
