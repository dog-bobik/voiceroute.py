# Pinned VoiceRoute contracts

These files snapshot the bot-platform contracts from the server revision recorded in
`manifest.json`. They provide reproducible input for SDK coverage review without
depending on a sibling server checkout.

Run `python scripts/check_contract_snapshots.py` to verify the pinned SHA-256 values.
Run `python scripts/check_api_coverage.py --json` to produce the operation/event inventory.
Run `python scripts/check_api_coverage.py --write-manifest contracts/voiceroute/sdk-coverage.json`
to refresh the checked-in operation-level inventory. Null method/DTO/test fields and the
`unmapped` status are intentional: they identify coverage work still requiring review.
When updating a snapshot, update the source revision and file hashes together, then review
the generated operation diff. The inventory classifies authentication surfaces; it does
not claim an SDK method is implemented until its status is explicitly mapped and verified.
