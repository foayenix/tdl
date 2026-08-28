Apple Silicon (M1 and later). Open the `.dmg`, drag **The Deposit Ledger** to Applications.

### The first launch

This build is signed ad-hoc, not by Apple, so macOS quarantines it. Dragging it
straight from the `.dmg` to the Dock or opening it in place gives:

> "The Deposit Ledger" is damaged and can't be opened. You should move it to the Bin.

It is not damaged — that is the message macOS shows on Apple Silicon for an app
it has not been told to trust. Copy it to Applications first, then once:

```
xattr -dr com.apple.quarantine "/Applications/The Deposit Ledger.app"
```

Every launch after that is normal. There is nothing to repeat on the next update
beyond this same one line.

### Updating

Download the new `.dmg` and drag it over the old app, then run the `xattr` line
again. Your ledger is a separate file on your Mac; installing a new version
never touches it. If the schema changed, the app migrates it on first launch and
tells you so.

Verify the download against the `.sha256` beside it:

```
shasum -a 256 -c TheDepositLedger-*.dmg.sha256
```
