from app.comparator import compare_output, normalize_output


def test_ignore_repeated_and_trailing_spaces():
    assert compare_output("a   b  \ncd   \n", "a b\ncd\n")


def test_ignore_tabs_and_extra_line_breaks_between_tokens():
    assert compare_output("a\t b\n\ncd\n", "a b cd")


def test_do_not_merge_or_split_tokens():
    assert not compare_output("12\n", "1 2\n")
    assert not compare_output("1 23\n", "12 3\n")


def test_case_sensitive():
    assert not compare_output("Hello\n", "hello\n")


def test_normalize_crlf():
    assert normalize_output("a\r\nb\r\n") == "a b"


def test_empty_and_whitespace_only_outputs_match():
    assert compare_output(" \t\r\n", "")
