# Portal submission - Custody Chain Verifier

Use after the exact GitHub source is deployed in Studio and the Explorer source
is verified against the deployed commit.

## Title

Custody Chain Verifier

## Notes under 1000 chars

```text
GenLayer IC for verifying an ordered chain of custody without asking validators
to produce a checklist of subjective findings.

Subject, ordered step requirements and one distinct custodian per step are
frozen before attestations. Each designated custodian submits exactly one
hash-committed statement, strictly in order. Once complete, the record hash
binds the params hash and every attestation hash.

The LLM returns one bounded value only: the first broken step index, or 0 if the
chain holds. Validators compare record hash, index and reason; readable prose is
audit-only. Range checks and INTACT/BROKEN/UNDETERMINED settlement are fully
deterministic. An incomplete chain is never judged: silence is visible through
pending_step, not manufactured into a break.

GenVM lint structure: exec_prompt is directly inside the inline callback passed
to prompt_comparative. Offline tests: 7/7 pass.
```

## Evidence checklist

- GitHub: https://github.com/Zhekinmaksim/genlayer-custody-chain-verifier
- Commit: GitHub `main`; contract source must stay unchanged after deployment
- Explorer contract and deploy transaction: pending Studio deployment
- Source match: confirm Explorer source equals the deployment commit
- Offline verification: `python3 -m py_compile contract.py sim/check.py` and
  `python3 sim/check.py` pass, 7/7 cases
- Live smoke: create a three-step chain; confirm wrong-address attest reverts;
  attest sequentially from the three custodians; evaluate and record the result
