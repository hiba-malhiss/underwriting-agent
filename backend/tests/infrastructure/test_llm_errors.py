"""Azure's content filter: the error says which filter blocked the prompt."""

from app.infrastructure.llm import _content_filters


def test_the_blocking_filters_are_named():
    body = {
        "code": "content_filter",
        "innererror": {
            "code": "ResponsibleAIPolicyViolation",
            "content_filter_result": {
                "hate": {"filtered": False, "severity": "safe"},
                "jailbreak": {"filtered": True, "detected": True},
                "self_harm": {"filtered": False, "severity": "safe"},
            },
        },
    }
    assert _content_filters(body) == ["jailbreak"]


def test_other_errors_are_not_content_filters():
    assert _content_filters({"code": "rate_limit_exceeded"}) == []
    assert _content_filters(None) == []
    assert _content_filters({"code": "content_filter"}) == ["no category given"]
