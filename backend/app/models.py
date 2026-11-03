"""SQLAlchemy models for nodes and readings."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
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
