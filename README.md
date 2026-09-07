# Custody Chain Verifier

A GenLayer Intelligent Contract for ordered chains of custody. Two to eight
steps, each attested on chain by a different designated custodian, and one
question: at which step does the chain first break.

## Why this is a different primitive

A checklist and a chain are not the same shape. In a checklist any item can fail
on its own and the rest still mean something, so the natural output is a set of
per-item flags. In a chain of custody the steps are **ordered and dependent**:
once step 3 fails, steps 4 through 8 prove nothing at all, because a handoff
from a party that never validly held the subject is not evidence, however well
documented it is.

So the meaningful output is not a set of flags, it is a **boundary**: the index
of the first failure. Everything before it holds; everything after it is
unassessable and asking about it is a category error.

That makes the consensus surface as small as it can get. One integer, between 0
and n.

The lifecycle is different too. The other primitives take a document from one
party. This one is an **n-party sequential commitment protocol**: each custodian
attests their own step, in order, one shot, hash committed, from an address
designated before any of them signed. The record that gets judged is assembled
on chain by the people who are accountable for it.

## The problem

Chain of custody, escalation procedures, supply chain provenance, regulatory
handoffs, multi-party approvals. All of them are sequences where the question is
never "which steps look bad" but "where did this stop being trustworthy". Today
that question is answered by whoever holds the file, usually after a dispute,
usually by the party with the most to lose from the honest answer.

## Consensus design

**Stage A - deterministic.** Subject, ordered step requirements and the
custodian list are fixed at creation and hashed into a params hash. Each
custodian then attests, in order, and each attestation is hash committed at
submission. When the last step lands, a record hash binds the params hash and
every attestation hash together. That record hash is recomputed before judgment.
No LLM, no web fetch.

**Stage B - non deterministic.** One prompt, one bounded question with `n + 1`
possible answers: the 1-based index of the first step whose attestation fails to
establish it or fails to connect to the step before, or 0 if the chain is
intact. The object returned to consensus is:

```json
{"ok": true, "record": "0x...", "first_break": 2, "reason": "", "why": "..."}
```

The equivalence principle compares `ok`, `record`, `first_break` and `reason`,
and instructs validators to ignore `why` entirely, so the readable explanation is
stored without ever entering consensus.

The callback passed to `gl.eq_principle.prompt_comparative` is declared directly
inside `evaluate`, and the `gl.nondet.exec_prompt` call is directly inside that
callback. This makes the non-deterministic boundary visible to GenVM lint.

**Stage C - deterministic.** Range check on the integer, then `INTACT` at 0 or
`BROKEN` at that step, with the failing step's own text resolvable through a
view. Terminal.

## Outcomes

| Outcome | Meaning |
| --- | --- |
| `INTACT` | Every step holds and every handoff connects. |
| `BROKEN` | The chain first fails at step k. The step text is recorded. |
| `UNDETERMINED` | The contract could not establish the facts: integrity failure, unreadable judgment, an index outside the valid range, or a record hash that does not match the commitment. |

## An incomplete chain is never judged

If a custodian never attests, the chain gets no verdict at all, and
`pending_step` says publicly which step is waiting and on whom.

This is deliberate and it is the most important design decision in the contract.
Inferring a break from silence would let anyone break any chain by refusing to
sign - and for the party that benefits from nothing being proved, a manufactured
break is exactly as good as a real one. **Absence of an attestation is not
evidence of a break.** The contract's job is to locate a break in a complete
record; incompleteness is a different fact, and it is visible on chain rather
than converted into a verdict.

The same reasoning is why there is no countersign step here: the attestations
**are** the consent. A custodian who disagrees with the requirement written for
their step simply does not attest, and an unattested chain is never judged.

## Adversarial analysis

- **Everything that defines the question is frozen at creation**, before a single
  attestation exists. Nobody can add a step, soften a requirement or swap in a
  friendlier custodian after seeing what was attested.
- **Custodians must be distinct addresses.** A chain whose every step is attested
  by one address is a single party's account of its own conduct and corroborates
  nothing. Distinctness is what makes the chain a chain.
- **Attestations are in order.** Out of order assembly would let a custodian sign
  a handoff before the handoff into their hands existed.
