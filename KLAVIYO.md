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
on). To release, merge a PR into `klaviyo/0.2.9` that bumps `LOCAL_VERSION`. The Buildkite pipeline (`kcd.yaml`)
runs the tests and builds the artifacts on every build. On `klaviyo/0.2.9` it then uploads them to Artifactory's
`pypi-local` with `ci/publish.sh`. That script skips the upload when the merge didn't change `LOCAL_VERSION`, since
Artifactory rejects re-uploading an existing version with a 403.

To build the artifacts locally:

```bash
ci/build_wheels.sh linux x86_64
ci/build_wheels.sh linux aarch64
ci/build_wheels.sh sdist
```

## Testing

Upstream's suite needs a ClickHouse server, plus a `clickhouse-client` binary on `PATH` that can reach it. It reads its
connection settings from `setup.cfg`. `ci/docker-compose.yml` provides both, and CI uses it:

```bash
docker compose -f ci/docker-compose.yml run --rm --build tests
```

CI runs against ClickHouse 26.6.1.1193, the version BYOC runs. Unchanged upstream 0.2.9 has 12 failing tests on that
version, all in areas this fork doesn't touch: JSON columns (`tests/columns/test_json.py`), progress
(`tests/test_blocks.py::ProgressTestCase`), last-query info (`tests/test_query_info.py`),
`tests/test_insert.py::InsertTestCase::test_insert_from_input`, and two `test_use_client_timezone` tests in
`tests/columns/test_datetime.py`. On 25.8.16.34, the OSS version, the same set fails except the two timezone tests.
Against 24.4.1, the newest version upstream tested 0.2.9 against, nothing fails: 377 passed and 108 skipped, all of
them numpy tests, since `USE_NUMPY` is unset.
