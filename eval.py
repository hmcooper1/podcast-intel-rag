import os
from dotenv import load_dotenv
from supabase import create_client
from ragas import evaluate
from ragas.metrics import LLMContextPrecisionWithoutReference
from ragas.dataset_schema import SingleTurnSample, EvaluationDataset

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# RAGAS uses gpt-4o-mini as judge by default via your OPENAI_API_KEY — cheap (~$0.02/run)

def eval_context_precision():
    """
    Context precision: how relevant are the retrieved chunks to each query.
    Score for runs that haven't been scored yet. 
    One per query - four per run.
    """
    # list of dicts with one row from supabase table (id, run date, query, contexts, contexts_precision)
    query_runs = supabase.table("eval_query_runs").select("*").is_("context_precision", "null").execute()

    if not query_runs.data:
        print("No unscored eval_query_runs found.")
        return

    print(f"Scoring context precision for {len(query_runs.data)} query run(s)...")

    # each qrun contains dict with query and contexts for that query
    for qrun in query_runs.data:
        # ragas class that represents one evaluation ex (holds input, response, context)
        sample = SingleTurnSample(
            user_input=qrun["query"],
            # placeholder because response is required for metric but not relevant
            response="Podcast episodes relevant to this query.",
            retrieved_contexts=qrun["contexts"],
        )

        dataset = EvaluationDataset(samples=[sample])
        # without reference bc uses llm as a judge
        result = evaluate(dataset, metrics=[LLMContextPrecisionWithoutReference])

        score = result["llm_context_precision_without_reference"]
        # write context precision score back to supabase table
        supabase.table("eval_query_runs").update({"context_precision": score}).eq("id", qrun["id"]).execute()
        print(f"  {qrun['run_date']} | '{qrun['query'][:50]}': {score:.2f}")


def print_summary():
    """
    Print context precision scores over time so you can track whether
    retrieval quality improves after changing queries, chunk size, etc.
    """
    query_runs = supabase.table("eval_query_runs").select(
        "run_date, query, context_precision"
    ).not_.is_("context_precision", "null").order("run_date").execute()

    if not query_runs.data:
        print("No scored runs yet.")
        return

    print("\n=== Context Precision by Query ===")
    # group by query so you can see each query's score trend over time
    by_query = {}
    for qrun in query_runs.data:
        q = qrun["query"]
        if q not in by_query:
            by_query[q] = []
        by_query[q].append((qrun["run_date"], qrun["context_precision"]))

    for query, scores in by_query.items():
        print(f"\n{query}")
        for date, score in scores:
            print(f"  {date}: {score:.2f}")


if __name__ == "__main__":
    eval_context_precision()
    print_summary()
