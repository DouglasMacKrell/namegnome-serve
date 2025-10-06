#!/usr/bin/env python3
"""LangChain ↔ Ollama sanity check.

Verifies that LangChain can successfully communicate with the local
Ollama service and the custom namegnome model.
"""

from langchain_ollama import OllamaLLM


def main() -> None:
    """Test LangChain integration with Ollama."""
    print("🧪 LangChain ↔ Ollama Sanity Check\n")

    # Initialize Ollama LLM with namegnome model
    print("Initializing Ollama LLM with 'namegnome' model...")
    llm = OllamaLLM(model="namegnome", temperature=0.3)

    # Test prompt
    prompt = "You are NameGnome's assistant. Reply with only 'OK' if you can hear me."

    print(f"\nPrompt: {prompt}")
    print("\nWaiting for response...")

    try:
        response = llm.invoke(prompt)
        print(f"\n✅ Response received:\n{response}\n")

        if "OK" in response.upper():
            print("✅ LangChain ↔ Ollama integration working correctly!")
            return
        else:
            print("⚠️  Model responded but didn't say 'OK' - may need prompt tuning")
            return

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure Ollama is running: ollama serve")
        print("  2. Verify model exists: ollama list")
        print("  3. Create model if missing:")
        print("     ollama create namegnome -f models/namegnome/Modelfile")
        raise


if __name__ == "__main__":
    main()
