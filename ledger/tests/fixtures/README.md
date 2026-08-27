# fixtures

`crossref_shape.json` is **not a recording**. §7 test 6 asks for a recorded
Crossref response, and this build environment cannot reach `api.crossref.org` —
the egress proxy answers 403 to the CONNECT, which is an organisation policy
denial, not a transient failure.

Rather than invent a paper and a DOI — §8 forbids exactly that — the fixture
uses Crossref's own **test prefix `10.5555`** and placeholder strings that
cannot be mistaken for bibliography. It exercises the response *shape*: the
`title`/`container-title` arrays, the `author` list with `given`/`family`,
`issued.date-parts`, `volume` and `type`.

**Before v0.1 ships, replace it with a real recording** from a machine that can
reach Crossref:

```
curl -H 'User-Agent: ledger/0.1' \
  https://api.crossref.org/works/10.1016/j.jep.2019.112202 \
  > ledger/tests/fixtures/crossref_10.1016_j.jep.2019.112202.json
```

then point `test_crossref.py` at it. The live test in that module is already
written and marked `@pytest.mark.network`; running
`pytest -m network ledger/tests` on a connected machine proves the parser
against the real API in one command.
