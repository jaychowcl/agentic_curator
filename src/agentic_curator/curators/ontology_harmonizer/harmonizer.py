from __future__ import annotations

from typing import Any


ScalarMetadataValue = str | int | float | bool
StartPathSpec = str | dict[str, Any]


class OntologyHarmonizer:
    """Placeholder curator for harmonizing publication text against ontologies."""

    DEFAULT_TARGET_PATHS: list[StartPathSpec] = [
        {"path": "/organism", "mode": "container_value"},
        {"path": "/characteristics", "mode": "tag_value"},
    ]

    def harmonize(
        self,
        publication_text: str | None = None,
        metadata: str | dict[str, Any] | list[Any] | None = None,
        title: str | None = None,
        ontology_frameworks: dict[str, Any] | None = None,
        target_paths: list[StartPathSpec] | None = None,
    ) -> dict[str, Any]:
        selected_target_paths = (
            self.DEFAULT_TARGET_PATHS if target_paths is None else target_paths
        )
        targets = self._extract_harmonization_targets(
            metadata,
            start_paths=selected_target_paths,
        )

        return {
            "status": "placeholder",
            "publication_text": publication_text,
            "metadata": metadata,
            "title": title,
            "ontology_frameworks": ontology_frameworks or {},
            "matches": [],
            "targets": targets,
        }

    def _extract_harmonization_targets(
        self,
        metadata: str | dict[str, Any] | list[Any] | None,
        start_paths: list[StartPathSpec] | None = None,
    ) -> list[dict[str, Any]]:
        targets: list[dict[str, Any]] = []

        if not isinstance(metadata, (dict, list)):
            return targets

        if start_paths is None:
            self._collect_targets(value=metadata, path="", targets=targets)
            return targets

        for start_path_spec in start_paths:
            start_path, mode = self._path_spec(start_path_spec)
            if start_path is None:
                continue

            resolved = self._resolve_json_pointer(metadata, start_path)
            if isinstance(resolved, (dict, list)):
                self._collect_targets_by_mode(
                    value=resolved,
                    path=start_path,
                    mode=mode,
                    targets=targets,
                )

        return targets

    def _collect_targets_by_mode(
        self,
        *,
        value: dict[str, Any] | list[Any],
        path: str,
        mode: str,
        targets: list[dict[str, Any]],
    ) -> None:
        if mode == "scalar":
            self._collect_targets(value=value, path=path, targets=targets)
            return

        if mode == "tag_value":
            self._collect_tag_value_targets(value=value, path=path, targets=targets)
            return

        if mode == "container_value":
            self._collect_container_value_targets(
                value=value,
                path=path,
                field_path=path,
                field=self._field_from_path(path),
                targets=targets,
            )

    @staticmethod
    def _path_spec(start_path_spec: Any) -> tuple[str | None, str]:
        if isinstance(start_path_spec, str):
            return start_path_spec, "scalar"

        if not isinstance(start_path_spec, dict):
            return None, "scalar"

        start_path = start_path_spec.get("path")
        if not isinstance(start_path, str):
            return None, "scalar"

        mode = start_path_spec.get("mode", "scalar")
        if mode not in {"scalar", "tag_value", "container_value"}:
            return None, "scalar"

        return start_path, mode

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

    def _collect_tag_value_targets(
        self,
        value: Any,
        path: str,
        targets: list[dict[str, Any]],
    ) -> None:
        if isinstance(value, dict):
            tag = value.get("tag")
            label = value.get("value")
            if self._is_target_value(tag) and self._is_target_value(label):
                targets.append(
                    self._target(
                        index=len(targets),
                        key=str(tag),
                        value=label,
                        path=self._join_json_pointer(path, "tag"),
                        label_path=self._join_json_pointer(path, "value"),
                        parent_path=path,
                    )
                )
                return

            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    self._collect_tag_value_targets(
                        value=item,
                        path=self._join_json_pointer(path, key),
                        targets=targets,
                    )
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    self._collect_tag_value_targets(
                        value=item,
                        path=self._join_json_pointer(path, index),
                        targets=targets,
                    )

    def _collect_container_value_targets(
        self,
        value: Any,
        path: str,
        field_path: str,
        field: str | None,
        targets: list[dict[str, Any]],
    ) -> None:
        if field is None:
            return

        if isinstance(value, dict):
            label = value.get("value")
            if self._is_target_value(label):
                targets.append(
                    self._target(
                        index=len(targets),
                        key=field,
                        value=label,
                        path=field_path,
                        label_path=self._join_json_pointer(path, "value"),
                        parent_path=path,
                    )
                )
                return

            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    self._collect_container_value_targets(
                        value=item,
                        path=self._join_json_pointer(path, key),
                        field_path=field_path,
                        field=field,
                        targets=targets,
                    )
            return

        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    self._collect_container_value_targets(
                        value=item,
                        path=self._join_json_pointer(path, index),
                        field_path=field_path,
                        field=field,
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
        label_path: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": f"target-{index}",
            "source": "metadata",
            "field": str(key),
            "label": str(value),
            "field_path": path,
            "label_path": path if label_path is None else label_path,
            "parent_path": parent_path,
            "key": key,
            "value": value,
        }

    @classmethod
    def _field_from_path(cls, path: str) -> str | None:
        if path == "":
            return None

        segment = path.rsplit("/", 1)[-1]
        return cls._unescape_json_pointer_segment(segment)

    @classmethod
    def _join_json_pointer(cls, path: str, segment: Any) -> str:
        escaped_segment = cls._escape_json_pointer_segment(str(segment))
        if not path:
            return f"/{escaped_segment}"

        return f"{path}/{escaped_segment}"

    @staticmethod
    def _escape_json_pointer_segment(segment: str) -> str:
        return segment.replace("~", "~0").replace("/", "~1")

    @classmethod
    def _resolve_json_pointer(
        cls,
        value: dict[str, Any] | list[Any],
        pointer: str,
    ) -> Any:
        if pointer == "":
            return value
        if not pointer.startswith("/"):
            return None

        current: Any = value
        for raw_segment in pointer.split("/")[1:]:
            segment = cls._unescape_json_pointer_segment(raw_segment)
            if isinstance(current, dict):
                if segment not in current:
                    return None
                current = current[segment]
                continue

            if isinstance(current, list):
                if not segment.isdecimal():
                    return None
                index = int(segment)
                if index >= len(current):
                    return None
                current = current[index]
                continue

            return None

        return current

    @staticmethod
    def _unescape_json_pointer_segment(segment: str) -> str:
        return segment.replace("~1", "/").replace("~0", "~")
