from __future__ import annotations

from typing import Any


ScalarMetadataValue = str | int | float | bool


class OntologyHarmonizer:
    """Placeholder curator for harmonizing publication text against ontologies."""

    def harmonize(
        self,
        publication_text: str | None = None,
        metadata: str | dict[str, Any] | list[Any] | None = None,
        title: str | None = None,
        ontology_frameworks: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "placeholder",
            "publication_text": publication_text,
            "metadata": metadata,
            "title": title,
            "ontology_frameworks": ontology_frameworks or {},
            "matches": [],
            "targets": self._extract_harmonization_targets(metadata),
        }

    def _extract_harmonization_targets(
        self,
        metadata: str | dict[str, Any] | list[Any] | None,
    ) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []

        if isinstance(metadata, (dict, list)):
            self._collect_targets(value=metadata, path="", targets=targets)

        return targets

    def _collect_targets(
        self,
        value: Any,
        path: str,
        targets: list[dict[str, Any]],
    ) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                item_path = self._join_json_pointer(path, key)
                if self._is_target_value(item):
                    targets.append(
                        self._target(
                            index=len(targets),
                            key=key,
                            value=item,
                            path=item_path,
                            parent_path=path,
                        )
                    )
                elif isinstance(item, (dict, list)):
                    self._collect_targets(value=item, path=item_path, targets=targets)
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    self._collect_targets(
                        value=item,
                        path=self._join_json_pointer(path, index),
                        targets=targets,
                    )

    @staticmethod
    def _is_target_value(value: Any) -> bool:
        return isinstance(value, (str, int, float, bool)) and value is not None

    @staticmethod
    def _target(
        *,
        index: int,
        key: Any,
        value: ScalarMetadataValue,
        path: str,
        parent_path: str,
    ) -> dict[str, Any]:
        return {
            "id": f"target-{index}",
            "source": "metadata",
            "field": str(key),
            "label": str(value),
            "field_path": path,
            "label_path": path,
            "parent_path": parent_path,
            "key": key,
            "value": value,
        }

    @classmethod
    def _join_json_pointer(cls, path: str, segment: Any) -> str:
        escaped_segment = cls._escape_json_pointer_segment(str(segment))
        if not path:
            return f"/{escaped_segment}"

        return f"{path}/{escaped_segment}"

    @staticmethod
    def _escape_json_pointer_segment(segment: str) -> str:
        return segment.replace("~", "~0").replace("/", "~1")
