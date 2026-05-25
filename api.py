#!/usr/bin/env python3
"""FastAPI application for STRATEGOS simulation engine."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.config import StrategosConfig
from core.events import EventType
from core.logging import configure_logging, get_logger
from core.simulation import Simulation

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Global simulation instance
simulation: Optional[Simulation] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global simulation

    # Startup
    logger.info("Starting STRATEGOS API server...")

    config = StrategosConfig()
    simulation = Simulation(
        db_path=config.db_path,
        checkpoint_dir=config.checkpoint_dir,
        checkpoint_interval=config.checkpoint_interval,
        time_scale=config.default_time_scale,
    )

    await simulation.initialize()
    logger.info("Simulation initialized", simulation_id=str(simulation.simulation_id))

    yield

    # Shutdown
    logger.info("Shutting down STRATEGOS API server...")
    if simulation:
        await simulation.shutdown()


# Create FastAPI app
app = FastAPI(
    title="STRATEGOS",
    description="Multi-scale geopolitical simulation engine with AI-driven autonomous agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for web UI
app.mount("/static", StaticFiles(directory="static"), name="static")


# Request/Response Models
class SimulationStatus(BaseModel):
    """Simulation status response."""

    simulation_id: str
    current_time: float
    time_scale: float
    is_running: bool
    clock_state: str
    event_count: int
    entity_count: int = 0
    formatted_time: Optional[str] = None


class EntityResponse(BaseModel):
    """Single entity response."""

    entity_id: str
    type: str
    position: list[float]
    velocity: list[float] = [0.0, 0.0, 0.0]
    heading: float = 0.0
    speed: float = 0.0
    max_speed: float = 0.0
    metadata: dict = {}
    created_at: float = 0.0
    destroyed_at: Optional[float] = None
    last_update_time: float = 0.0


class EntityListResponse(BaseModel):
    """List of entities response."""

    count: int
    entities: list[EntityResponse]


class CreateEntityRequest(BaseModel):
    """Request to create an entity."""

    type: str
    position: list[float] = [0.0, 0.0, 0.0]
    max_speed: float = 10.0
    metadata: Optional[dict] = None


class SetVelocityRequest(BaseModel):
    """Request to set entity velocity."""

    velocity: list[float]


class TimeScaleRequest(BaseModel):
    """Request to change time scale."""

    scale: float


class MarkerRequest(BaseModel):
    """Request to create a marker."""

    label: str
    metadata: Optional[dict] = None


class SeekRequest(BaseModel):
    """Request to seek to a specific time."""

    target_time: float


# REST Endpoints
@app.get("/")
async def root():
    """Redirect to web UI."""
    return RedirectResponse(url="/static/index.html")


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "STRATEGOS",
        "version": "0.1.0",
        "status": "running",
        "phase": "2 - Spatial Layer + Movement",
    }


@app.get("/status", response_model=SimulationStatus)
async def get_status():
    """Get current simulation status."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    status = simulation.get_status()
    return SimulationStatus(**status)


@app.post("/start")
async def start_simulation():
    """Start the simulation."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.start()
    return {"status": "started"}


@app.post("/stop")
async def stop_simulation():
    """Stop the simulation."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.stop()
    return {"status": "stopped"}


@app.post("/pause")
async def pause_simulation():
    """Pause the simulation."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.pause()
    return {"status": "paused"}


@app.post("/resume")
async def resume_simulation():
    """Resume the simulation."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.resume()
    return {"status": "resumed"}


@app.post("/time-scale")
async def set_time_scale(request: TimeScaleRequest):
    """Change simulation speed."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.set_time_scale(request.scale)
    return {"time_scale": request.scale}


@app.post("/seek")
async def seek_time(request: SeekRequest):
    """Seek to a specific simulation time."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    await simulation.seek(request.target_time)
    return {"current_time": simulation.clock.get_time()}


