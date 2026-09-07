import importlib.util
import hashlib
import pathlib
import sys
import types


CREATOR = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
ALICE = "0x1111111111111111111111111111111111111111"
BOB = "0x2222222222222222222222222222222222222222"
CAROL = "0x3333333333333333333333333333333333333333"


class UserError(Exception):
    pass


class Address(str):
    def __new__(cls, value):
        return str.__new__(cls, str(value))

    @property
    def as_hex(self):
        return str(self)


Address.ZERO = Address("0x0000000000000000000000000000000000000000")


class TreeMap(dict):
    @classmethod
    def __class_getitem__(cls, _item):
        return cls


class DynArray(list):
    @classmethod
    def __class_getitem__(cls, _item):
        return cls


class Keccak256:
    def __init__(self):
        self._h = hashlib.sha3_256()

    def update(self, data):
        self._h.update(data)

    def hexdigest(self):
        return self._h.hexdigest()


class Event:
    def emit(self):
        return None


def allow_storage(cls):
    return cls


class Public:
    def write(self, fn):
        return fn

    def view(self, fn):
        return fn


class Nondet:
    responses = []
    fail_next = False

    @classmethod
    def exec_prompt(cls, _prompt, **_kwargs):
        if cls.fail_next:
            cls.fail_next = False
            raise RuntimeError("provider down")
        if not cls.responses:
            raise RuntimeError("no response")
        return cls.responses.pop(0)


class EqPrinciple:
    @staticmethod
    def prompt_comparative(fn, _principle):
        return fn()


message = types.SimpleNamespace(sender_address=Address(CREATOR))
gl = types.SimpleNamespace(
    Contract=object,
    Event=Event,
    public=Public(),
    vm=types.SimpleNamespace(UserError=UserError),
    message=message,
    nondet=Nondet,
    eq_principle=EqPrinciple(),
)

genlayer = types.ModuleType("genlayer")
for name, value in {
    "Address": Address,
    "TreeMap": TreeMap,
    "DynArray": DynArray,
    "Keccak256": Keccak256,
    "allow_storage": allow_storage,
    "u32": int,
    "gl": gl,
}.items():
    setattr(genlayer, name, value)
sys.modules["genlayer"] = genlayer

root = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("contract", root / "contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def fresh():
    verifier = contract.CustodyChainVerifier()
    verifier.chains = TreeMap()
    verifier.ids = DynArray()
    Nondet.responses = []
    Nondet.fail_next = False
    message.sender_address = Address(CREATOR)
    return verifier


def must_raise(fn, code):
    try:
        fn()
    except UserError as exc:
        assert str(exc) == code, f"expected {code}, got {exc}"
        return
    raise AssertionError(f"expected {code}")


def create_chain(verifier, cid="case"):
    return verifier.create_chain(
        cid,
        "evidence bag 12",
        "collection\ntransport\nintake",
        f"{ALICE}\n{BOB}\n{CAROL}",
    )


def attest_next(verifier, sender, cid, statement):
    message.sender_address = Address(sender)
    digest = contract._digest(statement)
    return verifier.attest(cid, statement, digest)


def complete_chain(verifier, cid="case"):
    create_chain(verifier, cid)
    attest_next(verifier, ALICE, cid, "Alice collected evidence bag 12.")
    attest_next(verifier, BOB, cid, "Bob received evidence bag 12 from Alice and transported it.")
    attest_next(verifier, CAROL, cid, "Carol received evidence bag 12 from Bob for intake.")
    message.sender_address = Address(CREATOR)


def case_1_intact_chain():
    verifier = fresh()
    complete_chain(verifier)
    assert verifier.status_of("case") == "COMPLETE"
    assert verifier.pending_step("case") == 0
    Nondet.responses.append({"first_break": 0, "why": "all steps connect"})
    assert verifier.evaluate("case") == "INTACT"
    assert verifier.outcome_of("case") == "INTACT"
    assert verifier.first_break_of("case") == 0
    assert verifier.broken_step("case") == ""
    assert verifier.explanation_of("case") == "all steps connect"


def case_2_broken_at_named_step():
    verifier = fresh()
    complete_chain(verifier)
    Nondet.responses.append('{"first_break": 2, "why": "transport gap"}')
    assert verifier.evaluate("case") == "BROKEN"
    assert verifier.first_break_of("case") == 2
    assert verifier.broken_step("case") == "transport"
    must_raise(lambda: verifier.evaluate("case"), "CHAIN_INCOMPLETE_OR_SETTLED")


def case_3_incomplete_never_judged():
    verifier = fresh()
    create_chain(verifier)
    attest_next(verifier, ALICE, "case", "Alice collected evidence bag 12.")
    assert verifier.pending_step("case") == 2
    assert verifier.pending_custodian("case") == BOB
    must_raise(lambda: verifier.evaluate("case"), "CHAIN_INCOMPLETE_OR_SETTLED")
    assert verifier.outcome_of("case") == "NONE"


def case_4_ordered_and_designated():
    verifier = fresh()
    create_chain(verifier)
    must_raise(
        lambda: verifier.attest("case", "creator tries", contract._digest("creator tries")),
        "NOT_DESIGNATED_CUSTODIAN",
    )
    message.sender_address = Address(CAROL)
    must_raise(
        lambda: verifier.attest("case", "carol early", contract._digest("carol early")),
        "NOT_DESIGNATED_CUSTODIAN",
    )
    attest_next(verifier, ALICE, "case", "Alice collected evidence bag 12.")
    message.sender_address = Address(ALICE)
    must_raise(
        lambda: verifier.attest("case", "alice again", contract._digest("alice again")),
        "NOT_DESIGNATED_CUSTODIAN",
    )


def case_5_hash_commitment_and_record_pin():
    verifier = fresh()
    params = create_chain(verifier)
    message.sender_address = Address(ALICE)
    must_raise(lambda: verifier.attest("case", "bad", "0x00"), "HASH_MISMATCH")
    must_raise(lambda: verifier.attest("case", " \n ", contract._digest(" ")), "EMPTY_STATEMENT")
    attest_next(verifier, ALICE, "case", "Alice collected evidence bag 12.")
    assert verifier.record_hash_of("case") == ""
    attest_next(verifier, BOB, "case", "Bob received evidence bag 12 from Alice and transported it.")
    attest_next(verifier, CAROL, "case", "Carol received evidence bag 12 from Bob for intake.")
    hashes = "\n".join(verifier.statement_hashes_of("case"))
    assert verifier.record_hash_of("case") == contract._digest(params + "\n" + hashes)


def case_6_bad_index_and_provider_failure():
    verifier = fresh()
    complete_chain(verifier)
    Nondet.responses.append({"first_break": 9, "why": "bad"})
    assert verifier.evaluate("case") == "UNDETERMINED"
    assert verifier.reason_of("case") == "BREAK_OUT_OF_RANGE"

    verifier = fresh()
    complete_chain(verifier)
    Nondet.fail_next = True
    assert verifier.evaluate("case") == "UNDETERMINED"
    assert verifier.reason_of("case") == "JUDGMENT_UNAVAILABLE"


def case_7_creation_guards_and_abandon():
    verifier = fresh()
    must_raise(
        lambda: verifier.create_chain("few", "subject", "one", f"{ALICE}"),
        "TOO_FEW_STEPS",
    )
    must_raise(
        lambda: verifier.create_chain(
            "many", "subject", "\n".join(str(i) for i in range(9)), "\n".join([ALICE, BOB, CAROL, "0x4444444444444444444444444444444444444444", "0x5555555555555555555555555555555555555555", "0x6666666666666666666666666666666666666666", "0x7777777777777777777777777777777777777777", "0x8888888888888888888888888888888888888888", "0x9999999999999999999999999999999999999999"])
        ),
        "TOO_MANY_STEPS",
    )
    must_raise(
        lambda: verifier.create_chain("dup", "subject", "one\ntwo", f"{ALICE}\n{ALICE}"),
        "DUPLICATE_CUSTODIAN",
    )
    must_raise(
        lambda: verifier.create_chain("count", "subject", "one\ntwo\nthree", f"{ALICE}\n{BOB}"),
        "CUSTODIAN_COUNT_MISMATCH",
    )
    must_raise(
        lambda: verifier.create_chain("empty", " \n ", "one\ntwo", f"{ALICE}\n{BOB}"),
        "EMPTY_SUBJECT",
    )
    create_chain(verifier, "abandon")
    assert verifier.abandon("abandon") == "ABANDONED"
    assert verifier.pending_step("abandon") == 0
    assert verifier.pending_custodian("abandon") == ""
    message.sender_address = Address(ALICE)
    must_raise(
        lambda: verifier.attest("abandon", "late", contract._digest("late")),
        "CHAIN_NOT_OPEN",
    )

    verifier = fresh()
    create_chain(verifier, "started")
    attest_next(verifier, ALICE, "started", "Alice collected evidence bag 12.")
    message.sender_address = Address(CREATOR)
    must_raise(lambda: verifier.abandon("started"), "ALREADY_ATTESTED")


cases = [
    case_1_intact_chain,
    case_2_broken_at_named_step,
    case_3_incomplete_never_judged,
    case_4_ordered_and_designated,
    case_5_hash_commitment_and_record_pin,
    case_6_bad_index_and_provider_failure,
    case_7_creation_guards_and_abandon,
]

for case in cases:
    case()
    print(f"PASS {case.__name__}")

print(f"{len(cases)}/{len(cases)} pass")
