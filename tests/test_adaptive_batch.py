"""Adaptive Batch Processing Test — validate multiple corridors with real tools.

Tests the AdaptiveBatchProcessor against real drone corridor operations:
- Creates multiple corridors
- Validates each one
- Processes results adaptively (sample → classify → process)

Run: python tests/test_adaptive_batch.py
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/autoai-mini/Documents/axplusb/auto-ai-agent-framework/agent-framework-pypi/src')

os.environ.setdefault('AWS_REGION', 'us-east-1')

from app.sdk_agent.tools.simulation import drone_tools
from app.sdk_agent.tools.corridor import management
from app.sdk_agent.tools.compliance import ledger_tools
from app.sdk_agent.tools.registry import execute_tool

from agent_framework.composable.batch_processing.adaptive import (
    AdaptiveBatchProcessor, AdaptiveBatchConfig,
)


# Define corridor specs to validate
CORRIDORS = [
    {"name": "Delhi-Agra", "start_lat": 28.6139, "start_lon": 77.2090, "end_lat": 27.1767, "end_lon": 78.0081},
    {"name": "Mumbai-Pune", "start_lat": 19.0760, "start_lon": 72.8777, "end_lat": 18.5204, "end_lon": 73.8567},
    {"name": "Chennai-Bangalore", "start_lat": 13.0827, "start_lon": 80.2707, "end_lat": 12.9716, "end_lon": 77.5946},
    {"name": "Kolkata-Bhubaneswar", "start_lat": 22.5726, "start_lon": 88.3639, "end_lat": 20.2961, "end_lon": 85.8245},
    {"name": "Hyderabad-Vijayawada", "start_lat": 17.3850, "start_lon": 78.4867, "end_lat": 16.5062, "end_lon": 80.6480},
    {"name": "Jaipur-Udaipur", "start_lat": 26.9124, "start_lon": 75.7873, "end_lat": 24.5854, "end_lon": 73.7125},
    {"name": "Lucknow-Varanasi", "start_lat": 26.8467, "start_lon": 80.9462, "end_lat": 25.3176, "end_lon": 82.9739},
    {"name": "Ahmedabad-Surat", "start_lat": 23.0225, "start_lon": 72.5714, "end_lat": 21.1702, "end_lon": 72.8311},
    {"name": "BadRoute-TooShort", "start_lat": 28.6139, "start_lon": 77.2090, "end_lat": 28.6140, "end_lon": 77.2091},  # Too short
    {"name": "Patna-Ranchi", "start_lat": 25.6093, "start_lon": 85.1376, "end_lat": 23.3441, "end_lon": 85.3096},
]


def process_corridor(corridor_spec, context_hint=None):
    """Create and validate a single corridor."""
    try:
        # Create
        result = execute_tool("create_corridor", {
            "name": corridor_spec["name"],
            "start_lat": corridor_spec["start_lat"],
            "start_lon": corridor_spec["start_lon"],
            "end_lat": corridor_spec["end_lat"],
            "end_lon": corridor_spec["end_lon"],
            "resolution": 10,
        })

        if "error" in result:
            return {"success": False, "error": result["error"], "corridor": corridor_spec["name"]}

        corridor_id = result["corridor_id"]
        block_count = result["block_count"]

        # Validate
        validation = execute_tool("validate_corridor", {"corridor_id": corridor_id})
        is_valid = validation.get("valid", False)
        issues = validation.get("issues", [])

        return {
            "success": is_valid,
            "corridor_id": corridor_id,
            "name": corridor_spec["name"],
            "blocks": block_count,
            "distance_km": validation.get("estimated_distance_km", 0),
            "issues": issues,
            "error": "; ".join(issues) if not is_valid else None,
            "tokens": 200,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "corridor": corridor_spec["name"]}


async def main():
    print("=" * 70)
    print("ADAPTIVE BATCH TEST: Validate 10 Drone Corridors")
    print("=" * 70)

    config = AdaptiveBatchConfig(
        sample_size=3,
        checkpoint_interval=5,
        simple_threshold=0.8,
        broken_threshold=0.2,
        detect_patterns=True,
        inject_fixes=True,
    )

    processor = AdaptiveBatchProcessor(
        process_fn=process_corridor,
        config=config,
    )

    start = time.time()

    async for event in processor.process(CORRIDORS):
        if event.type == "sample_complete":
            print(f"\n  [SAMPLE] {event.data}")
        elif event.type == "classification_complete":
            print(f"  [CLASSIFY] {event.data}")
        elif event.type == "item_complete":
            print(f"  [PROGRESS] {event.data['percent']:.0f}% ({event.data['index']}/{event.data['total']})")
        elif event.type == "checkpoint":
            print(f"  [CHECKPOINT] {event.data}")
        elif event.type == "complete":
            result = event.data["result"]

            elapsed = time.time() - start
            print(f"\n{'='*70}")
            print(f"BATCH COMPLETE")
            print(f"{'='*70}")
            print(f"  Total items: {result.total_items}")
            print(f"  Processed: {result.processed}")
            print(f"  Successful: {result.successful}")
            print(f"  Failed: {result.failed}")
            print(f"  Success rate: {result.success_rate:.0%}")
            print(f"  Manual review: {len(result.manual_review)}")
            print(f"  Duration: {elapsed:.2f}s")
            print(f"  Tokens: {result.total_tokens:,}")
            print(f"  Checkpoints: {result.checkpoints_saved}")
            print(f"  Detected fixes: {len(result.detected_fixes)}")

            if result.detected_fixes:
                print(f"\n  Patterns detected:")
                for fix in result.detected_fixes:
                    print(f"    - {fix.error_pattern[:60]} (rate: {fix.success_rate:.0%})")

            if result.manual_review:
                print(f"\n  Manual review items:")
                for item in result.manual_review:
                    print(f"    - {item.get('item_id')}: {item.get('error', '?')[:60]}")

            print(f"\n  Report:\n")
            print(result.to_report())

            # Assertions
            assert result.total_items == 10
            assert result.processed == 10
            assert result.successful >= 8  # Most corridors should be valid
            print(f"\n  Test PASS!")


if __name__ == "__main__":
    asyncio.run(main())
