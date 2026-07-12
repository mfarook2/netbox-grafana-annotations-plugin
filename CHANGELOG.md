# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-12

### Release Summary
Initial release of NetBox Grafana Annotations Plugin. This is a **minor** release (first public version) introducing a webhook receiver that turns NetBox Event Rule deliveries into Grafana annotations, with a resolution strategy for mapping NetBox objects to Grafana dashboards/panels.

### Added
- Webhook receiver endpoint (`/plugins/netbox_grafana_annotations_plugin/webhook/`), authenticated via HMAC `X-Hook-Signature` verification matching NetBox's own webhook-signing convention — no NetBox API token or login-required exemption needed.
- Payload parsing with ORM-based resolution of both sides of a changed foreign-key field (e.g. a device role change resolves to `"Access Switch" -> "Core Switch"`, not raw database ids).
- Object → dashboard/panel mapping: a `grafana_dashboard_uid` custom-field override, falling back to a live Grafana tag search (`netbox:{object_type}:{object_name}`) with in-process caching.
- Parent-object resolution for child object types (e.g. Interface resolves to its parent Device for mapping purposes, since there's no such thing as a per-interface dashboard), configurable via `PARENT_OBJECT_MAP`.
- `AnnotationLog` model: a visible, queryable record of every webhook received and whether its annotation attempt succeeded, with Grafana's response status and error detail for failures.
- Full `PLUGINS_CONFIG` settings surface (Grafana URL/token, webhook secret, tag template, custom field names, cache TTL, timeout).
- Comprehensive test suite (46 tests) covering payload parsing, mapping resolution, signature verification, and the webhook view, run via GitHub Actions CI against a real NetBox instance.
- Documentation with MkDocs.

### Fixed
- N/A (initial release)

### Changed
- N/A (initial release)

### Deprecated
- N/A (initial release)

### Removed
- N/A (initial release)

### Security
- N/A (initial release)

---

## Release Notes Template for Future Versions

When creating a new release, use this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Release Summary
Brief narrative summary describing the release type (major/minor/patch) and key highlights.

### **Breaking Changes**
<!-- Only include this section if there are breaking changes -->
- **[#issue]** Description of breaking change and migration path
- Link to detailed migration guide if needed

### Added
- New features and capabilities

### Fixed
- Bug fixes with issue references

### Changed
- Changes to existing functionality

### Deprecated
- Features marked for future removal

### Removed
- Features that have been removed

### Security
- Security improvements and fixes
```

---

**Best Practice**: For clear release communication, ensure each release includes:
1. Narrative summary characterizing the release type (major/minor/patch)
2. Clear indicators for bugs, features, or enhancements
3. Bold "Breaking Changes" header when applicable with migration guidance
4. Detailed changelog with issue references
