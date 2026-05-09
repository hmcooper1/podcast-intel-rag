from fetch_audio import sanitize_filename, strip_html, parse_duration

class TestSanitizeFilename:
    def test_removes_special_chars(self):
        assert sanitize_filename("How I AI: Using OpenClaw (2026)") == "How_I_AI_Using_OpenClaw_2026"

    def test_replaces_spaces_with_underscores(self):
        assert sanitize_filename("The AI Daily Brief") == "The_AI_Daily_Brief"

    def test_keeps_hyphens(self):
        assert sanitize_filename("Lex Fridman - Episode 400") == "Lex_Fridman_-_Episode_400"

    def test_empty_string(self):
        assert sanitize_filename("") == ""

class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Transcript</p><b>available</b>") == "Transcript available"

    def test_plain_text_unchanged(self):
        assert strip_html("This week on the show we discuss RAG pipelines") == "This week on the show we discuss RAG pipelines"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_nested_tags(self):
        result = strip_html("<div><p>OpenAI</p><p>released GPT-5</p></div>")
        assert "OpenAI" in result
        assert "released GPT-5" in result

class TestParseDuration:
    def test_raw_seconds(self):
        assert parse_duration("3600") == 3600

    def test_hhmmss_format(self):
        assert parse_duration("1:23:45") == 5025

    def test_mmss_format(self):
        assert parse_duration("45:30") == 2730

    def test_none_returns_none(self):
        assert parse_duration(None) is None

    def test_empty_string_returns_none(self):
        assert parse_duration("") is None
