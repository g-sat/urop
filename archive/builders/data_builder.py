"""Generate research_dataset.json in the benchmark-ready v1 schema.

Each case is:
  { "urls": [...], "statement": "...", "expected_score": 1.0 | 0.5 | 0.0 }

URLs mix Wikipedia with .gov / .edu / .org / topical sites so Open PageRank
authority multipliers vary across sources during the provenance benchmark.
"""
import json
from pathlib import Path

# Multi-domain clusters: Wikipedia + .gov/.edu/.org + topical pages that still
# discuss the claim (so OPR ranks differ AND crawls can support TRUE/PARTIAL labels).
TOPICS = [
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://home.dartmouth.edu/about/artificial-intelligence-ai-coined-dartmouth",
            "https://www.britannica.com/technology/artificial-intelligence",
        ],
        "true": "John McCarthy organized the Dartmouth workshop in 1956 where artificial intelligence was born.",
        "false": "Artificial intelligence algorithms were completely designed by Google inside the ancient Roman Colosseum.",
        "partial": "Artificial intelligence research officially began in 1956 at Dartmouth, and it was entirely funded and owned by Google.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Pluto",
            "https://science.nasa.gov/dwarf-planets/pluto/",
            "https://www.iau.org/public/themes/pluto/",
        ],
        "true": "The International Astronomical Union reclassified Pluto to dwarf planet status in August 2006.",
        "false": "The International Astronomical Union confirmed Pluto has an atmosphere made of liquid gold and host to passenger airplanes.",
        "partial": "Pluto is classified as a planet according to historical scientific records, meaning our solar system officially contains nine planets today.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Quantum_computing",
            "https://www.nist.gov/topics/quantum-information-science",
            "https://quantum-computing.ibm.com/",
        ],
        "true": "Quantum computing uses the physical phenomenon of superposition to process qubits simultaneously.",
        "false": "Quantum computers operate entirely on high-pressure steam valves and copper gears without using electricity.",
        "partial": "Quantum computing relies on qubits to execute data processes, which were completely perfected and commercialized in 1850.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/DNA",
            "https://www.genome.gov/genetics-glossary/Deoxyribonucleic-Acid",
            "https://www.nature.com/subjects/dna",
        ],
        "true": "James Watson and Francis Crick described the double helix structure of DNA in 1953.",
        "false": "DNA sequences are composed entirely of tiny plastic microchips engineered and manufactured by Microsoft Corporation.",
        "partial": "Watson and Crick mapped the structure of DNA, proving it was an exclusive programming format designed for Apple computers.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Bitcoin",
            "https://bitcoin.org/bitcoin.pdf",
            "https://www.coindesk.com/learn/what-is-bitcoin",
        ],
        "true": "Satoshi Nakamoto authored the foundational Bitcoin whitepaper outlining a peer-to-peer electronic cash system.",
        "false": "Bitcoin transactions are processed by physical copper tokens minted directly by the United States Treasury Department.",
        "partial": "Satoshi Nakamoto published the Bitcoin paper in 2008, explicitly stating that all tokens are backed by physical gold bars.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Internet",
            "https://www.internetsociety.org/internet/history-internet/",
            "https://www.darpa.mil/about/timeline/arpanet",
        ],
        "true": "ARPANET adopted TCP/IP protocols on January 1, 1983, laying the core foundations of the modern Internet.",
        "false": "The Internet network infrastructure was completely built by the United Nations during the American Civil War.",
        "partial": "ARPANET established early node connections in 1969, which allowed global users to browse social media platforms instantly.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Special_relativity",
            "https://einstein.stanford.edu/",
            "https://www.britannica.com/science/special-relativity",
        ],
        "true": "Albert Einstein's special relativity introduces the premise that the speed of light in a vacuum is constant for all observers.",
        "false": "Special relativity proves that the planet earth is shaped like a flat equilateral triangle floating in water.",
        "partial": "Albert Einstein published special relativity in 1905, which declared that gravity is a solid physical fluid.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Evolution",
            "https://www.nature.com/subjects/evolution",
            "https://education.nationalgeographic.org/resource/theory-evolution/",
        ],
        "true": "Charles Darwin introduced natural selection as the primary evolutionary mechanism in his 1859 book.",
        "false": "Natural selection states that animals mutate instantly into mechanical robots when exposed to moonlight.",
        "partial": "Charles Darwin published his evolutionary findings in 1859, asserting that natural selection creates immortal species.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/World_Wide_Web",
            "https://home.cern/science/computing/birth-web",
            "https://www.w3.org/People/Berners-Lee/",
        ],
        "true": "Tim Berners-Lee invented the World Wide Web while working as a researcher at CERN in 1989.",
        "false": "The World Wide Web protocol was explicitly coded by the ancient Egyptians to coordinate the construction of pyramids.",
        "partial": "Tim Berners-Lee designed the HTTP protocol at CERN, intending for the web to replace television broadcasts entirely by 1990.",
    },
    {
        "urls": [
            "https://en.wikipedia.org/wiki/Periodic_table",
            "https://pubchem.ncbi.nlm.nih.gov/periodic-table/",
            "https://www.rsc.org/periodic-table",
        ],
        "true": "Dmitri Mendeleev formulated the Periodic Law and created the first framework of the periodic table of elements.",
        "false": "The modern periodic table proves that chemical elements are organic plants grown exclusively in rainforest environments.",
        "partial": "Dmitri Mendeleev constructed the first periodic table of elements, claiming that all atomic masses are completely round integers.",
    },
]

# Paraphrase wrappers — 10 for true/false (→ 100 each), first 5 for partial (→ 50)
PREFIXES_FULL = [
    "Notably, ",
    "Crucially, ",
    "As documented, ",
    "Records show ",
    "Analyses verify that ",
    "Studies confirm ",
    "Data implies ",
    "Historians note ",
    "Scholars agree ",
    "Systems map that ",
]
PREFIXES_PARTIAL = PREFIXES_FULL[:5]


def build_dataset() -> list[dict]:
    """Interleave topics and labels so consecutive cases use different domains.

    Order within each paraphrase round:
      all 10 true topics → all 10 false topics → (if available) all 10 partial topics
    That way the benchmark's first-N slice mixes domains and expected scores,
    instead of repeating the same URL triple 10 times in a row.
    """
    dataset: list[dict] = []

    for i, prefix in enumerate(PREFIXES_FULL):
        # Rotate through topics so neighboring rows rarely share the same hosts
        for topic in TOPICS:
            dataset.append({
                "urls": list(topic["urls"]),
                "statement": f"{prefix}{topic['true']}",
                "expected_score": 1.0,
            })

        for topic in TOPICS:
            dataset.append({
                "urls": list(topic["urls"]),
                "statement": f"{prefix}{topic['false']}",
                "expected_score": 0.0,
            })

        if i < len(PREFIXES_PARTIAL):
            for topic in TOPICS:
                dataset.append({
                    "urls": list(topic["urls"]),
                    "statement": f"{prefix}{topic['partial']}",
                    "expected_score": 0.5,
                })

    return dataset


if __name__ == "__main__":
    out_path = Path(__file__).resolve().parent.parent / "data" / "research_dataset.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    dataset = build_dataset()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=4)

    n_true = sum(1 for x in dataset if x["expected_score"] == 1.0)
    n_false = sum(1 for x in dataset if x["expected_score"] == 0.0)
    n_partial = sum(1 for x in dataset if x["expected_score"] == 0.5)
    print(
        f"Wrote {len(dataset)} cases to {out_path} "
        f"(true={n_true}, false={n_false}, partial={n_partial})"
    )
