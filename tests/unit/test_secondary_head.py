from servicepilot.routing.secondary_head import (
    CharNgramCentroidBinaryHead,
    character_ngrams,
)


def test_character_features_are_deterministic() -> None:
    assert character_ngrams("配送 超时") == character_ngrams("配送超时")
    assert "配送" in character_ngrams("配送超时")
    assert "配送超" in character_ngrams("配送超时")


def test_centroid_head_requires_both_classes() -> None:
    try:
        CharNgramCentroidBinaryHead.fit((("配送超时", True),))
    except ValueError as exc:
        assert "both positive and negative" in str(exc)
    else:
        raise AssertionError("single-class fit should fail")


def test_centroid_head_uses_fixed_zero_margin() -> None:
    head = CharNgramCentroidBinaryHead.fit(
        (
            ("配送超时并要求人工投诉", True),
            ("送达延迟同时转人工", True),
            ("只登记配送超时", False),
            ("仅记录送达延迟", False),
        )
    )

    assert head.predict("配送超时还要人工投诉").positive is True
    assert head.predict("只记录配送延迟").positive is False
