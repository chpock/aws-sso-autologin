def test_tokenize_log_line_returns_tokens():
    from aws_sso_autologin.classifier import tokenize_log_line

    tokens = tokenize_log_line("2026-01-01 12:00:00 INFO: Login successful")
    assert isinstance(tokens, list)
    assert len(tokens) > 0
