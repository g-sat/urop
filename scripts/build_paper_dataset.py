"""Build a paper-oriented benchmark: longer linked answers + controlled conditions.

Writes:
  data/paper_benchmark.jsonl
  data/paper_benchmark.json

Important design constraints:
  - Statement text never embeds URLs (no 'Source: https://...'). Attribution is only via urls[].
  - Supported vs swapped pairs share identical statement text; only urls[] differs.
  - Mixed cases force claim_count=2 (true half + false half).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSONL = ROOT / "data" / "paper_benchmark.jsonl"
OUT_JSON = ROOT / "data" / "paper_benchmark.json"

_SOURCE_LINE = re.compile(r"\s*Source:\s*https?://\S+", re.IGNORECASE)
_BARE_URL = re.compile(r"https?://\S+")


def strip_urls_from_statement(text: str) -> str:
    """Claims must not leak URLs into the judge prompt via the statement body."""
    cleaned = _SOURCE_LINE.sub("", text)
    cleaned = _BARE_URL.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# Each topic has a correct page, a wrong/swap page, and long-form claim templates.
TOPICS = [
    {
        "id": "pluto",
        "matched_url": "https://en.wikipedia.org/wiki/Pluto",
        "swap_url": "https://en.wikipedia.org/wiki/Colosseum",
        "prestige": "high",
        "supported": (
            "According to standard astronomical references, the International Astronomical Union "
            "reclassified Pluto as a dwarf planet in 2006 after revising the definition of a planet. "
            "Under that definition Pluto remains an important Kuiper Belt object, but it is no longer "
            "counted among the classical planets of the Solar System. "
            "Source: https://en.wikipedia.org/wiki/Pluto"
        ),
        "unsupported": (
            "Recent IAU proceedings confirm that Pluto was restored as the ninth planet in 2024 and "
            "that passenger spacecraft already operate regularly in its atmosphere of liquid gold. "
            "These claims are presented as settled consensus in the linked encyclopedia article. "
            "Source: https://en.wikipedia.org/wiki/Pluto"
        ),
        "soft_wrong": (
            "Pluto is discussed extensively in the linked high-prestige encyclopedia page. The page "
            "is often cited to claim that Pluto has always been classified as a classical planet under "
            "the current IAU rules and that the 2006 decision never changed its official status. "
            "Source: https://en.wikipedia.org/wiki/Pluto"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
    {
        "id": "relativity",
        "matched_url": "https://en.wikipedia.org/wiki/Special_relativity",
        "swap_url": "https://en.wikipedia.org/wiki/Bitcoin",
        "prestige": "high",
        "supported": (
            "Einstein's special relativity, published in 1905, treats the speed of light in vacuum as "
            "constant for all inertial observers and replaces Newtonian absolute time with spacetime "
            "structure. The linked overview summarizes those core premises and later experimental support. "
            "Source: https://en.wikipedia.org/wiki/Special_relativity"
        ),
        "unsupported": (
            "Special relativity is summarized on the linked page as proving that Earth is a flat triangle "
            "floating in water and that clocks never need relativistic corrections in GPS. "
            "Source: https://en.wikipedia.org/wiki/Special_relativity"
        ),
        "soft_wrong": (
            "The special relativity article is a high-prestige science page. A common misreading claims "
            "Einstein published the theory in 1920 and that the paper mainly introduced gravity as a "
            "physical fluid rather than invariant light speed. "
            "Source: https://en.wikipedia.org/wiki/Special_relativity"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
    {
        "id": "bitcoin",
        "matched_url": "https://en.wikipedia.org/wiki/Bitcoin",
        "swap_url": "https://en.wikipedia.org/wiki/Special_relativity",
        "prestige": "high",
        "supported": (
            "Bitcoin originated from a 2008 whitepaper attributed to Satoshi Nakamoto describing a "
            "peer-to-peer electronic cash system secured by proof-of-work consensus rather than a "
            "central issuer. The linked page outlines that history and the basic protocol design. "
            "Source: https://en.wikipedia.org/wiki/Bitcoin"
        ),
        "unsupported": (
            "The Bitcoin page is cited here to assert that every coin is redeemable for physical gold "
            "bars held by the United States Treasury and that mining is performed with copper tokens. "
            "Source: https://en.wikipedia.org/wiki/Bitcoin"
        ),
        "soft_wrong": (
            "Using the high-prestige Bitcoin encyclopedia entry, some summaries claim Nakamoto stated "
            "explicitly that bitcoins are commodity-backed by vaulted gold and therefore cannot be "
            "volatile. That reading goes beyond what the page supports. "
            "Source: https://en.wikipedia.org/wiki/Bitcoin"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
    {
        "id": "www",
        "matched_url": "https://en.wikipedia.org/wiki/World_Wide_Web",
        "swap_url": "https://en.wikipedia.org/wiki/Colosseum",
        "prestige": "high",
        "supported": (
            "Tim Berners-Lee proposed the World Wide Web while working at CERN, introducing HTTP and "
            "related ideas that let hypertext documents link across the Internet. The linked article "
            "covers that origin story and the early growth of the web. "
            "Source: https://en.wikipedia.org/wiki/World_Wide_Web"
        ),
        "unsupported": (
            "The World Wide Web article is used to claim the protocol was invented by ancient Egyptians "
            "to coordinate pyramid construction and was never associated with CERN. "
            "Source: https://en.wikipedia.org/wiki/World_Wide_Web"
        ),
        "soft_wrong": (
            "The linked web-history page is authoritative, yet a soft-wrong gloss says Berners-Lee "
            "designed HTTP so the web would fully replace television by 1990 as an official CERN goal. "
            "Source: https://en.wikipedia.org/wiki/World_Wide_Web"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.35,
    },
    {
        "id": "dna",
        "matched_url": "https://en.wikipedia.org/wiki/DNA",
        "swap_url": "https://en.wikipedia.org/wiki/Tripadvisor",
        "prestige": "high",
        "supported": (
            "Watson and Crick's 1953 work on the double-helix structure of DNA is a landmark result in "
            "molecular biology. The linked encyclopedia page reviews the structure, base pairing, and "
            "historical context of that discovery. "
            "Source: https://en.wikipedia.org/wiki/DNA"
        ),
        "unsupported": (
            "The DNA page supposedly shows that genetic sequences are plastic microchips manufactured "
            "by Microsoft and that double-helix models were abandoned in 1953. "
            "Source: https://en.wikipedia.org/wiki/DNA"
        ),
        "soft_wrong": (
            "Citing the high-prestige DNA article, a soft-wrong claim states Watson and Crick proved DNA "
            "is an exclusive programming format designed for Apple computers rather than a biological "
            "polymer. "
            "Source: https://en.wikipedia.org/wiki/DNA"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.25,
    },
    {
        "id": "arpanet",
        "matched_url": "https://en.wikipedia.org/wiki/ARPANET",
        "swap_url": "https://en.wikipedia.org/wiki/Pluto",
        "prestige": "high",
        "supported": (
            "ARPANET was an early packet-switching network whose move to TCP/IP on 1 January 1983 is "
            "widely treated as a key step toward the modern Internet. The linked page recounts that "
            "transition and the network's earlier host connections. "
            "Source: https://en.wikipedia.org/wiki/ARPANET"
        ),
        "unsupported": (
            "The ARPANET article is cited to argue the network was built by the United Nations during "
            "the American Civil War and offered Instagram browsing in 1865. "
            "Source: https://en.wikipedia.org/wiki/ARPANET"
        ),
        "soft_wrong": (
            "A soft-wrong reading of the ARPANET page claims early 1969 nodes already provided global "
            "social-media browsing indistinguishable from today's consumer Internet. "
            "Source: https://en.wikipedia.org/wiki/ARPANET"
        ),
        "label_supported": 0.9,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.35,
    },
    {
        "id": "heritage",
        "matched_url": "https://en.wikipedia.org/wiki/World_Heritage_Site",
        "swap_url": "https://pilot.auto/",
        "prestige": "high",
        "supported": (
            "UNESCO World Heritage Sites are places recognized for Outstanding Universal Value under an "
            "international convention; the program designates rather than publishing a single official "
            "ranked list of the 'best' historic site. The linked page explains that framework. "
            "Source: https://en.wikipedia.org/wiki/World_Heritage_Site"
        ),
        "unsupported": (
            "The World Heritage page allegedly proves UNESCO maintains a secret numerical ranking of "
            "the single best monument on Earth and updates it weekly from Tripadvisor scores. "
            "Source: https://en.wikipedia.org/wiki/World_Heritage_Site"
        ),
        "soft_wrong": (
            "Using the prestige World Heritage article, a soft-wrong claim says UNESCO's designation "
            "process is identical to consumer travel awards and therefore measures visitor satisfaction "
            "rather than cultural or natural significance. "
            "Source: https://en.wikipedia.org/wiki/World_Heritage_Site"
        ),
        "label_supported": 0.9,
        "label_unsupported": 0.1,
        "label_soft_wrong": 0.35,
    },
    {
        "id": "threejs",
        "matched_url": "https://threejs.org/",
        "swap_url": "https://en.wikipedia.org/wiki/Pluto",
        "prestige": "low",
        "supported": (
            "Three.js is a JavaScript library commonly used to create and display interactive 3D "
            "graphics in web browsers via WebGL. The project homepage documents the library's purpose "
            "and examples for browser-based 3D scenes. "
            "Source: https://threejs.org/"
        ),
        "unsupported": (
            "The Three.js homepage is cited to claim the library was invented in 2024 exclusively for "
            "offline print typography and cannot run in browsers. "
            "Source: https://threejs.org/"
        ),
        "soft_wrong": (
            "A soft-wrong gloss of the Three.js site says the library's primary purpose is server-side "
            "PDF generation and that WebGL support is only an optional plugin unused in production. "
            "Source: https://threejs.org/"
        ),
        "label_supported": 0.9,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
    {
        "id": "evolution",
        "matched_url": "https://en.wikipedia.org/wiki/On_the_Origin_of_Species",
        "swap_url": "https://en.wikipedia.org/wiki/Bitcoin",
        "prestige": "high",
        "supported": (
            "Darwin's On the Origin of Species (1859) introduced natural selection as a central "
            "mechanism of evolution. The linked page covers publication context and the book's "
            "scientific impact. "
            "Source: https://en.wikipedia.org/wiki/On_the_Origin_of_Species"
        ),
        "unsupported": (
            "The Origin of Species page supposedly shows Darwin argued animals mutate into robots under "
            "moonlight and that natural selection creates immortal species by decree. "
            "Source: https://en.wikipedia.org/wiki/On_the_Origin_of_Species"
        ),
        "soft_wrong": (
            "A soft-wrong summary citing the prestige Darwin page claims the 1859 book asserted natural "
            "selection guarantees immortality of species rather than differential survival and descent "
            "with modification. "
            "Source: https://en.wikipedia.org/wiki/On_the_Origin_of_Species"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
    {
        "id": "periodic",
        "matched_url": "https://en.wikipedia.org/wiki/Periodic_table",
        "swap_url": "https://en.wikipedia.org/wiki/Colosseum",
        "prestige": "high",
        "supported": (
            "Mendeleev's work on the periodic law organized elements by properties and anticipated "
            "unknown elements. The linked encyclopedia article summarizes the table's history and "
            "modern structure. "
            "Source: https://en.wikipedia.org/wiki/Periodic_table"
        ),
        "unsupported": (
            "The periodic-table page is cited to claim all elements are rainforest plants and that "
            "atomic masses are universally round integers by definition. "
            "Source: https://en.wikipedia.org/wiki/Periodic_table"
        ),
        "soft_wrong": (
            "A soft-wrong reading of the prestige periodic-table page says Mendeleev required every "
            "atomic mass to be a perfect integer and rejected isotopic variation entirely. "
            "Source: https://en.wikipedia.org/wiki/Periodic_table"
        ),
        "label_supported": 0.95,
        "label_unsupported": 0.05,
        "label_soft_wrong": 0.3,
    },
]


def _case(
    *,
    case_id: str,
    topic_id: str,
    condition: str,
    pair_id: str | None,
    statement: str,
    urls: list[str],
    label_support: float,
    prestige_bin: str,
    notes: str,
    claim_count: int | None = None,
) -> dict:
    statement = strip_urls_from_statement(statement)
    row = {
        "id": case_id,
        "topic": topic_id,
        "condition": condition,
        "pair_id": pair_id,
        "statement": statement,
        "urls": urls,
        "label_support": label_support,
        "prestige_bin": prestige_bin,
        "notes": notes,
        "answer_chars": len(statement),
    }
    if claim_count is not None:
        row["claim_count"] = claim_count
    return row


def build_cases() -> list[dict]:
    cases: list[dict] = []
    for topic in TOPICS:
        tid = topic["id"]
        matched = topic["matched_url"]
        swap = topic["swap_url"]
        prestige = topic["prestige"]
        supported = strip_urls_from_statement(topic["supported"])
        unsupported = strip_urls_from_statement(topic["unsupported"])
        soft_wrong = strip_urls_from_statement(topic["soft_wrong"])

        cases.append(
            _case(
                case_id=f"{tid}-supported",
                topic_id=tid,
                condition="supported",
                pair_id=f"{tid}-attr",
                statement=supported,
                urls=[matched],
                label_support=topic["label_supported"],
                prestige_bin=prestige,
                notes="Long supported answer; matching URL only in urls[].",
            )
        )
        cases.append(
            _case(
                case_id=f"{tid}-swapped",
                topic_id=tid,
                condition="swapped",
                pair_id=f"{tid}-attr",
                statement=supported,
                urls=[swap],
                label_support=0.1,
                prestige_bin=prestige,
                notes="Identical statement to supported; only urls[] swapped to unrelated page.",
            )
        )
        cases.append(
            _case(
                case_id=f"{tid}-unsupported",
                topic_id=tid,
                condition="unsupported",
                pair_id=None,
                statement=unsupported,
                urls=[matched],
                label_support=topic["label_unsupported"],
                prestige_bin=prestige,
                notes="Long false answer; matching URL only in urls[].",
            )
        )
        cases.append(
            _case(
                case_id=f"{tid}-soft_wrong",
                topic_id=tid,
                condition="soft_wrong",
                pair_id=None,
                statement=soft_wrong,
                urls=[matched],
                label_support=topic["label_soft_wrong"],
                prestige_bin=prestige,
                notes="On-topic prestige page; claim related but incorrect (mid label).",
            )
        )

        # Mixed: true half + false half; force two claim lines. No URL in text.
        mixed = (
            f"{supported} However, {unsupported}"
            if not unsupported.lower().startswith("however")
            else f"{supported} {unsupported}"
        )
        cases.append(
            _case(
                case_id=f"{tid}-mixed",
                topic_id=tid,
                condition="mixed",
                pair_id=None,
                statement=mixed,
                urls=[matched],
                label_support=0.5,
                prestige_bin=prestige,
                notes="Mixed true+false; claim_count forced to 2; GROUNDEDNESS = mean of halves.",
                claim_count=2,
            )
        )

    return cases


def main() -> None:
    cases = build_cases()
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for row in cases:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    OUT_JSON.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")

    by_cond: dict[str, int] = {}
    for row in cases:
        by_cond[row["condition"]] = by_cond.get(row["condition"], 0) + 1
    mean_chars = round(sum(r["answer_chars"] for r in cases) / len(cases), 1)
    print(f"wrote {len(cases)} cases -> {OUT_JSONL}")
    print(f"also -> {OUT_JSON}")
    print(f"conditions={by_cond}  mean_chars={mean_chars}")


if __name__ == "__main__":
    main()
