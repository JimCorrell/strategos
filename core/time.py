# core/time.py

from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
import asyncio
from datetime import datetime, timezone
from enum import Enum


class ClockState(str, Enum):
    """Enumeration for clock states."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class TimeState:
    """Current state of simulation time."""

    current_time: float  # Simulation seconds since start
    time_scale: float  # Multiplier (1.0 = real-time, 10.0 = 10x speed)
    is_running: bool
    started_at: Optional[datetime] = None  # When we started running


class SimulationClock:
    """Manages continuous simulation time with variable scaling."""

    def __init__(self, time_scale: float = 1.0):
        self._time_state = TimeState(current_time=0.0, time_scale=time_scale, is_running=False)
        self._last_update: Optional[float] = None  # asyncio loop time
        self._update_task: Optional[asyncio.Task] = None
        self._clock_state = ClockState.STOPPED

    async def start(self) -> None:
        """Begin time progression."""
        if self._time_state.is_running:
            return

        self._time_state.is_running = True
        self._clock_state = ClockState.RUNNING
        self._time_state.started_at = datetime.now(timezone.utc)
        self._last_update = asyncio.get_event_loop().time()

        # Start the update loop
        self._update_task = asyncio.create_task(self._update_loop())
        await asyncio.sleep(0)  # Yield control to allow async execution

    async def pause(self) -> None:
        """Pause time progression."""
        self._time_state.is_running = False
        self._clock_state = ClockState.PAUSED
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                # Task cancelled successfully, clean up
                pass
            finally:
                self._update_task = None

    async def resume(self) -> None:
        """Resume time progression from paused state."""
        if self._clock_state == ClockState.PAUSED:
            await self.start()

    async def stop(self) -> None:
        """Stop the clock completely."""
        self._time_state.is_running = False
        self._clock_state = ClockState.STOPPED
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                # Task cancelled successfully, clean up
                pass
            finally:
                self._update_task = None

    async def seek(self, target_time: float) -> None:
        """Jump to a specific simulation time."""
        was_running = self._time_state.is_running
        if was_running:
            await self.pause()

        self._time_state.current_time = max(0.0, target_time)

        if was_running:
            await self.start()

    async def set_time_scale(self, scale: float) -> None:
        """Change simulation speed."""
        if scale <= 0:
            raise ValueError("Time scale must be positive")
        self._time_state.time_scale = scale

    async def tick(self) -> float:
        """Force an update of the simulation time and return current time."""
        if not self._time_state.is_running:
            return self.get_time()

        await asyncio.sleep(0)  # Yield to allow update loop to run
        return self.get_time()

    async def _update_loop(self) -> None:
        """Internal loop that advances simulation time."""
        while self._time_state.is_running:
            await asyncio.sleep(0.016)  # ~60 FPS update rate

            current_real_time = asyncio.get_event_loop().time()
            if self._last_update is not None:
                delta_real = current_real_time - self._last_update
                delta_sim = delta_real * self._time_state.time_scale
                self._time_state.current_time += delta_sim

            self._last_update = current_real_time

    def get_time(self) -> float:
        """Get current simulation time."""
        return self._time_state.current_time

    def get_time_scale(self) -> float:
        """Get current time scale."""
        return self._time_state.time_scale

    def get_state(self) -> ClockState:
        """Get the current clock state."""
        return self._clock_state

    @property
    def state(self) -> ClockState:
        """Get the current clock state (property)."""
        return self._clock_state

    @property
    def simulation_time(self) -> float:
        """Alias for get_time for compatibility."""
        return self.get_time()

    @simulation_time.setter
    def simulation_time(self, value: float) -> None:
        """Set simulation time directly."""
        self._time_state.current_time = max(0.0, value)

    @property
    def time_scale(self) -> float:
        """Alias for get_time_scale for compatibility."""
        return self.get_time_scale()

    @time_scale.setter
    def time_scale(self, value: float) -> None:
        """Set time scale directly."""
        if value <= 0:
            raise ValueError("Time scale must be positive")
        self._time_state.time_scale = value

    def format_time(self) -> str:
        """Format time as HH:MM:SS or Xd HH:MM:SS."""
        total_seconds = int(self._time_state.current_time)
        days = total_seconds // 86400
        remainder = total_seconds % 86400
        hours = remainder // 3600
        minutes = (remainder % 3600) // 60
        seconds = remainder % 60

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
