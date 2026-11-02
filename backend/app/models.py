"""SQLAlchemy models for nodes and readings."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Node(Base):
    """Registry of ESP32 sensor nodes."""

    __tablename__ = "node"

    node_id = Column(String(64), primary_key=True)
    node_type = Column(String(16), nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=False)
    last_battery_v = Column(Numeric(5, 2), nullable=True)
    last_rssi_dbm = Column(Integer, nullable=True)

    readings = relationship(
        "Reading",
        back_populates="node",
        lazy="selectin",
        passive_deletes="all",
    )


class Reading(Base):
    """Individual metric readings from a node."""

    __tablename__ = "reading"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(
        String(64),
        ForeignKey("node.node_id", ondelete="CASCADE"),
        nullable=False,
    )
    metric = Column(String(64), nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)
    value = Column(Numeric(10, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("node_id", "metric", "ts", name="uq_node_metric_ts"),
        Index("ix_node_metric_ts", "node_id", "metric", "ts"),
    )

    node = relationship("Node", back_populates="readings")
