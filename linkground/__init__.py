"""
LinkGround
----------
APIs for measuring LLM outputs against linked web sources.

Pipeline novelty:
  statement + URLs -> crawl evidence -> continuous groundedness
  -> Open PageRank authority weighting -> trust index
"""

__version__ = "2.1.0"
__all__ = ["__version__"]
