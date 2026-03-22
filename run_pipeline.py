import fetch_audio
import transcribe
import embed
import email_digest

def main():
    print("=== Step 1: Fetch ===")
    fetch_audio.main()

    print("\n=== Step 2: Transcribe ===")
    transcribe.main()

    print("\n=== Step 3: Embed ===")
    embed.main()

    print("\n=== Step 4: Email digest ===")
    email_digest.generate_digest()

if __name__ == "__main__":
    main()