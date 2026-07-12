# Compatibility

This document tracks the minimum and maximum supported NetBox versions for each release of NetBox Grafana Annotations Plugin.

| Plugin Version | Minimum NetBox Version | Maximum NetBox Version |
|----------------|------------------------|------------------------|
| 0.1.0 | 4.6.0 | 4.6.99 |

Tested against NetBox v4.6.4 (netbox-docker image `v4.6-5.0.1`) during development. The 4.6.x range reflects what's actually been exercised so far, not a broader compatibility claim -- widen it only after testing against those other versions.

## Notes

- This plugin requires Python 3.12 or later
- Always test your plugin with the target NetBox version before upgrading in production
- Check the [NetBox release notes](https://docs.netbox.dev/en/stable/release-notes/) for breaking changes

## Upgrading

When upgrading NetBox or this plugin:

1. Review the NetBox release notes for any breaking changes
2. Test the upgrade in a development environment
3. Backup your database before upgrading production
4. Run database migrations: `python manage.py migrate`
5. Clear the cache: `python manage.py clearcache`
