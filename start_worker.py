#!/usr/bin/env python3
"""
Analytics Worker Runner

This script starts the asynchronous analytics worker that processes
click data from RabbitMQ and updates MongoDB with analytics information.
"""

import sys
import os
import asyncio

# Ensure project root is on the path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

from workers.stats_worker import StatsWorker  # noqa: E402


def main():
    """Main function to start the analytics worker"""
    print("=" * 60)
    print("🚀 Starting Spoo.me Shortener Stats Worker")
    print("=" * 60)
    print("This worker will process click analytics asynchronously")
    print("and update MongoDB with detailed statistics.")
    print()

    try:
        # Run the async worker entrypoint
        asyncio.run(StatsWorker())
    except KeyboardInterrupt:
        print("\n👋 Worker stopped by user")
    except Exception as e:
        print(f"\n❌ Worker failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
