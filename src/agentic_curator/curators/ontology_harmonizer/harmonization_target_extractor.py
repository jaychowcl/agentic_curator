# =============================================================================
# Authors
# =============================================================================
# Created by jaychowcl @ Saez-Rodriguez Group & GSK on June 2026
# https://github.com/jaychowcl
# https://saezlab.org
# https://www.gsk.com/
# =============================================================================

from __future__ import annotations

from typing import Any


ScalarMetadataValue = str | int | float | bool
StartPathSpec = str | dict[str, Any]


class HarmonizationTargetExtractor:
    """Extract editable metadata targets for future ontology harmonization."""

    DEFAULT_TARGET_PATHS: list[StartPathSpec] = [
        {"path": "/organism", "mode": "container_value"},
        {"path": "/characteristics", "mode": "tag_value"},
    ]
    MINIML_CHANNEL_TARGETS: tuple[tuple[str, str], ...] = (
        ("source", "field_value"),
        ("molecule", "field_value"),
        ("organism", "container_value"),
        ("characteristics", "tag_value"),
    )

    def extract(
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
                continue

            if mode == "field_value" and self._is_target_value(resolved):
                field = self._field_from_path(start_path)
                if field is None:
                    continue
                targets.append(
                    self._target(
                        index=len(targets),
                        key=field,
                        value=resolved,
                        path=start_path,
                        parent_path=self._parent_path(start_path),
                    )
                )

        return targets

    def build_miniml_sample_target_paths(
        self,
        miniml_json: str | dict[str, Any] | list[Any] | None,
    ) -> list[StartPathSpec]:
        if isinstance(miniml_json, dict):
            return self._build_miniml_package_target_paths(
                package=miniml_json,
                package_path="",
            )

        if not isinstance(miniml_json, list):
            return []

        target_paths: list[StartPathSpec] = []
        for package_index, package in enumerate(miniml_json):
            if not isinstance(package, dict):
                continue
            package_path = self._join_json_pointer("", package_index)
            target_paths.extend(
                self._build_miniml_package_target_paths(
                    package=package,
                    package_path=package_path,
                )
            )
        return target_paths

    def dedupe_targets(self, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped_targets: list[dict[str, Any]] = []
        target_indexes: dict[tuple[str, str], int] = {}

        for target in targets:
            field = str(target.get("pre_hz_field"))
            label = str(target.get("pre_hz_label"))
            dedupe_key = (field, label)
            occurrence = self._target_occurrence(target)

            if dedupe_key in target_indexes:
                deduped_targets[target_indexes[dedupe_key]]["occurrences"].append(
                    occurrence
                )
                continue

            deduped_target = dict(target)
            deduped_target["id"] = f"target-{len(deduped_targets)}"
            deduped_target["occurrences"] = [occurrence]
            deduped_target.pop("pre_hz_field_path", None)
            deduped_target.pop("pre_hz_label_path", None)
            deduped_target.pop("parent_path", None)
            target_indexes[dedupe_key] = len(deduped_targets)
            deduped_targets.append(deduped_target)

        return deduped_targets

    def _build_miniml_package_target_paths(
        self,
        *,
        package: dict[str, Any],
        package_path: str,
    ) -> list[StartPathSpec]:
        samples = package.get("sample")
        if not isinstance(samples, list):
            return []

        target_paths: list[StartPathSpec] = []
        samples_path = self._join_json_pointer(package_path, "sample")
        for sample_index, sample in enumerate(samples):
            if not isinstance(sample, dict):
                continue

            channels = sample.get("channel")
            if not isinstance(channels, list):
                continue

            sample_path = self._join_json_pointer(samples_path, sample_index)
            channels_path = self._join_json_pointer(sample_path, "channel")
            for channel_index, channel in enumerate(channels):
                if not isinstance(channel, dict):
                    continue

                channel_path = self._join_json_pointer(channels_path, channel_index)
                for field, mode in self.MINIML_CHANNEL_TARGETS:
                    if field not in channel:
                        continue
                    target_paths.append(
                        {
                            "path": self._join_json_pointer(channel_path, field),
                            "mode": mode,
                        }
                    )

        return target_paths

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
        if mode not in {"scalar", "tag_value", "container_value", "field_value"}:
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
            "pre_hz_field": str(key),
            "pre_hz_label": str(value),
            "pre_hz_field_path": path,
            "pre_hz_label_path": path if label_path is None else label_path,
            "parent_path": parent_path,
            "hz_field": key,
            "hz_label": value,
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
    def _parent_path(path: str) -> str:
        if "/" not in path.strip("/"):
            return ""
        return path.rsplit("/", 1)[0]

    @staticmethod
    def _target_occurrence(target: dict[str, Any]) -> dict[str, Any]:
        return {
            "pre_hz_field_path": target.get("pre_hz_field_path"),
            "pre_hz_label_path": target.get("pre_hz_label_path"),
            "parent_path": target.get("parent_path"),
            "hz_field": target.get("hz_field"),
            "hz_label": target.get("hz_label"),
        }

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
