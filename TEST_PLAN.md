# Test plan - Custody Chain Verifier

Seven cases, all runnable offline against `sim/check.py` and again in hosted
Studio against a live deployment. The multi party protocol has to be right
before any judgment happens, so most of these cases never reach the LLM at all.

Fixture used throughout: a three step chain over `evidence bag 12` - collection,
transport, intake - with three distinct custodians.

## 1. Intact chain

All three custodians attest in order. The model returns `first_break: 0`.

Expected: status `COMPLETE` before evaluation, `pending_step` is 0, outcome
`INTACT`, `first_break_of` is 0, `broken_step` is empty, `explanation_of` is
recorded but was never compared.

## 2. Broken at a named step

Same chain, the model returns `first_break: 2`.

Expected: `BROKEN`, `first_break_of` is 2, `broken_step` returns the transport
step's own frozen text. Re-evaluating reverts with
`CHAIN_INCOMPLETE_OR_SETTLED`.

Returning the step text matters: an index alone is not a finding, and the text
is the requirement everyone committed to before any attestation existed.

## 3. An incomplete chain is never judged

Only the first custodian attests.

Expected: `pending_step` is 2, `pending_custodian` is Bob's address, `evaluate`
reverts with `CHAIN_INCOMPLETE_OR_SETTLED`, and `outcome_of` stays `NONE`.

This is the case that protects the primitive from being weaponised. If silence
produced a break, anyone could break any chain by refusing to sign, and a
manufactured break is exactly as useful as a real one to whoever benefits from
nothing being proved.

## 4. Attestations are ordered and designated

- the creator, who is not a custodian, tries to attest -> `NOT_DESIGNATED_CUSTODIAN`
- Carol, custodian of step 3, tries to attest step 1 -> `NOT_DESIGNATED_CUSTODIAN`
- Alice attests step 1, then tries to attest step 2 -> `NOT_DESIGNATED_CUSTODIAN`

Order and identity are enforced by the same check, because the only address that
may sign is the one designated for the step that is currently open.

## 5. Hash commitment and record pin

- a statement hash that does not match -> `HASH_MISMATCH`
- a whitespace-only statement -> `EMPTY_STATEMENT`
- `record_hash_of` is empty while the chain is incomplete and set the moment the
  last step lands
- the record hash equals `_digest(params_hash + "\n" + joined statement hashes)`,
  recomputed independently in the test

The record hash is what makes a post-hoc swap detectable, so it gets checked
against a recomputation rather than just checked for existence.

## 6. Out of range index and provider failure

The model returns `first_break: 9` on a three step chain -> `UNDETERMINED` with
reason `BREAK_OUT_OF_RANGE`. `exec_prompt` raising -> `UNDETERMINED` with reason
`JUDGMENT_UNAVAILABLE`.

Neither becomes `INTACT`. A judgment that could not be read must not be
presentable as a clean chain.

## 7. Creation guards and abandon

- one step -> `TOO_FEW_STEPS`
- nine steps -> `TOO_MANY_STEPS`
- the same address twice in the custodian list -> `DUPLICATE_CUSTODIAN`
- three steps with two custodians -> `CUSTODIAN_COUNT_MISMATCH`
- whitespace-only subject -> `EMPTY_SUBJECT`
- `abandon` before any attestation -> `ABANDONED`, and attesting afterwards
  reverts with `CHAIN_NOT_OPEN`
- `abandon` after the first attestation -> `ALREADY_ATTESTED`

The duplicate custodian guard is the one worth reading twice. Without it the
contract would happily judge a chain in which one party attested every handoff
to itself, and would report `INTACT` on it.

---

## Studio verification

Run in hosted Studio before submission:

- deploy and confirm the deploy transaction finalises
- `create_chain` smoke transaction with three distinct custodian addresses,
  confirming the returned params hash and the stored step list
- `attest` from the wrong address and out of order, confirming both revert on
  chain rather than only offline
- `attest` from each designated address in order, confirming `record_hash_of`
  appears only when the last step lands
- `evaluate` on the complete chain, confirming the outcome and the first break
  index are written

Studio needs three funded accounts for this, one per custodian. State plainly in
the submission which cases were run live, which were only exercised offline, and
the transaction hashes. Full live LLM adjudication across a full validator set
is not something I can force from Studio, so I say so rather than implying
otherwise.
