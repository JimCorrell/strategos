#!/usr/bin/env python3
"""
STRATEGOS Launcher Script

Single-command launcher for the STRATEGOS simulation engine.
Handles setup, testing, and launching the application.
"""

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_banner():
    """Print STRATEGOS banner."""
    banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              ⚔️  S T R A T E G O S  ⚔️                    ║
║                                                           ║
║        Multi-scale Geopolitical Simulation Engine        ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
{Colors.ENDC}
"""
    print(banner)


def print_info(message):
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ  {message}{Colors.ENDC}")


def print_success(message):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓  {message}{Colors.ENDC}")


def print_warning(message):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠  {message}{Colors.ENDC}")


def print_error(message):
    """Print error message."""
    print(f"{Colors.FAIL}✗  {message}{Colors.ENDC}")


def check_python_version():
    """Check if Python version is 3.11+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error(f"Python 3.11+ required, but you have {version.major}.{version.minor}")
        return False
    print_success(f"Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_venv():
    """Check if virtual environment is activated."""
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print_success("Virtual environment is activated")
        return True
    else:
        print_warning("Virtual environment not detected")
        print_info("Run: source .venv/bin/activate")
        return False


def check_dependencies():
    """Check if required packages are installed."""
    required_packages = [
        "fastapi",
        "uvicorn",
        "aiosqlite",
        "structlog",
        "pydantic",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        print_error(f"Missing packages: {', '.join(missing)}")
        print_info("Run: pip install -r requirements.txt")
        return False

    print_success("All dependencies installed")
    return True


def create_directories():
    """Create necessary directories."""
    dirs = ["checkpoints", "logs"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
    print_success("Required directories created")


def run_tests(verbose=False):
    """Run test suite."""
    print_info("Running tests...")

    cmd = (
        [sys.executable, "-m", "pytest", "tests/", "-v"]
        if verbose
        else [sys.executable, "-m", "pytest", "tests/", "-q"]
    )

    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            print_success("All tests passed")
            return True
        else:
            print_warning("Some tests failed")
            return False
    except FileNotFoundError:
        print_warning("pytest not installed, skipping tests")
        print_info("Install with: pip install pytest pytest-asyncio")
        return True


def start_api_server(host="0.0.0.0", port=8000, reload=True):
    """Start the FastAPI server."""
    print_info(f"Starting STRATEGOS API server on {host}:{port}...")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    if reload:
        cmd.append("--reload")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print_info("\nShutting down STRATEGOS...")
        print_success("Goodbye!")


def open_browser(port=8000, delay=2):
    """Open web browser to the UI."""
    url = f"http://localhost:{port}"
    print_info(f"Opening browser to {url}...")
    time.sleep(delay)  # Wait for server to start
    webbrowser.open(url)


def run_cli_demo():
    """Run the CLI demo."""
    print_info("Starting CLI demo...")
    subprocess.run([sys.executable, "run_simulation.py"])


def run_interactive():
    """Run interactive mode."""
    print_info("Starting interactive mode...")
    subprocess.run([sys.executable, "run_simulation.py", "--interactive"])


def main():
    """Main launcher function."""
    parser = argparse.ArgumentParser(
        description="STRATEGOS Launcher - Start the simulation engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Start API server with web UI
  %(prog)s --test             # Run tests then start server
  %(prog)s --demo             # Run CLI demo
  %(prog)s --interactive      # Run interactive mode
  %(prog)s --no-browser       # Start server without opening browser
  %(prog)s --port 3000        # Use custom port
        """,
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run CLI demo instead of API server",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive REPL mode",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run tests before starting",
    )

    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Run tests and exit",
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for API server (default: 8000)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for API server (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload in development",
    )

    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip environment checks",
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Run checks unless skipped
    if not args.skip_checks:
        print_info("Running environment checks...")

        if not check_python_version():
            sys.exit(1)

        check_venv()  # Warning only

        if not check_dependencies():
            sys.exit(1)

        create_directories()
        print()

    # Run tests if requested
    if args.test or args.test_only:
        success = run_tests(verbose=True)
        print()

        if args.test_only:
            sys.exit(0 if success else 1)

        if not success:
            response = input("Tests failed. Continue anyway? [y/N] ")
            if response.lower() != "y":
                sys.exit(1)

    # Launch appropriate mode
    if args.demo:
        run_cli_demo()

    elif args.interactive:
        run_interactive()

    else:
        # Start API server with web UI
        if not args.no_browser:
            # Open browser in background
            import threading

            browser_thread = threading.Thread(
                target=open_browser, args=(args.port,), daemon=True
            )
            browser_thread.start()

        start_api_server(
            host=args.host,
            port=args.port,
            reload=not args.no_reload,
        )


if __name__ == "__main__":
    main()
