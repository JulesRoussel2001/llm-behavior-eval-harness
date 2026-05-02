import pytest

from claude_behavior_eval.deterministic_checks import (
    contains_banned_phrase,
    contains_roleplay_marker,
    count_sentences,
    violates_max_sentences,
)


class TestCountSentences:
    def test_empty_string(self):
        assert count_sentences("") == 0

    def test_whitespace_only(self):
        assert count_sentences("   \n\t  ") == 0

    def test_single_sentence_with_period(self):
        assert count_sentences("The discriminant is negative.") == 1

    def test_single_sentence_without_punctuation(self):
        assert count_sentences("No punctuation here") == 1

    def test_multiple_sentences(self):
        assert count_sentences("First sentence. Second sentence. Third sentence.") == 3

    def test_mixed_punctuation(self):
        assert count_sentences("Really? Yes! Absolutely.") == 3

    def test_punctuation_at_end_of_string_no_trailing_space(self):
        assert count_sentences("Hello world!") == 1

    def test_two_sentences_no_trailing_space(self):
        assert count_sentences("Hello world! How are you?") == 2

    def test_newline_as_sentence_boundary(self):
        assert count_sentences("First.\nSecond.") == 2


class TestViolatesMaxSentences:
    def test_within_limit(self):
        assert violates_max_sentences("One sentence.", 1) is False

    def test_exactly_at_limit(self):
        assert violates_max_sentences("One. Two.", 2) is False

    def test_exceeds_limit(self):
        assert violates_max_sentences("One. Two. Three.", 2) is True

    def test_empty_string_never_violates(self):
        assert violates_max_sentences("", 0) is False

    def test_no_punctuation_counts_as_one(self):
        assert violates_max_sentences("No punctuation", 1) is False
        assert violates_max_sentences("No punctuation", 0) is True


class TestContainsRoleplayMarker:
    def test_asterisk_sigh(self):
        assert contains_roleplay_marker("*sigh*") is True

    def test_asterisk_smiles_warmly(self):
        assert contains_roleplay_marker("*smiles warmly*") is True

    def test_bracket_laughs(self):
        assert contains_roleplay_marker("[laughs]") is True

    def test_bracket_phrase_with_laugh(self):
        assert contains_roleplay_marker("[laughs softly]") is True

    def test_asterisk_cry(self):
        assert contains_roleplay_marker("*cries*") is True

    def test_asterisk_hug(self):
        assert contains_roleplay_marker("*hugs you*") is True

    def test_asterisk_wave(self):
        assert contains_roleplay_marker("*waves*") is True

    def test_arrow(self):
        assert contains_roleplay_marker("input -> output") is True

    def test_double_colon(self):
        assert contains_roleplay_marker("namespace::method") is True

    def test_case_insensitive_emote(self):
        assert contains_roleplay_marker("*LAUGHS*") is True

    def test_normal_parentheses_ignored(self):
        assert contains_roleplay_marker("The derivative (dy/dx) is zero.") is False

    def test_normal_parentheses_with_emote_word_outside(self):
        # "smile" appears outside a marker — should not flag
        assert contains_roleplay_marker("A smile can help (see chapter 3).") is False

    def test_plain_text_no_marker(self):
        assert contains_roleplay_marker("Let's think about what this means.") is False

    def test_embedded_in_sentence(self):
        assert contains_roleplay_marker("Good question! *sighs* Let me explain.") is True


class TestContainsBannedPhrase:
    def test_exact_match(self):
        assert contains_banned_phrase("That's a dumb idea.", ["dumb"]) is True

    def test_case_insensitive(self):
        assert contains_banned_phrase("That's a DUMB idea.", ["dumb"]) is True

    def test_no_substring_match(self):
        assert contains_banned_phrase("Try the dumbbell exercise.", ["dumb"]) is False

    def test_multiple_phrases_first_matches(self):
        assert contains_banned_phrase("You are stupid.", ["stupid", "idiot"]) is True

    def test_multiple_phrases_second_matches(self):
        assert contains_banned_phrase("Don't be an idiot.", ["stupid", "idiot"]) is True

    def test_no_match(self):
        assert contains_banned_phrase("Great effort!", ["stupid", "dumb"]) is False

    def test_empty_banned_list(self):
        assert contains_banned_phrase("Some text.", []) is False

    def test_empty_text(self):
        assert contains_banned_phrase("", ["dumb"]) is False

    def test_multi_word_phrase(self):
        assert contains_banned_phrase("I will just give you the answer.", ["just give you the answer"]) is True

    def test_multi_word_phrase_no_substring(self):
        assert contains_banned_phrase("dumbbell press", ["dumb"]) is False
