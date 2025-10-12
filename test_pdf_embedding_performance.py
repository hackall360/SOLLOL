#!/usr/bin/env python3
"""
Test batch embedding performance on real PDFs with connection reuse optimization.

This test validates the performance improvement from HTTP connection reuse
when processing large documents.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/joker/SOLLOL/src")

from sollol import OllamaPool

try:
    from PyPDF2 import PdfReader
except ImportError:
    print("❌ PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    print(f"📄 Reading PDF: {Path(pdf_path).name}")

    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n\n"

        print(f"   ✅ Extracted {len(text)} characters from {len(reader.pages)} pages")
        return text
    except Exception as e:
        print(f"   ❌ Error reading PDF: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 500) -> list:
    """Split text into chunks of approximately chunk_size characters."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_size + word_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_size = word_len
        else:
            current_chunk.append(word)
            current_size += word_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def test_pdf_embedding():
    """Test embedding performance on real PDF document."""
    print("=" * 80)
    print("SOLLOL PDF Embedding Performance Test")
    print("With HTTP Connection Reuse Optimization")
    print("=" * 80)

    # Select PDF to test
    pdf_path = "/home/joker/FlockParser/testpdfs/quantum_info_majorana_2023.pdf"

    if not Path(pdf_path).exists():
        print(f"❌ PDF not found: {pdf_path}")
        return False

    # Extract text
    print(f"\n📖 Step 1: Extract text from PDF")
    text = extract_text_from_pdf(pdf_path)

    if not text or len(text) < 100:
        print("❌ Failed to extract sufficient text from PDF")
        return False

    # Chunk text
    print(f"\n✂️  Step 2: Split into chunks")
    chunks = chunk_text(text, chunk_size=500)
    print(f"   ✅ Created {len(chunks)} chunks (~500 chars each)")

    # Limit to reasonable number for testing
    test_chunks = chunks[:50]  # Test with first 50 chunks
    print(f"   🧪 Testing with first {len(test_chunks)} chunks")

    # Create pool
    print(f"\n📦 Step 3: Initialize OllamaPool")
    pool = OllamaPool.auto_configure()

    if not pool.nodes:
        print("❌ No Ollama nodes found")
        return False

    print(f"   ✅ Found {len(pool.nodes)} nodes:")
    for node in pool.nodes:
        print(f"      → {node['host']}:{node['port']}")

    # Verify connection reuse is enabled
    if not hasattr(pool, 'session'):
        print("   ⚠️  WARNING: Session not found (connection reuse may not be working)")
    else:
        print(f"   ✅ Connection reuse enabled (session type: {type(pool.session).__name__})")

    # Test sequential embeddings
    print(f"\n🚀 Step 4: Generate embeddings ({len(test_chunks)} chunks)")
    print("   (Connection reuse should eliminate TCP handshake overhead)")

    start_time = time.time()
    successful = 0
    failed = 0

    for i, chunk in enumerate(test_chunks, 1):
        try:
            result = pool.embed(model="mxbai-embed-large", input=chunk)
            if 'embeddings' in result or 'embedding' in result:
                successful += 1
                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    print(f"   📊 Progress: {i}/{len(test_chunks)} ({rate:.1f} chunks/sec)")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"   ⚠️  Chunk {i} failed: {e}")

    total_time = time.time() - start_time

    # Results
    print(f"\n" + "=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print(f"Document: {Path(pdf_path).name}")
    print(f"Total chunks: {len(test_chunks)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nPerformance:")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Avg per chunk: {(total_time/len(test_chunks))*1000:.1f}ms")
    print(f"  Throughput: {len(test_chunks)/total_time:.1f} chunks/sec")

    # Pool stats
    stats = pool.get_stats()
    print(f"\nPool Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Successful: {stats['successful_requests']}")
    print(f"  Failed: {stats['failed_requests']}")
    print(f"  Success rate: {(stats['successful_requests']/stats['total_requests']*100):.1f}%")

    # Connection reuse savings estimate
    handshake_overhead_ms = 15  # Typical TCP + TLS overhead
    saved_time = (len(test_chunks) - 1) * handshake_overhead_ms / 1000
    print(f"\n💰 Connection Reuse Savings:")
    print(f"  Estimated overhead saved: {saved_time:.1f}s")
    print(f"  ({len(test_chunks)-1} connections × {handshake_overhead_ms}ms)")

    # Performance assessment
    avg_ms = (total_time / len(test_chunks)) * 1000
    print(f"\n🎯 Performance Assessment:")
    if avg_ms < 100:
        print(f"  ✅ EXCELLENT - {avg_ms:.0f}ms per chunk (optimal)")
    elif avg_ms < 200:
        print(f"  ✅ GOOD - {avg_ms:.0f}ms per chunk")
    elif avg_ms < 500:
        print(f"  ⚠️  ACCEPTABLE - {avg_ms:.0f}ms per chunk")
    else:
        print(f"  ⚠️  SLOW - {avg_ms:.0f}ms per chunk (may need optimization)")

    # Cleanup
    print(f"\n🧹 Cleaning up...")
    pool.stop()

    print("=" * 80)
    print("✅ Test complete!")
    print("=" * 80)

    return successful > 0


if __name__ == "__main__":
    try:
        success = test_pdf_embedding()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
