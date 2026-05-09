import fetch_audio
import transcribe
import embed
import email_digest
import check_data_quality
import rag_eval

def main():
    print("=== Step 1: Fetch ===")
    fetch_audio.main()

    print("\n=== Step 2: Transcribe ===")
    transcribe.main()

    print("\n=== Step 3: Embed ===")
    embed.main()

    print("\n=== Step 4: Data quality checks ===")
    check_data_quality.run_all_checks()

    print("\n=== Step 5: Email digest ===")
    email_digest.generate_digest()

    print("\n=== Step 6: Eval ===")
    rag_eval.eval_context_precision()
    rag_eval.print_summary()

if __name__ == "__main__":
    main()