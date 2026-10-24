# Sealed held-out suite (encrypted)

`sealed-heldout-v1.zip.enc` is the sealed held-out suite for the five study
tasks, encrypted. It holds 157 held-out test cases in three tiers, the five
reference implementations, and the validation evidence (naive variants, their
scores, and the validation report).

It stays encrypted until the last study run (R018, or R023 if the optional
replication is run) is finished. The study's author keeps the passphrase;
it is not stored anywhere in this repository.

| File | SHA-256 |
| --- | --- |
| `sealed-heldout-v1.zip` (the plaintext archive, as recorded in section 11 of the [pre-registration](../docs/PREREGISTRATION.md)) | `9451954e1d4d4a914cad422b0477c838626ce9507bb9ac23966dbcc5a02c2198` |
| `sealed-heldout-v1.zip.enc` (this encrypted file) | `9ead2595d7649e3f4c975c371f99c0beb6311c7bc2dd739edf4c0a1967cf5e4d` |

## Unsealing (after the last study run)

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
    -in sealed/sealed-heldout-v1.zip.enc -out sealed-heldout-v1.zip
sha256sum sealed-heldout-v1.zip      # must equal 9451954e…c2198 above
unzip -n sealed-heldout-v1.zip      # -n: keep this README, add the suite beside it
python3 tools/study/score_run.py --hash-only --heldout sealed/heldout
                                      # must equal the tree hash in section 11
```

OpenSSL asks for the passphrase. Then commit the unpacked `sealed/` folder,
so the tests become public alongside the results they produced.
