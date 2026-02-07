#!/usr/bin/env python3
"""Simple CLI runner for testing the STRATEGOS simulation engine."""

import asyncio
import sys
from pathlib import Path

from core.config import StrategosConfig
from core.events import EventType
from core.logging import configure_logging, get_logger
from core.simulation import Simulation

logger = get_logger(__name__)


async def print_event(event):
    """Print events as they occur."""
    print(
        f"[{event.simulation_time:.2f}s] {event.event_type.value if hasattr(event.event_type, 'value') else event.event_type}: {event.data}"
    )


async def run_demo():
    """Run a simple demonstration of the simulation."""
    # Configure logging
    configure_logging("INFO")

    logger.info("Starting STRATEGOS simulation demo...")

    # Create simulation
    sim = Simulation(
        db_path="strategos_demo.db",
        checkpoint_dir="checkpoints",
        checkpoint_interval=5.0,  # Checkpoint every 5 seconds
        time_scale=1.0,
    )

    try:
        # Initialize
        await sim.initialize()
        logger.info("Simulation initialized", simulation_id=str(sim.simulation_id))

        # Subscribe to all events for debugging
        sim.add_event_listener(print_event)

        # Start simulation
        await sim.start()
        logger.info("Simulation started")

        # Create some test markers
        await sim.create_marker("Demo Start")
        await asyncio.sleep(0.5)

        await sim.create_marker("Checkpoint Test", metadata={"note": "Testing checkpoints"})
        await asyncio.sleep(0.5)

        # Pause simulation
        await sim.pause()
        logger.info("Simulation paused")

        # Get status
        status = sim.get_status()
        print("\nSimulation Status:")
        for key, value in status.items():
            print(f"  {key}: {value}")

        # Resume
        await sim.resume()
        logger.info("Simulation resumed")

        # Let it run a bit
        await asyncio.sleep(1.0)

        # Change time scale
        await sim.set_time_scale(2.0)
        logger.info("Time scale changed to 2x")

        await asyncio.sleep(1.0)

        # Create a final marker
        await sim.create_marker("Demo End")

        # Stop simulation
        await sim.stop()

        # Final status
        print("\nFinal Status:")
        status = sim.get_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

        logger.info("Demo complete!")

    except Exception as e:
        logger.error("Demo failed", error=str(e), exc_info=True)
        raise
    finally:
        await sim.shutdown()


async def interactive_mode():
    """Run an interactive REPL for the simulation."""
    configure_logging("INFO")

    sim = Simulation(
        db_path="strategos_interactive.db",
        checkpoint_dir="checkpoints",
        checkpoint_interval=10.0,
        time_scale=1.0,
    )

    await sim.initialize()
    sim.add_event_listener(print_event)

    print("\n" + "=" * 60)
    print("STRATEGOS Interactive Simulation")
    print("=" * 60)
    print("\nCommands:")
    print("  start        - Start the simulation")
    print("  stop         - Stop the simulation")
    print("  pause        - Pause the simulation")
    print("  resume       - Resume the simulation")
    print("  status       - Show simulation status")
    print("  marker <msg> - Create a marker event")
    print("  scale <n>    - Set time scale")
    print("  quit         - Exit")
    print()

    try:
        while True:
            try:
                cmd = input("> ").strip().lower()

                if not cmd:
                    continue

                parts = cmd.split(maxsplit=1)
                command = parts[0]

                if command == "quit":
                    break
                elif command == "start":
                    await sim.start()
                    print("Simulation started")
                elif command == "stop":
                    await sim.stop()
                    print("Simulation stopped")
                elif command == "pause":
                    await sim.pause()
                    print("Simulation paused")
                elif command == "resume":
                    await sim.resume()
                    print("Simulation resumed")
                elif command == "status":
                    status = sim.get_status()
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                elif command == "marker":
                    if len(parts) < 2:
                        print("Usage: marker <message>")
                    else:
                        await sim.create_marker(parts[1])
                        print(f"Marker created: {parts[1]}")
                elif command == "scale":
                    if len(parts) < 2:
                        print("Usage: scale <number>")
                    else:
                        try:
                            scale = float(parts[1])
                            await sim.set_time_scale(scale)
                            print(f"Time scale set to {scale}x")
                        except ValueError:
                            print("Invalid scale value")
                else:
                    print(f"Unknown command: {command}")

            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except Exception as e:
                print(f"Error: {e}")

    finally:
        await sim.shutdown()


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        asyncio.run(interactive_mode())
    else:
        asyncio.run(run_demo())


if __name__ == "__main__":
    main()
