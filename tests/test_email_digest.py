from pipeline.email_digest import score_episodes

def make_chunk(id, title, podcast, weight=1.0):
    return {
        "id": id,
        "episode_title": title,
        "podcast_name": podcast,
        "chunk_text": "and that is where I think we will see agentic systems really impact the enterprise",
        "weight": weight,
    }

class TestScoreEpisodes:
    def test_counts_chunks_per_episode(self):
        chunks = [
            make_chunk("1", "Intro to AI Engineering", "The AI Daily Brief"),
            make_chunk("2", "Intro to AI Engineering", "The AI Daily Brief"),
            make_chunk("3", "RAG vs Fine-Tuning in 2025", "DataFramed"),
        ]
        result = score_episodes(chunks)
        assert result["Intro to AI Engineering"]["score"] == 2.0
        assert result["RAG vs Fine-Tuning in 2025"]["score"] == 1.0

    def test_sorted_highest_first(self):
        chunks = [
            make_chunk("1", "RAG vs Fine-Tuning in 2025", "DataFramed"),
            make_chunk("2", "Intro to AI Engineering", "The AI Daily Brief"),
            make_chunk("3", "Intro to AI Engineering", "The AI Daily Brief"),
        ]
        result = score_episodes(chunks)
        assert list(result.keys())[0] == "Intro to AI Engineering"
        assert list(result.keys())[1] == "RAG vs Fine-Tuning in 2025"

    def test_double_weighted_queries_score_higher(self):
        chunks = [
            make_chunk("1", "AI in Drug Discovery", "The Readout Loud", weight=2.0),
            make_chunk("2", "State of LLMs", "How I AI", weight=1.0),
        ]
        result = score_episodes(chunks)
        assert result["AI in Drug Discovery"]["score"] == 2.0
        assert result["State of LLMs"]["score"] == 1.0

    def test_empty_chunks_returns_empty(self):
        assert score_episodes([]) == {}

    def test_excerpts_truncated_to_300_chars(self):
        long_chunk = make_chunk("1", "Intro to AI Engineering", "The AI Daily Brief")
        long_chunk["chunk_text"] = "x" * 400
        result = score_episodes([long_chunk])
        assert len(result["Intro to AI Engineering"]["excerpts"][0]) == 300