@app.post("/marker")
async def create_marker(request: MarkerRequest):
    """Create a timestamped marker event."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    event = await simulation.create_marker(request.label, request.metadata)
    return {
        "event_id": str(event.event_id),
        "simulation_time": event.simulation_time,
        "label": request.label,
    }


@app.get("/events")
async def get_events(
    from_time: float = 0.0,
    to_time: Optional[float] = None,
    event_type: Optional[str] = None,
):
    """Get events from the event store."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    event_types = [event_type] if event_type else None
    events = await simulation.event_store.get_events(from_time, to_time, event_types)

    return {
        "count": len(events),
        "events": [
            {
                "event_id": str(e.event_id),
                "simulation_time": e.simulation_time,
                "event_type": e.event_type.value
                if isinstance(e.event_type, EventType)
                else e.event_type,
                "data": e.data,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@app.post("/entities", response_model=EntityResponse, status_code=201)
async def create_entity(request: CreateEntityRequest):
    """Create a new entity in the simulation."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")
    if not simulation._running:
        raise HTTPException(status_code=400, detail="Simulation must be running to create entities")

    entity_id = await simulation.create_entity(
        entity_type=request.type,
        position=request.position,
        max_speed=request.max_speed,
        metadata=request.metadata,
    )

    entity_data = simulation.get_entity(entity_id) or {}
    return EntityResponse(
        entity_id=str(entity_id),
        type=entity_data.get("type", request.type),
        position=list(entity_data.get("position", request.position)),
        velocity=[0.0, 0.0, 0.0],
        max_speed=request.max_speed,
        metadata=request.metadata or {},
    )


@app.post("/entities/{entity_id}/velocity")
async def set_entity_velocity(entity_id: str, request: SetVelocityRequest):
    """Set velocity for a moving entity."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    try:
        uid = UUID(entity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity_id — must be a UUID")

    if simulation.get_entity(uid) is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    if len(request.velocity) == 2:
        velocity = (request.velocity[0], request.velocity[1], 0.0)
    elif len(request.velocity) == 3:
        velocity = tuple(request.velocity)
    else:
        raise HTTPException(status_code=400, detail="velocity must have 2 or 3 components")

    await simulation.set_entity_velocity(uid, velocity)
    return {"entity_id": entity_id, "velocity": list(velocity)}


@app.get("/entities", response_model=EntityListResponse)
async def get_entities():
    """Get snapshot of all living entities with interpolated positions."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    entities = []
    for entity_id, entity_data in simulation.state.entities.items():
        entity_id_str = str(entity_id)

        position = list(entity_data.get("position", [0.0, 0.0, 0.0]))
        if simulation.movement_system:
            try:
                uid = entity_id if isinstance(entity_id, UUID) else UUID(entity_id_str)
                interp = simulation.movement_system.get_entity_position(uid)
                if interp is not None:
                    position = list(interp)
            except Exception:
                pass

        entities.append(EntityResponse(
            entity_id=entity_id_str,
            type=entity_data.get("type", "unknown"),
            position=position,
            velocity=list(entity_data.get("velocity", [0.0, 0.0, 0.0])),
            heading=entity_data.get("heading", 0.0),
            speed=entity_data.get("speed", 0.0),
            max_speed=entity_data.get("max_speed", 0.0),
            metadata=entity_data.get("metadata", {}),
            created_at=entity_data.get("created_at", 0.0),
            destroyed_at=entity_data.get("destroyed_at"),
            last_update_time=entity_data.get("last_update_time", 0.0),
        ))

    return EntityListResponse(count=len(entities), entities=entities)


@app.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str):
    """Get a single entity by ID."""
    if not simulation:
        raise HTTPException(status_code=503, detail="Simulation not initialized")

    try:
        uid = UUID(entity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity_id — must be a UUID")

    entity_data = simulation.get_entity(uid)
    if entity_data is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    position = list(entity_data.get("position", [0.0, 0.0, 0.0]))
    if simulation.movement_system:
        try:
            interp = simulation.movement_system.get_entity_position(uid)
            if interp is not None:
                position = list(interp)
        except Exception:
            pass

    return EntityResponse(
        entity_id=entity_id,
        type=entity_data.get("type", "unknown"),
        position=position,
        velocity=list(entity_data.get("velocity", [0.0, 0.0, 0.0])),
        heading=entity_data.get("heading", 0.0),
        speed=entity_data.get("speed", 0.0),
        max_speed=entity_data.get("max_speed", 0.0),
        metadata=entity_data.get("metadata", {}),
        created_at=entity_data.get("created_at", 0.0),
        destroyed_at=entity_data.get("destroyed_at"),
        last_update_time=entity_data.get("last_update_time", 0.0),
    )


# WebSocket endpoint for real-time event streaming
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """Stream events in real-time via WebSocket."""
    await websocket.accept()

    if not simulation:
        await websocket.close(code=1011, reason="Simulation not initialized")
        return

    logger.info("WebSocket client connected")

    async def send_event(event):
        """Send event to WebSocket client."""
        try:
            await websocket.send_json(
                {
                    "event_id": str(event.event_id),
                    "simulation_time": event.simulation_time,
                    "event_type": event.event_type.value
                    if isinstance(event.event_type, EventType)
                    else event.event_type,
                    "data": event.data,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
            )
        except Exception as e:
            logger.error("Failed to send event via WebSocket", error=str(e))

    # Subscribe to events
    simulation.add_event_listener(send_event)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            message = await websocket.receive_text()
            logger.debug("WebSocket message received", message=message)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
    finally:
        # Note: We don't have an unsubscribe method yet, but we should add one
        logger.info("WebSocket connection closed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
