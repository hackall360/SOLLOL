#!/usr/bin/env python3
"""
Test script for batch API endpoints.
Tests all batch API functionality.
"""

import requests
import time
import json

BASE_URL = "http://localhost:23000"


def test_batch_embed_api():
    """Test batch embedding API."""
    print("\n🧪 Testing Batch Embed API...")

    # Submit batch job
    response = requests.post(
        f"{BASE_URL}/api/batch/embed",
        json={
            "model": "nomic-embed-text",
            "documents": ["test doc 1", "test doc 2", "test doc 3"],
        },
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert "job_id" in data
    assert data["status"] == "running"
    assert data["total_items"] == 3

    job_id = data["job_id"]
    print(f"   ✅ Job submitted: {job_id}")

    return job_id


def test_get_job_status(job_id):
    """Test getting job status."""
    print(f"\n🧪 Testing Get Job Status API...")

    time.sleep(2)  # Wait for job to complete

    response = requests.get(f"{BASE_URL}/api/batch/jobs/{job_id}")
    assert response.status_code == 200

    data = response.json()
    print(f"   ✅ Job status: {data['status']}")
    print(f"   ✅ Progress: {data['progress']['percent']}%")
    print(f"   ✅ Duration: {data['duration_seconds']:.3f}s")

    return data


def test_get_job_results(job_id):
    """Test getting job results."""
    print(f"\n🧪 Testing Get Job Results API...")

    response = requests.get(f"{BASE_URL}/api/batch/results/{job_id}")
    assert response.status_code == 200

    data = response.json()
    print(f"   ✅ Got results for {data['total_items']} items")
    print(f"   ✅ Completed: {data['completed_items']}, Failed: {data['failed_items']}")

    return data


def test_list_jobs():
    """Test listing jobs."""
    print(f"\n🧪 Testing List Jobs API...")

    response = requests.get(f"{BASE_URL}/api/batch/jobs?limit=10")
    assert response.status_code == 200

    data = response.json()
    print(f"   ✅ Found {data['total']} jobs")

    for job in data["jobs"][:3]:
        print(f"      - {job['job_id']}: {job['status']} ({job['progress']['percent']}%)")

    return data


def test_cancel_job():
    """Test cancelling a job."""
    print(f"\n🧪 Testing Cancel Job API...")

    # Submit a new job
    response = requests.post(
        f"{BASE_URL}/api/batch/embed",
        json={
            "model": "nomic-embed-text",
            "documents": ["cancel test"] * 100,  # Larger job
        },
    )
    job_id = response.json()["job_id"]

    # Try to cancel immediately (might be too late if job completes fast)
    response = requests.delete(f"{BASE_URL}/api/batch/jobs/{job_id}")

    # Could be 200 (cancelled) or 404 (already completed)
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        print(f"   ✅ Job {job_id} cancelled")
    else:
        print(f"   ✅ Job {job_id} already completed (too fast to cancel)")


def test_stats_endpoint():
    """Test that batch stats are exposed."""
    print(f"\n🧪 Testing Stats Endpoint (Batch Jobs)...")

    response = requests.get(f"{BASE_URL}/api/stats")
    assert response.status_code == 200

    data = response.json()
    assert "batch_jobs" in data

    batch_stats = data["batch_jobs"]
    print(f"   ✅ Total jobs created: {batch_stats['total_jobs_created']}")
    print(f"   ✅ Total completed: {batch_stats['total_jobs_completed']}")
    print(f"   ✅ Active jobs: {batch_stats['active_jobs']}")


def main():
    print("=" * 70)
    print("🧪 SOLLOL Batch API Test Suite")
    print("=" * 70)

    try:
        # Check if gateway is running
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        if response.status_code != 200:
            print("\n❌ Gateway not running on port 23000")
            print("   Start with: sollol up --port 23000 --ray-workers 1 --dask-workers 2")
            return 1

        print(f"\n✅ Gateway running (version {response.json()['version']})")

        # Run tests
        job_id = test_batch_embed_api()
        test_get_job_status(job_id)
        test_get_job_results(job_id)
        test_list_jobs()
        test_cancel_job()
        test_stats_endpoint()

        print("\n" + "=" * 70)
        print("✅ All batch API tests passed!")
        print("=" * 70)
        print("\nBatch API endpoints working:")
        print("  • POST /api/batch/embed - Submit batch embedding job")
        print("  • GET /api/batch/jobs/{job_id} - Get job status")
        print("  • GET /api/batch/results/{job_id} - Get job results")
        print("  • GET /api/batch/jobs - List jobs")
        print("  • DELETE /api/batch/jobs/{job_id} - Cancel job")
        print("  • GET /api/stats - Includes batch_jobs stats")

        return 0

    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to gateway on port 23000")
        print("   Start with: sollol up --port 23000 --ray-workers 1 --dask-workers 2")
        return 1
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
