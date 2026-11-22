"""SQLAlchemy models for nodes and readings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Node(Base):
    """Registry of ESP32 sensor nodes."""

    __tablename__ = "node"

    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(16), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_battery_v: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    last_rssi_dbm: Mapped[int | None] = mapped_column(Integer)

    readings = relationship(
        "Reading",
        back_populates="node",
        lazy="selectin",
        passive_deletes="all",
    )


class Reading(Base):
    """Individual metric readings from a node."""

    __tablename__ = "reading"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("node.node_id", ondelete="CASCADE"),
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("node_id", "metric", "ts", name="uq_node_metric_ts"),
        Index("ix_node_metric_ts", "node_id", "metric", "ts"),
    )

    node = relationship("Node", back_populates="readings")


# ---------------------------------------------------------------------------- garden (SPEC §12–§16)
# Coordinates are metres in the garden's own frame: x to the east, y to the north, origin at the
# south-west corner of the plot. Sizes: w along x, d along y, h up. rotation is degrees, clockwise.

_JSON = JSON().with_variant(JSONB(), "postgresql")

OBJECT_KINDS = (
    "bed",
    "house",
    "greenhouse",
    "compost",
    "path",
    "tree",
    "shrub",
    "water",
    "fence",
    "sensor",
    "other",
)
PLANTING_STATUSES = (
    "planned",
    "sown",
    "sprouted",
    "growing",
    "flowering",
    "harvesting",
    "done",
    "failed",
)
PLANTING_METHODS = ("sown", "transplanted", "planted")
TASK_CATEGORIES = ("repair", "build", "maintenance", "planting", "harvest", "watering", "other")
TASK_URGENCIES = ("low", "normal", "high", "critical")
TASK_STATUSES = ("open", "done")
SPECIES_KINDS = ("plant", "insect", "fungus", "bird", "mammal", "other")
SPECIES_VERDICTS = ("beneficial", "neutral", "harmful", "invasive", "unknown")
SOURCE_KINDS = ("guide", "paper", "seed_packet", "note", "website")


class GardenObject(Base):
    """Anything placed on the garden map: beds, the garden house, compost bin, paths, sensors …"""

    __tablename__ = "garden_object"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    w: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    d: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    h: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    rotation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    color: Mapped[str | None] = mapped_column(String(16))
    props: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    node_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("node.node_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Crop(Base):
    """What a crop needs and how long it takes. Used by the growth model (SPEC §16)."""

    __tablename__ = "crop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    latin: Mapped[str | None] = mapped_column(String(120))
    family: Mapped[str | None] = mapped_column(String(60))
    days_to_germinate: Mapped[int | None] = mapped_column(Integer)
    days_to_harvest: Mapped[int | None] = mapped_column(Integer)
    base_temp_c: Mapped[float | None] = mapped_column(Float)
    gdd_to_harvest: Mapped[float | None] = mapped_column(Float)
    soil_temp_min_c: Mapped[float | None] = mapped_column(Float)
    moisture_min_pct: Mapped[float | None] = mapped_column(Float)
    moisture_max_pct: Mapped[float | None] = mapped_column(Float)
    sun: Mapped[str | None] = mapped_column(String(12))
    spacing_cm: Mapped[int | None] = mapped_column(Integer)
    sow_months: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str | None] = mapped_column(Text)


class Planting(Base):
    """One entry in the seed log: what was sown or planted, where and when."""

    __tablename__ = "planting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("garden_object.id", ondelete="SET NULL")
    )
    crop_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("crop.id", ondelete="SET NULL"))
    crop: Mapped[str] = mapped_column(String(80), nullable=False)
    variety: Mapped[str | None] = mapped_column(String(80))
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    w: Mapped[float | None] = mapped_column(Float)
    d: Mapped[float | None] = mapped_column(Float)
    count: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="sown")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sown")
    sown_on: Mapped[date] = mapped_column(Date, nullable=False)
    expected_harvest: Mapped[date | None] = mapped_column(Date)
    harvested_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Task(Base):
    """A to-do or reminder, optionally pinned to an object or a spot on the map."""

    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(24), nullable=False, default="other")
    urgency: Mapped[str] = mapped_column(String(12), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open")
    deadline: Mapped[date | None] = mapped_column(Date)
    object_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("garden_object.id", ondelete="SET NULL")
    )
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Species(Base):
    """A plant or animal: either one you found, or part of the common-species catalogue."""

    __tablename__ = "species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    latin: Mapped[str | None] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="plant")
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    common: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Sighting(Base):
    """One time a species was found in the garden."""

    __tablename__ = "sighting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    species_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("species.id", ondelete="CASCADE"), nullable=False
    )
    seen_on: Mapped[date] = mapped_column(Date, nullable=False)
    object_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("garden_object.id", ondelete="SET NULL")
    )
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    count: Mapped[int | None] = mapped_column(Integer)
    removed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    photo: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Source(Base):
    """Reference material the advisor may quote (SPEC §16): growing guides, seed packets, notes."""

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="guide")
    url: Mapped[str | None] = mapped_column(String(500))
    publisher: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
