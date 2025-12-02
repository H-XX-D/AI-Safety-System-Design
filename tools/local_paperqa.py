#!/usr/bin/env python3
"""
Local PaperQA Setup for AI Safety System Documentation

This script indexes the AI Safety System documentation using a local
llama.cpp server (no external API calls - fully self-contained).

Usage:
    python tools/local_paperqa.py ask "What is the deception detection system?"
    python tools/local_paperqa.py index
    python tools/local_paperqa.py interactive
"""

import asyncio
import os
import sys
import glob
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configuration for local llama.cpp server
LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8080/v1")
LLAMA_MODEL_NAME = os.environ.get("LLAMA_MODEL_NAME", "phi-3.5-mini")

# Directories to index
DOCS_DIRS = [
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "assessments", 
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "ui" / "README.md",
]

# File extensions to include
INCLUDE_EXTENSIONS = {".md", ".txt", ".py", ".yaml", ".yml"}


def get_doc_files() -> list[Path]:
    """Get all documentation files to index."""
    files = []
    
    for doc_path in DOCS_DIRS:
        if doc_path.is_file():
            files.append(doc_path)
        elif doc_path.is_dir():
            for ext in INCLUDE_EXTENSIONS:
                files.extend(doc_path.glob(f"**/*{ext}"))
    
    # Also include key Python files for code documentation
    key_files = [
        "orchestrator.py",
        "research_system.py", 
        "deception_detector.py",
        "alignment_filter.py",
        "worm_manifest.py",
        "memory_merkle.py",
        "debate_engine.py",
        "ui/app.py",
        "ui/data_store.py",
    ]
    
    for f in key_files:
        path = PROJECT_ROOT / f
        if path.exists():
            files.append(path)
    
    return list(set(files))  # Remove duplicates


async def setup_paperqa():
    """Set up PaperQA with local llama.cpp backend."""
    try:
        from paperqa import Docs, Settings
    except ImportError:
        print("PaperQA not installed. Installing...")
        os.system(f"{sys.executable} -m pip install paper-qa")
        from paperqa import Docs, Settings
    
    # Configure for local llama.cpp server
    local_llm_config = {
        "model_list": [
            {
                "model_name": LLAMA_MODEL_NAME,
                "litellm_params": {
                    "model": f"openai/{LLAMA_MODEL_NAME}",
                    "api_base": LLAMA_SERVER_URL,
                    "api_key": "sk-no-key-required",
                    "temperature": 0.1,
                    "max_tokens": 1024,
                },
            }
        ]
    }
    
    settings = Settings(
        llm=LLAMA_MODEL_NAME,
        llm_config=local_llm_config,
        summary_llm=LLAMA_MODEL_NAME,
        summary_llm_config=local_llm_config,
        # Use sparse embeddings (no external embedding API needed)
        embedding="sparse",
    )
    
    return Docs(), settings


async def index_docs(docs, settings):
    """Index all documentation files."""
    files = get_doc_files()
    print(f"\n📚 Indexing {len(files)} documentation files...\n")
    
    for i, filepath in enumerate(files, 1):
        try:
            relative_path = filepath.relative_to(PROJECT_ROOT)
            print(f"  [{i}/{len(files)}] {relative_path}")
            
            # Create citation from filepath
            citation = f"AI Safety System - {relative_path}"
            docname = str(relative_path)
            
            await docs.aadd(
                str(filepath),
                citation=citation,
                docname=docname,
                settings=settings,
            )
        except Exception as e:
            print(f"    ⚠️  Error indexing {filepath}: {e}")
    
    print(f"\n✅ Indexed {len(files)} files successfully!")
    return docs


async def ask_question(docs, settings, question: str):
    """Ask a question about the documentation."""
    print(f"\n🔍 Question: {question}\n")
    print("=" * 60)
    
    try:
        session = await docs.aquery(question, settings=settings)
        print(f"\n📖 Answer:\n{session.answer}\n")
        print("=" * 60)
        
        if session.contexts:
            print("\n📚 Sources:")
            for ctx in session.contexts[:5]:
                print(f"  - {ctx.text.doc.docname}")
        
        return session
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def interactive_mode(docs, settings):
    """Run interactive Q&A session."""
    print("\n" + "=" * 60)
    print("🤖 AI Safety System Documentation Q&A")
    print("=" * 60)
    print("Ask questions about the AI Safety System.")
    print("Type 'quit' or 'exit' to stop.\n")
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if question.lower() in ("quit", "exit", "q"):
                print("\n👋 Goodbye!")
                break
            
            if not question:
                continue
            
            await ask_question(docs, settings, question)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            break


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Local PaperQA for AI Safety System Documentation"
    )
    parser.add_argument(
        "command",
        choices=["ask", "index", "interactive", "info"],
        help="Command to run"
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Question to ask (for 'ask' command)"
    )
    
    args = parser.parse_args()
    
    if args.command == "info":
        print("\n📊 AI Safety System Documentation Index Info")
        print("=" * 50)
        files = get_doc_files()
        print(f"Files to index: {len(files)}")
        for f in files[:20]:
            print(f"  - {f.relative_to(PROJECT_ROOT)}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        print(f"\nLlama server: {LLAMA_SERVER_URL}")
        print(f"Model: {LLAMA_MODEL_NAME}")
        return
    
    # Check if llama server is running
    import urllib.request
    try:
        urllib.request.urlopen(f"{LLAMA_SERVER_URL.replace('/v1', '')}/health", timeout=2)
    except Exception:
        print("❌ Llama server not running at", LLAMA_SERVER_URL)
        print("Start it with:")
        print('  llama-server -m "/Volumes/Thunderbolt SSD/Models/Phi-3.5-mini-instruct-Q4_K_M.gguf" -c 4096 --embedding --port 8080')
        sys.exit(1)
    
    print("✅ Llama server is running")
    
    # Set up PaperQA
    docs, settings = await setup_paperqa()
    
    # Index documents
    docs = await index_docs(docs, settings)
    
    if args.command == "ask":
        if not args.question:
            print("❌ Please provide a question")
            sys.exit(1)
        await ask_question(docs, settings, args.question)
    
    elif args.command == "interactive":
        await interactive_mode(docs, settings)
    
    elif args.command == "index":
        print("✅ Indexing complete!")


if __name__ == "__main__":
    asyncio.run(main())




