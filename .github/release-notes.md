Apple Silicon (M1 and later). Open the `.dmg`, drag **The Deposit Ledger** to Applications.

### The first launch

This build is not signed by Apple, so macOS refuses it once. Either right-click
the app and choose **Open**, then confirm — or run this once after installing:

```
xattr -dr com.apple.quarantine "/Applications/The Deposit Ledger.app"
```

Every launch after that is normal.

### Updating

Download the new `.dmg` and drag it over the old app. Your ledger is a separate
file on your Mac; installing a new version never touches it. If the schema
changed, the app migrates it on first launch and tells you so.

Verify the download against the `.sha256` beside it:

```
shasum -a 256 -c TheDepositLedger-*.dmg.sha256
```
