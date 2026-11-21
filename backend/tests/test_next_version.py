"""Tests for backend/scripts/next_version.py (SPEC 9.3)."""

from scripts.next_version import next_version


def test_no_tags_returns_v010() -> None:
    """No semver tags at all → first release is v0.1.0."""
    assert next_version(tags=[], commit_messages=[]) == "v0.1.0"
    assert next_version(tags=[], commit_messages=["[major]"]) == "v0.1.0"


def test_non_semver_tags_ignored() -> None:
    """Tags that don't match vX.Y.Z are skipped."""
    result = next_version(
        tags=["latest", "stable", "foo", "v1.0", "vX.Y.Z", "99.99.99-beta"],
        commit_messages=[],
    )
    assert result == "v0.1.0"


def test_patch_bump_default() -> None:
    """Default bump without [minor]/[major] is patch +1."""
    assert next_version(tags=["v0.1.0"], commit_messages=[]) == "v0.1.1"
    assert next_version(tags=["v1.2.3"], commit_messages=["some fix"]) == "v1.2.4"
    assert next_version(tags=["v0.0.5"], commit_messages=[]) == "v0.0.6"


def test_minor_bump_resets_patch() -> None:
    """[minor] in any commit message bumps minor and resets patch to 0."""
    result = next_version(
        tags=["v0.1.0"],
        commit_messages=["feat: add new endpoint [minor]"],
    )
    assert result == "v0.2.0"

    result = next_version(
        tags=["v1.2.3"],
        commit_messages=["some commit\n[minor] another line"],
    )
    assert result == "v1.3.0"

    result = next_version(
        tags=["v0.9.5"],
        commit_messages=["feature [minor] and other stuff"],
    )
    assert result == "v0.10.0"


def test_major_bump_resets_minor_and_patch() -> None:
    """[major] in any commit message bumps major and resets minor+patch to 0."""
    result = next_version(
        tags=["v0.9.5"],
        commit_messages=["breaking: redesign [major]"],
    )
    assert result == "v1.0.0"

    result = next_version(
        tags=["v2.5.9"],
        commit_messages=["major rewrite [major]"],
    )
    assert result == "v3.0.0"


def test_major_takes_precedence_over_minor() -> None:
    """When both [major] and [minor] appear in commits, major wins."""
    result = next_version(
        tags=["v0.1.0"],
        commit_messages=[
            "small change [minor]",
            "big change [major]",
        ],
    )
    assert result == "v1.0.0"


def test_latest_semver_tag_is_used_as_base() -> None:
    """When multiple semver tags exist, the numerically highest is the base."""
    result = next_version(
        tags=["v0.1.0", "v0.2.0", "v0.3.1"],
        commit_messages=[],
    )
    assert result == "v0.3.2"

    result = next_version(
        tags=["v1.0.0", "v0.9.9", "v1.1.0"],
        commit_messages=["[minor]"],
    )
    assert result == "v1.2.0"


def test_non_semver_tags_mix_with_valid() -> None:
    """Non-semver tags are ignored; valid semver tags are used as base."""
    result = next_version(
        tags=["latest", "v0.5.0", "stable", "release"],
        commit_messages=[],
    )
    assert result == "v0.5.1"


def test_only_commits_since_latest_tag_count(monkeypatch) -> None:
    """An old commit mentioning [major] must not bump again after it was released."""
    import scripts.next_version as nv

    _seen_since: list[str | None] = []

    def _fake_log(since: str | None = None) -> list[str]:
        _seen_since.append(since)
        return ["Fix the worker"]

    monkeypatch.setattr(nv, "_git_tags", lambda: ["v0.1.0"])
    monkeypatch.setattr(nv, "_git_log_messages", _fake_log)

    result = nv.next_version()
    assert result == "v0.1.1"
    assert _seen_since == ["v0.1.0"]