- **Attestations are one shot.** An attestation that could be revised after the
  next one landed lets a party rewrite history to close a gap the auditor would
  otherwise have seen. This is the same immutability rule the other contracts
  apply to their single input, applied per step.
- **Each attestation is hash committed at submission** and the record hash binds
  all of them plus the params, so any later swap is detectable and settles as
  `RECORD_SWAPPED`.
- **Only the designated address can attest its step.** The creator has no special
  power here at all: it cannot attest, it cannot evaluate preferentially, and
  after the first attestation it cannot even abandon.
- **`evaluate` is permissionless** once the chain is complete, so no custodian
  can sit on an inconvenient verdict.
- **Every outcome is terminal**, `UNDETERMINED` included, so nobody can re-roll
  the judgment.
- **Step definitions and attestations are untrusted data**, fenced with a marker
  derived from the params hash and labelled as material under examination, with
  an explicit instruction to ignore embedded claims that the chain is verified.
  An injection would have to move the same integer across independent validators
  to settle.
- **`abandon`** closes a chain nobody has attested yet, so a stale chain does not
  sit open forever. It is blocked the moment the first custodian signs.

## Why it converges

Locating a boundary in an ordered sequence is a single discrete choice among
`n + 1` options, and the ordering makes it monotone: a model that reads the chain
in order and stops at the first failure has one decision to make, not n. Two
validators that would describe the failure differently still return the same
index, and only the index is compared.

There is a second reason to prefer the index over per-step flags. Per-step flags
invite a model to assess step 7 after step 3 has already failed, which is not a
question with an answer. The index makes the dependency structure part of the
question rather than something the aggregation has to repair afterwards.

## Interface

| Method | Who | Effect |
| --- | --- | --- |
| `create_chain(chain_id, subject, steps_text, custodians_text)` | creator | Freezes subject, ordered steps (2 to 8) and one distinct custodian per step. Returns the params hash. |
| `attest(chain_id, statement, statement_hash)` | designated custodian | Attests the next open step. In order, one shot. Reverts on hash mismatch. |
| `abandon(chain_id)` | creator | Closes a chain with no attestations yet. |
| `evaluate(chain_id)` | anyone | Judges a complete chain. Terminal. |
| `status_of`, `outcome_of`, `reason_of` | view | Lifecycle and outcome. |
| `pending_step`, `pending_custodian` | view | Which step is waiting and on whom. |
| `first_break_of`, `broken_step` | view | The boundary and the failing step's text. |
| `steps_of`, `custodians_of`, `attestations_of` | view | The frozen terms and the assembled record. |
| `statement_hashes_of`, `params_hash_of`, `record_hash_of` | view | The commitments. |
| `explanation_of` | view | Readable reasoning. Audit only, never consensus. |
| `chain_ids` | view | Enumerates chains. |

### Hash convention

All hashes are `keccak256` over canonical text: line endings normalised to `\n`,
trailing whitespace stripped per line, ends stripped. An attestation is
collapsed to a single line and capped at 600 characters before hashing, so
reproduce that form off-chain and the contract will accept the hash. The record
hash is taken over the params hash, a newline, and the attestation hashes joined
by newlines, in step order.

## Cost

One LLM call per `evaluate`, replicated per validator. No web fetch. Storage
cost is dominated by the attestations, which is why each is capped at 600
characters: an attestation is a statement of fact about one handoff, not a
report.

## Testing

```
python3 sim/check.py
```

Seven cases, all passing: an intact chain, a break at a named step, an
incomplete chain that is never judged, ordering and designation enforcement,
hash commitment and record pinning verified against a recomputed hash, an
out-of-range index and a provider failure both settling as `UNDETERMINED`, and
the creation guards including duplicate custodians.

This does **not** test consensus - that is what hosted Studio exercises, and
`TEST_PLAN.md` records what was run there. Full live LLM adjudication is not
simulated offline.

## Layout

```
contract.py     the Intelligent Contract
README.md       this file
TEST_PLAN.md    seven cases, expected results, Studio notes
sim/            offline stand-in for the SDK plus the seven-case check
```

Solo project. MIT licensed.
