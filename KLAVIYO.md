# Klaviyo fork of clickhouse-driver

This is a fork of [mymarilyn/clickhouse-driver](https://github.com/mymarilyn/clickhouse-driver) at the `0.2.9` tag.
segmentation-service uses it, and the working branch is `klaviyo/0.2.9`.

## Why it exists

ClickHouse Cloud's [replica-aware routing](https://clickhouse.com/docs/products/cloud/features/infrastructure/replica-aware-routing)
picks a replica from the TLS server name (SNI) the client sends, in the form `<value>.sticky.<host>`. In upstream
clickhouse-driver, `server_hostname` sets both the SNI and the name the server certificate has to match. Python's
`ssl` module uses a single name for both. The certificate only covers `*.<host>`, and a wildcard matches just one DNS
label, so verification fails whenever the SNI is a sticky name.

The fork adds a `tls_sni_override` connection option, which works like clickhouse-client's `--tls-sni-override`. The
client sends the override as the SNI and checks the certificate against `server_hostname or host`. When the option
isn't passed, behavior is the same as upstream. See GPLAT-1727 for the background.

## How it differs from upstream

- The version is `0.2.9+klaviyo.N` (`LOCAL_VERSION` in `clickhouse_driver/__init__.py`, which `setup.py` reads).
- `ci/build_wheels.sh` builds the published artifacts: cp310 manylinux wheels for x86_64 and aarch64, plus an sdist.
  There is no macOS wheel. macOS installs build from the sdist, which ships the generated `.c` files.

Nothing else differs. Keep it that way, so rebasing onto a newer upstream release and opening the change upstream
both stay easy.

## Releasing

Artifactory versions are immutable, so every release needs a new `LOCAL_VERSION` (`klaviyo.2`, `klaviyo.3`, and so
on). Publishing will go through a Buildkite pipeline that hasn't been built yet. Until it exists, the
artifacts come from:

```bash
ci/build_wheels.sh linux x86_64
ci/build_wheels.sh linux aarch64
ci/build_wheels.sh sdist
```

## Testing

Upstream's suite needs a ClickHouse server, plus a `clickhouse-client` binary on `PATH` that can reach it. It reads its
connection settings from `setup.cfg`. Baseline on `klaviyo/0.2.9` before any fork changes: 377 passed, 108 skipped,
0 failed, run against ClickHouse 24.4.1 (the newest version upstream tested 0.2.9 against) with Python 3.10. All 108
skips are numpy tests, since `USE_NUMPY` was unset, the same as upstream CI's main matrix.
