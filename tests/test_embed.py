from pipeline.embed import chunk_text, parse_filename

class TestChunkText:
    def test_basic_split(self):
        # 10 word transcript snippet split into two chunks of 5
        text = "so today we are going to talk about building agents"
        chunks = chunk_text(text, chunk_size=5, overlap=0)
        assert len(chunks) == 2
        assert chunks[0] == "so today we are going"

    def test_overlap_repeats_words(self):
        text = "agents can use tools to search the web and retrieve documents"
        chunks = chunk_text(text, chunk_size=4, overlap=2)
        assert chunks[0] == "agents can use tools"
        assert chunks[1] == "use tools to search"
        assert "use" in chunks[0] and "use" in chunks[1]

    def test_empty_transcript(self):
        assert chunk_text("", chunk_size=500, overlap=50) == []

    def test_short_transcript_fits_in_one_chunk(self):
        text = "This episode covers the basics of vector embeddings"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

class TestParseFilename:
    def test_standard_format(self):
        podcast_id, title = parse_filename("ai_daily_brief__Claude_4_Is_Here.txt")
        assert podcast_id == "ai_daily_brief"
        assert title == "Claude 4 Is Here"

    def test_no_double_underscore_returns_full_name(self):
        podcast_id, title = parse_filename("dataframed.txt")
        assert podcast_id == "dataframed"
        assert title == "dataframed"

    def test_underscores_in_title_become_spaces(self):
        _, title = parse_filename("how_i_ai__Building_RAG_From_Scratch.txt")
        assert title == "Building RAG From Scratch"
