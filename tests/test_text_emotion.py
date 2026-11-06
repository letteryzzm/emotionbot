from perception.text_emotion import TextEmotion, keyword_probs


def test_keyword_positive():
    assert max(keyword_probs("今天特别开心"), key=keyword_probs("今天特别开心").get) == "happy"


def test_literal_sarcasm_stays_positive():
    # 文本层就应该按字面判 happy，矛盾留给融合层去发现
    p = keyword_probs("太好了，又要加班")
    assert max(p, key=p.get) == "happy"


def test_negative_keywords():
    p = keyword_probs("烦死了，真的受不了")
    assert max(p, key=p.get) in {"angry", "disgust"}


def test_offline_fallback_used_without_key():
    t = TextEmotion(api_key="")
    probs, src = t.infer("今天特别开心")
    assert src == "keyword"
    assert max(probs, key=probs.get) == "happy"


def test_empty_text_is_safe():
    probs, src = TextEmotion(api_key="").infer("   ")
    assert src == "empty"
    assert abs(sum(probs.values()) - 1.0) < 1e-9
