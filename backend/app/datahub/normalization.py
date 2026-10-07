from collections.abc import Mapping

from app.datahub.schemas import NormalizedPayload
from app.datahub.types import DatasetDefinition


def normalize_row(
    dataset: DatasetDefinition, values: Mapping[str, object]
) -> NormalizedPayload:
    return dataset.schema.model_validate(values)
