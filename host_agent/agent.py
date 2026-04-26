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
import os
import platform
import socket
import sys
import json
import uuid

from signaling_client import SignalingClient

CONFIG_FILE = 'config.json'

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            pass
    return {}

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        pass

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
        quality=args.quality,
        password=args.password,
        extra_ice_servers=build_extra_ice_servers(args),
    )

    # Create a session
    try:
        session_code = await client.create_session(host_identifier=host_id, alias=args.alias)
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        logger.error("Is the signaling server running? Check the --server URL.")
        sys.exit(1)

    # Save the current arguments to config.json for future use
    config_data = {
        'server': args.server,
        'fps': args.fps,
        'quality': args.quality,
        'monitor': args.monitor,
        'alias': args.alias,
        'password': args.password,
        'stun_servers': args.stun_server,
        'turn_servers': args.turn_server,
        'turn_username': args.turn_username,
        'turn_password': args.turn_password,
    }
    save_config(config_data)

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
    config = load_config()

    parser.add_argument(
        '--server',
        default=config.get('server', 'http://localhost:8000'),
        help='URL of the Remote Desktop signaling server (default from config or localhost:8000)',
    )
    parser.add_argument(
        '--alias',
        default=config.get('alias', ''),
        help='A permanent alias to use instead of a random session code (e.g. "my-pc")',
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=config.get('fps', 30),
        help='Screen capture FPS (default: 30)',
    )
    parser.add_argument(
        '--monitor',
        type=int,
        default=config.get('monitor', 1),
        help='Monitor index to capture (default: 1 = primary)',
    )
    parser.add_argument(
        '--silent',
        action='store_true',
        help='Run in silent mode (no banner or extra logs)',
    )
    parser.add_argument(
        '--quality',
        choices=['ultra-low', 'low', 'medium', 'high', 'ultra'],
        default=config.get('quality', 'medium'),
        help='Initial quality preset (default: medium). Use ultra-low for 10kbps connections.',
    )
    parser.add_argument(
        '--stun-server',
        action='append',
        default=config.get('stun_servers', []),
        help='Extra STUN server URL. Can be repeated or comma-separated.',
    )
    parser.add_argument(
        '--turn-server',
        action='append',
        default=config.get('turn_servers', []),
        help='TURN server URL. Can be repeated or comma-separated.',
    )
    parser.add_argument(
        '--turn-username',
        default=config.get('turn_username', os.getenv('REMOTE_SUPPORT_TURN_USERNAME', '')),
        help='TURN username. Defaults to REMOTE_SUPPORT_TURN_USERNAME.',
    )
    parser.add_argument(
        '--turn-password',
        default=config.get('turn_password', os.getenv('REMOTE_SUPPORT_TURN_PASSWORD', '')),
        help='TURN password. Defaults to REMOTE_SUPPORT_TURN_PASSWORD.',
    )
    parser.add_argument(
        '--password',
        default=config.get('password', os.getenv('REMOTE_SUPPORT_PASSWORD', '')),
        help='Require a password for clients to connect (enables secure unattended access).',
    )
    return parser.parse_args()


def build_extra_ice_servers(args):
    """Build optional ICE servers from CLI args and environment variables."""
    stun_servers = split_server_list([
        *args.stun_server,
        os.getenv('REMOTE_SUPPORT_STUN_SERVERS', ''),
    ])
    turn_servers = split_server_list([
        *args.turn_server,
        os.getenv('REMOTE_SUPPORT_TURN_SERVERS', ''),
    ])

    ice_servers = [{'urls': url} for url in stun_servers]
    for url in turn_servers:
        server = {'urls': url}
        if args.turn_username:
            server['username'] = args.turn_username
        if args.turn_password:
            server['credential'] = args.turn_password
        ice_servers.append(server)
    return ice_servers


def split_server_list(values):
    servers = []
    for value in values:
        for item in value.replace('\n', ',').split(','):
            item = item.strip()
            if item:
                servers.append(item)
    return servers


if __name__ == '__main__':
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nGoodbye!")
