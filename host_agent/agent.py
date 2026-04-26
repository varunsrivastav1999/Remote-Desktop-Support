#!/usr/bin/env python3
"""
agent.py — Remote Desktop Host Agent

This is the main entry point for the host agent. It:
  1. Creates a remote support session on the signaling server
  2. Displays the session code for the user to share
  3. Waits for a support technician to connect
  4. Streams the screen via WebRTC
  5. Executes remote mouse/keyboard commands

Usage:
    python agent.py --server http://localhost:8000
    python agent.py --server http://localhost:8000 --fps 60 --monitor 1

Requirements:
    pip install -r requirements.txt
"""

import argparse
import asyncio
import logging
import platform
import socket
import sys

from signaling_client import SignalingClient

# ─── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('remote_desktop.agent')

# ─── Banner ───────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ◈  R E M O T E  D E S K T O P  —  Host Agent          ║
║                                                              ║
║     Remote Desktop Support · Powered by WebRTC               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


import uuid

def get_host_identifier() -> str:
    """Get a unique, permanent identifier for this machine."""
    # Use the hardware MAC address as a unique seed
    hw_id = hex(uuid.getnode())
    hostname = socket.gethostname()
    return f"{hostname}-{hw_id}"


async def main(args):
    """Main async entry point."""
    if not args.silent:
        print(BANNER)

    host_id = get_host_identifier()
    if not args.silent:
        logger.info(f"Host: {host_id}")
        logger.info(f"Server: {args.server}")
        logger.info(f"FPS: {args.fps} | Monitor: {args.monitor}")
        print()

    # Create the signaling client
    client = SignalingClient(
        server_url=args.server,
        fps=args.fps,
        monitor=args.monitor,
    )

    # Create a session
    try:
        session_code = await client.create_session(host_identifier=host_id)
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        logger.error("Is the signaling server running? Check the --server URL.")
        sys.exit(1)

    # Display the session code
    print("┌─────────────────────────────────────────────┐")
    print("│                                             │")
    print(f"│   Session Code:  {session_code}           │")
    print("│                                             │")
    print("│   Share this code with the support tech.    │")
    print("│   They will enter it in the web client.     │")
    print("│                                             │")
    print("│   Waiting for connection...                 │")
    print("│   Press Ctrl+C to stop.                     │")
    print("│                                             │")
    print("└─────────────────────────────────────────────┘")
    print()

    # Connect and serve
    try:
        await client.connect_and_serve()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client._cleanup()
        logger.info("Agent stopped.")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Remote Desktop Host Agent — share your screen for remote support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py --server http://localhost:8000
  python agent.py --server https://support.example.com --fps 60
  python agent.py --server http://192.168.1.100:8000 --monitor 2
        """,
    )
    parser.add_argument(
        '--server',
        required=True,
        help='URL of the Remote Desktop signaling server (e.g., http://localhost:8000)',
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=30,
        help='Screen capture FPS (default: 30)',
    )
    parser.add_argument(
        '--monitor',
        type=int,
        default=1,
        help='Monitor index to capture (default: 1 = primary)',
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Run in silent mode (no banner or extra logs)',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nGoodbye!")
