from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DemoProfile(Base):
    __tablename__ = "demo_profiles"
    __table_args__ = (CheckConstraint("data_origin = 'synthetic'", name="ck_demo_synthetic_only"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(30))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    bmi: Mapped[float] = mapped_column(Float)
    hypertension: Mapped[int] = mapped_column(Integer)
    heart_disease: Mapped[int] = mapped_column(Integer)
    smoking_history: Mapped[str] = mapped_column(String(40))
    known_type2_diabetes: Mapped[bool] = mapped_column(Boolean, default=False)
    data_origin: Mapped[str] = mapped_column(String(20), default="synthetic")

    readings: Mapped[list["GlucoseReading"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    labs: Mapped[list["LabResult"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class GlucoseReading(Base):
    __tablename__ = "glucose_readings"
    __table_args__ = (CheckConstraint("glucose_mg_dl > 0", name="ck_glucose_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("demo_profiles.id", ondelete="CASCADE"), index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    original_value: Mapped[float] = mapped_column(Float)
    original_unit: Mapped[str] = mapped_column(String(16))
    glucose_mg_dl: Mapped[float] = mapped_column(Float)
    measurement_type: Mapped[str] = mapped_column(String(30))
    source_type: Mapped[str] = mapped_column(String(30), default="synthetic")

    profile: Mapped[DemoProfile] = relationship(back_populates="readings")


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("demo_profiles.id", ondelete="CASCADE"), index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    test_type: Mapped[str] = mapped_column(String(40))
    original_value: Mapped[float] = mapped_column(Float)
    original_unit: Mapped[str] = mapped_column(String(16))
    normalized_value_mg_dl: Mapped[float | None] = mapped_column(Float, nullable=True)
    fasting_confirmed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), default="synthetic")

    profile: Mapped[DemoProfile] = relationship(back_populates="labs")


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(80), unique=True)
    task_type: Mapped[str] = mapped_column(String(80))
    feature_schema: Mapped[str] = mapped_column(Text)
    evaluation_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_validation: Mapped[bool] = mapped_column(Boolean, default=False)


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str | None] = mapped_column(ForeignKey("demo_profiles.id"), nullable=True)
    model_version: Mapped[str] = mapped_column(String(80))
    model_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    predicted_class: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    input_snapshot: Mapped[str] = mapped_column(Text)
    shap_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

