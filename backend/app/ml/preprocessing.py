from __future__ import annotations

from typing import Any

from app.ml.features import FEATURES


def prediction_frame(features: dict[str, Any]):
    """Select exactly the six no-labs contract fields for the saved pipeline."""
    import pandas as pd
    return pd.DataFrame([{key: features[key] for key in FEATURES}], columns=FEATURES)
