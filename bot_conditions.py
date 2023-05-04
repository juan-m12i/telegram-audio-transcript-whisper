import re
from bot_types import Condition


def lower_match_factory(value: str) -> Condition:
    def exact_match(text: str) -> bool:
        return text.lower() == value.lower()
    return exact_match


def exact_match_factory(value: str) -> Condition:
    def exact_match(text: str) -> bool:
        return text == value
    return exact_match


def first_chars_lower_factory(length: int, value: str) -> Condition:
    def first_chars_lower(text: str) -> bool:
        return text[:length].lower() == value.lower()
    return first_chars_lower


def first_chars_exact_factory(length: int, value: str) -> Condition:
    def first_chars_exact(text: str) -> bool:
        return text[:length] == value
    return first_chars_exact


def regex_match_factory(pattern: str) -> Condition:
    def regex_match(text: str) -> bool:
        return bool(re.match(pattern, text))
    return regex_match


def catch_all_condition() -> Condition:
    def always_true(_: str) -> bool:
        return True
    return always_true


# Common Conditions
condition_ping = lower_match_factory('ping')
condition_catch_all = catch_all_condition()
