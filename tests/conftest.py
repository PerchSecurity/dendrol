from _pytest.config import Config
from icdiff import ConsoleDiff
from py._io.terminalwriter import get_terminal_width


# This is done during initialization, before any tests are run, instead of
# within our assertrepr hook — because the assertrepr hook is called while
# terminal capturing is enabled and all calls to get_terminal_width() return 80
# ref: https://github.com/pytest-dev/pytest/issues/4030#issuecomment-425672782
INITIAL_TERMWIDTH = get_terminal_width()


def pytest_assertrepr_compare(config: Config, op: str, left, right):
    # Local import to avoid preclusion of pytest's assertion rewriting
    from dendrol import PatternTree

    # Resets the red color from the "E" at the start of each pytest
    # exception/assertion traceback line -- markup() appends a reset
    # character after its output, so we give it an empty string,
    # because we only care about that reset.
    terminal_writer = config.get_terminal_writer()
    reset_colors = lambda s: terminal_writer.markup('', white=True) + s

    if op == '==' and isinstance(left, PatternTree) and isinstance(right, PatternTree):
        left_desc = 'PatternTree(<left>)'
        right_desc = 'PatternTree(<right>)'
        rewritten_assert = f'{left_desc} {op} {right_desc}'

        summary = 'The pattern trees are not equivalent. Full diff:'

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
            '',
            summary,
            '',
        ]
        lines.extend(
            reset_colors(diff_line)
            for diff_line in diff
        )
        return lines
