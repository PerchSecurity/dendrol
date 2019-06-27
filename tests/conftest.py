from __future__ import unicode_literals, print_function, absolute_import
from _pytest.config import Config
from icdiff import ConsoleDiff
from py._io.terminalwriter import get_terminal_width


# This is done during initialization, before any tests are run, instead of
# within our assertrepr hook - because the assertrepr hook is called while
# terminal capturing is enabled and all calls to get_terminal_width() return 80
# ref: https://github.com/pytest-dev/pytest/issues/4030#issuecomment-425672782
INITIAL_TERMWIDTH = get_terminal_width()


def pytest_assertrepr_compare(config, op, left, right):
    # Local import to avoid preclusion of pytest's assertion rewriting
    from dendrol import PatternTree

    # Resets the red color from the "E" at the start of each pytest
    # exception/assertion traceback line -- markup() appends a reset
    # character after its output, so we give it an empty string,
    # because we only care about that reset.
    terminal_writer = config.get_terminal_writer()
    reset_colors = lambda s: terminal_writer.markup(u'', white=True) + s

    if op == u'==' and isinstance(left, PatternTree) and isinstance(right, PatternTree):
        left_desc = u'PatternTree(<left>)'
        right_desc = u'PatternTree(<right>)'
        rewritten_assert = u'{left_desc} {op} {right_desc}'.format(
            left_desc=left_desc,
            op=op,
            right_desc=right_desc,
        )

        summary = u'The pattern trees are not equivalent. Full diff:'

        left_repr = left.serialize()
        right_repr = right.serialize()

        differ = ConsoleDiff(tabsize=4, cols=120)
        diff = differ.make_table(
            fromdesc=left_desc,
            fromlines=left_repr.splitlines(),
            todesc=right_desc,
            tolines=right_repr.splitlines(),
        )

        lines = [
            rewritten_assert,
            u'',
            summary,
            u'',
        ]
        lines.extend(
            reset_colors(diff_line)
            for diff_line in diff
        )
        return lines
